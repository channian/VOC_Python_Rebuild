"""
tests_integration/test_main_b_routes.py — WP6：main_b 補完路由的整合測試（真 PG）

涵蓋：每個新頁面 GET 200＋四條寫入路徑（申請隔離→送簽→簽核、QA 寫值、規格送簽→核准套用）
走 HTTP API 成功並反映在 DB。使用 conftest 的 b_db fixture（每測試前自動重 seed）。
"""

from datetime import datetime, timedelta
from unittest import mock

import pytest
from sqlalchemy import select

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from models_b import Isolation, MailList, Spec, SpecApply, ReadingCurrent  # noqa: E402
from scripts.seed_test_data import (  # noqa: E402
    APPLICANT_EMPNO, SIGNER_EMPNO, TEST_PLANT_ID, TEST_PLANT_NO,
)
from services.flow_service import FlowStatus  # noqa: E402


@pytest.fixture()
def client(b_db):
    """TestClient（b_db fixture 先行確保 schema+seed 就緒；路由自行開 session）。"""
    from main_b import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def as_user(monkeypatch):
    """身分切換 helper：模擬 .env 改 MOCK_USER_EMPNO（閉環測試申請人≠簽核人）。"""
    from config import settings

    def _switch(empno: str, name: str = ""):
        monkeypatch.setattr(settings, "MOCK_USER_EMPNO", empno)
        monkeypatch.setattr(settings, "MOCK_USER_NAME", name or empno)
    return _switch


# 2026-07-06 主控更新：隔離簽核用的「水保養中」名單列已直接種進
# scripts/seed_test_data.py 本體（供瀏覽器實測也能用），本檔原本自行補這筆的
# _seed_isolation_signer() 已移除（保留會與 seed 撞主鍵）。


# ── 頁面 GET 200 ────────────────────────────────────────────────────────────

PAGES = [
    "/ui/control", "/ui/control/items?plantno=TEST1", "/ui/flow",
    "/ui/spec", "/ui/qa", "/ui/reason", "/warning/water_urgent/ui",
]


@pytest.mark.parametrize("path", PAGES)
def test_wp6_pages_render(client, path):
    r = client.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"


def test_control_items_contains_seeded_items(client):
    html = client.get("/ui/control/items?plantno=TEST1").text
    assert "pH1" in html and "Cu1" in html


# ── 寫入路徑 1：申請隔離 → 送簽 → 簽核核准 ─────────────────────────────────

def test_isolation_apply_submit_sign_via_api(client, b_db, as_user):
    # 以 TEST001（申請人）身分申請＋送簽
    as_user(APPLICANT_EMPNO, "測試申請人")
    stime = datetime.now() + timedelta(minutes=5)
    etime = stime + timedelta(minutes=50)
    payload = {
        "plantid": TEST_PLANT_ID, "mdfdesc": "WP6 API 測試", "remark": "",
        "stime": stime.isoformat(), "etime": etime.isoformat(),
        "items": [{"plantno": TEST_PLANT_NO, "item": "Cu1", "sourceid": "1"}],
    }
    r = client.post("/control/create?is_commit=false", json=payload)
    assert r.status_code == 200, r.text

    iso = b_db.execute(
        select(Isolation).where(Isolation.mdfdesc == "WP6 API 測試")
    ).scalar_one()
    assert iso.fstatus == int(FlowStatus.待簽核)

    r = client.post(f"/control/submit/{iso.id}")
    assert r.status_code == 200, r.text
    b_db.refresh(iso)
    assert iso.fstatus == int(FlowStatus.簽核中)
    assert iso.flow_id is not None

    # 申請人自己簽 → 應被擋（舊系統原設計：簽核人排除申請人本人）
    r = client.post("/flow/sign", json={"ccid": iso.id, "flowid": iso.flow_id, "actionid": 1})
    assert r.status_code == 400 and "不具備簽核資格" in r.text

    # 切換 TEST999（簽核人）身分 → 待辦看得到 → 核准成功
    as_user(SIGNER_EMPNO, "測試簽核人")
    todos = client.get("/flow/todos").json()
    assert any(t["ccid"] == iso.id for t in todos)

    # 2026-07-08 補：核准通知信 hook 曾長期是 no-op（process_sign 的 notify_callback 沒被router接上），
    # 使用者實測簽核成功但沒收到信才發現。這裡 mock 掉 send_email_sync 避免真連 SMTP，
    # 只驗證「有被呼叫、收件人是申請人的 email」——鎖住這條線不再被回歸悄悄拔掉。
    with mock.patch("routers_b.control_router_b.send_email_sync") as mock_send:
        r = client.post("/flow/sign", json={"ccid": iso.id, "flowid": iso.flow_id, "actionid": 1})
        assert r.status_code == 200, r.text
        mock_send.assert_called_once()
        subject, body, to_addrs = mock_send.call_args.args[:3]
        assert "核准" in subject
        assert to_addrs == ["TEST_PLACEHOLDER@aseglobal.com"]  # 申請人(TEST001)的 notesid 轉 email

    b_db.refresh(iso)
    assert iso.fstatus == int(FlowStatus.核准)


# ── 寫入路徑 2：QA 手測值 ───────────────────────────────────────────────────

def test_qa_update_via_api(client, b_db):
    # 種子 spec 全為 SCADA 來源；QA 防呆要求 source=QA，先把 VOC1 轉成 QA 來源再走 API
    spec = b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "VOC1")
    ).scalar_one()
    spec.source_id = 3  # QA
    b_db.commit()

    r = client.post("/qa/update", json={
        "plantno": TEST_PLANT_NO, "item": "VOC1", "rvalue": "1.23", "remark": "WP6",
    })
    assert r.status_code == 200, r.text

    rc = b_db.execute(
        select(ReadingCurrent).where(
            ReadingCurrent.plant_no == TEST_PLANT_NO, ReadingCurrent.item == "VOC1")
    ).scalar_one()
    assert float(rc.value) == pytest.approx(1.23)
    assert rc.status == "normal"


# ── 寫入路徑 3：規格送簽 → 核准套用 ─────────────────────────────────────────

def test_spec_apply_and_sign_via_api(client, b_db):
    r = client.post("/spec/apply", json={
        "plantno": TEST_PLANT_NO, "item": "Cu1", "ftype": "M",
        "LAW": "6", "OOS": "5", "OOC": "4", "alert": "3", "source_id": 1, "remark": "WP6",
    })
    assert r.status_code == 200, r.text
    formid = r.json()["formid"]

    sa = b_db.get(SpecApply, formid)
    assert sa.fstatus == int(FlowStatus.待簽核)

    r = client.post("/spec/sign", json={"formid": formid, "flowid": 0, "actionid": 1})
    assert r.status_code == 200, r.text

    b_db.expire_all()
    sa = b_db.get(SpecApply, formid)
    assert sa.fstatus == int(FlowStatus.核准)
    spec = b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "Cu1")
    ).scalar_one()
    assert float(spec.oos_high) == pytest.approx(5.0)  # 申請新值已套用回 spec


# ── 規格清單形狀（B numeric → A 字串轉接）──────────────────────────────────

def test_spec_list_shape(client):
    rows = client.get("/spec/list").json()
    assert rows, "spec/list 不應為空"
    row = next(r for r in rows if r["plantno"] == TEST_PLANT_NO and "pH" in r["item"])
    assert set(row) >= {"plantno", "item", "LAW", "OOS", "OOC", "alert", "sourceid"}
    assert "-" in row["OOS"]  # pH 雙邊規格應轉回 'low-high' 字串形狀
