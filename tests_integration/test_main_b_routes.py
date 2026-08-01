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


def test_spec_modal_sources_shape(client):
    """SPEC_SOURCES 必須是 A 棧形狀 sourceid/source（共用模板 JS 讀這兩個 key）。
    2026-07-10 使用者實測：B 版曾回 source_id/name，來源下拉全顯示 undefined，
    被誤認為編輯功能沒實作——鎖住這個形狀不再回歸。"""
    html = client.get("/ui/spec").text
    assert '"sourceid"' in html and '"source"' in html
    assert '"source_id"' not in html.split("const SPEC_SOURCES")[1][:200]


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

    # 2026-07-08 補：送簽通知信 hook 曾長期是 no-op（create_sign_flow 的 notify_callback 沒被
    # router 接上），使用者實測簽核成功、也收到核准信之後才發現「送簽當下」那封提醒簽核人
    # 的信一直沒寄——鎖住這條線不再被回歸悄悄拔掉。
    with mock.patch("routers_b.control_router_b.send_email_sync") as mock_send:
        r = client.post(f"/control/submit/{iso.id}")
        assert r.status_code == 200, r.text
        mock_send.assert_called_once()
        subject, body, to_addrs = mock_send.call_args.args[:3]
        assert "待簽核" in subject
        assert to_addrs == ["TEST_PLACEHOLDER@aseglobal.com"]  # 簽核人(TEST999)的 notesid 轉 email
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


# ── 雙邊規格判定改資料驅動（2026-07-31，item.is_dual_bound）────────────────────
#
# B 棧規格端點改成「先查 item.is_dual_bound 再驗證」，不再靠項目名稱猜單/雙邊。
# 驗證此路徑：明確雙邊的項目（名稱是「溫度D」，完全沒有 pH 字樣）能存雙邊門檻；
# 明確單邊的擋下雙邊門檻；未指定（NULL）時退回舊的名稱推測（現況不變）。

_DUAL_ITEMS = [("溫度D", True), ("溫度S", False), ("溫度N", None)]


@pytest.fixture()
def dual_bound_items(b_db):
    """建三個規格型態不同的項目（雙邊/單邊/未指定）＋各一筆空白 spec 供 /spec/update 用。"""
    from sqlalchemy import func

    from models_b import Item

    max_id = b_db.execute(select(func.max(Item.item_id))).scalar() or 0
    for offset, (name, dual) in enumerate(_DUAL_ITEMS, start=1):
        b_db.add(Item(item_id=max_id + offset, item=name, display_name=name, unit="°C",
                      is_active=True, is_dual_bound=dual))
        b_db.add(Spec(plant_no=TEST_PLANT_NO, item=name, source_id=1, seqno=90 + offset))
    b_db.commit()
    yield


def test_spec_update_accepts_double_sided_for_is_dual_bound_true(client, b_db, dual_bound_items):
    """★ 核心驗收：is_dual_bound=True 的項目（名稱不含 pH）可成功存雙邊門檻。"""
    r = client.post("/spec/update", json={
        "plantno": TEST_PLANT_NO, "item": "溫度D",
        "LAW": "20-35", "OOS": "20-35", "OOC": "22-33", "alert": "23-32",
        "source_id": 1, "remark": "dual-bound",
    })
    assert r.status_code == 200, r.text

    b_db.expire_all()
    spec = b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "溫度D")
    ).scalar_one()
    assert float(spec.oos_low) == pytest.approx(20.0)
    assert float(spec.oos_high) == pytest.approx(35.0)
    assert spec.oos_status == "valid"
    assert float(spec.ooc_low) == pytest.approx(22.0)
    assert float(spec.alert_high) == pytest.approx(32.0)


def test_spec_create_accepts_double_sided_for_is_dual_bound_true(client, b_db):
    """新增路徑同樣吃 item.is_dual_bound（此項目尚無 spec，走 /spec/create）。"""
    from sqlalchemy import func

    from models_b import Item

    max_id = b_db.execute(select(func.max(Item.item_id))).scalar() or 0
    b_db.add(Item(item_id=max_id + 1, item="溫度C", display_name="溫度C", unit="°C",
                  is_active=True, is_dual_bound=True))
    b_db.commit()

    r = client.post("/spec/create", json={
        "plantno": TEST_PLANT_NO, "item": "溫度C",
        "LAW": "20-35", "OOS": "20-35", "OOC": "22-33", "alert": "23-32", "source_id": 1,
    })
    assert r.status_code == 200, r.text

    spec = b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "溫度C")
    ).scalar_one()
    assert float(spec.oos_high) == pytest.approx(35.0)


def test_spec_update_rejects_double_sided_for_is_dual_bound_false(client, dual_bound_items):
    """is_dual_bound=False → 填雙邊門檻要被擋，且錯誤原因要傳到前端（不可吞掉）。"""
    r = client.post("/spec/update", json={
        "plantno": TEST_PLANT_NO, "item": "溫度S",
        "LAW": "20-35", "OOS": "20-35", "OOC": "22-33", "alert": "23-32", "source_id": 1,
    })
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert isinstance(detail, list)
    assert any("必須為單邊規格" in d["msg"] for d in detail)


def test_spec_update_falls_back_to_name_guess_when_null(client, dual_bound_items):
    """is_dual_bound=NULL → 退回名稱推測（溫度猜成單邊），維持現況不變。"""
    r = client.post("/spec/update", json={
        "plantno": TEST_PLANT_NO, "item": "溫度N",
        "LAW": "20-35", "OOS": "20-35", "OOC": "22-33", "alert": "23-32", "source_id": 1,
    })
    assert r.status_code == 422, r.text
    assert any("必須為單邊規格" in d["msg"] for d in r.json()["detail"])


def test_spec_apply_accepts_double_sided_for_is_dual_bound_true(client, b_db, dual_bound_items):
    """送簽路徑（/spec/apply）同樣以 item.is_dual_bound 為準。"""
    r = client.post("/spec/apply", json={
        "plantno": TEST_PLANT_NO, "item": "溫度D", "ftype": "M",
        "LAW": "20-35", "OOS": "20-35", "OOC": "22-33", "alert": "23-32", "source_id": 1,
    })
    assert r.status_code == 200, r.text

    sa = b_db.get(SpecApply, r.json()["formid"])
    assert float(sa.payload["oos_low"]) == pytest.approx(20.0)
    assert float(sa.payload["oos_high"]) == pytest.approx(35.0)


def test_spec_update_ph_still_requires_double_sided(client):
    """回歸保護：種子項目 pH1（is_dual_bound 未設定）仍走名稱推測，單邊值要被擋。"""
    r = client.post("/spec/update", json={
        "plantno": TEST_PLANT_NO, "item": "pH1",
        "LAW": "6", "OOS": "6", "OOC": "7", "alert": "7.2", "source_id": 1,
    })
    assert r.status_code == 422, r.text
    assert any("必須為雙邊規格" in d["msg"] for d in r.json()["detail"])


# ── 規格清單形狀（B numeric → A 字串轉接）──────────────────────────────────

def test_spec_list_shape(client):
    rows = client.get("/spec/list").json()
    assert rows, "spec/list 不應為空"
    row = next(r for r in rows if r["plantno"] == TEST_PLANT_NO and "pH" in r["item"])
    assert set(row) >= {"plantno", "item", "item_key", "LAW", "OOS", "OOC", "alert", "sourceid"}
    assert "-" in row["OOS"]  # pH 雙邊規格應轉回 'low-high' 字串形狀


# ── item_key：儲存鍵原樣往返（2026-08-01 修「有顯示別名的項目改不動」）──────────
#
# bug 本體：列表把 spec.item（'pH1'）換成 item.display_name（'pH'）給前端，前端原樣送回，
# 後端再用 to_storage_item() 想換回去——但那支只認硬編的 K14B/K22/九號放流口 三個廠區，
# 其他廠區（例如 TEST1）的別名項目換不回來，update_spec() 一律「找不到資料!」。
# 修法：列表多回 item_key＝真正的儲存鍵，前端原樣帶回，後端直接用，中間不轉換。


def _spec_row(client, plantno: str, display_item: str) -> dict:
    return next(
        r for r in client.get(f"/spec/list?plantno={plantno}").json() if r["item"] == display_item
    )


def test_spec_list_returns_storage_key_as_item_key(client):
    """TEST1/pH1 顯示成 'pH'，但 item_key 必須是真正的儲存鍵 'pH1'。"""
    row = _spec_row(client, TEST_PLANT_NO, "pH")
    assert row["item"] == "pH" and row["item_key"] == "pH1"
    # 以 item_key 篩選查得到（前端篩選下拉送的就是這個值）
    filtered = client.get(f"/spec/list?plantno={TEST_PLANT_NO}&item=pH1").json()
    assert [r["item_key"] for r in filtered] == ["pH1"]


def test_spec_page_embeds_item_key(client):
    """b/spec.html 內嵌的 INITIAL_SPECS 必須帶 item_key——前端寫入 payload 靠它，
    少了它整頁又會退回「拿顯示名當識別碼」的老路。"""
    html = client.get("/ui/spec").text
    embedded = html.split("const INITIAL_SPECS = ")[1].split(";\n")[0]
    assert '"item_key"' in embedded and '"pH1"' in embedded


def test_spec_update_roundtrip_alias_item_in_non_alias_plant(client, b_db):
    """★ 本次 bug 本體：廠區(TEST1)不在別名硬編清單內、項目存成 'pH1' 顯示成 'pH'，
    照前端「列表拿什麼就送回什麼」的往返流程，規格必須改得動。"""
    row = _spec_row(client, TEST_PLANT_NO, "pH")
    r = client.post("/spec/update", json={
        "plantno": row["plantno"], "item": row["item"], "item_key": row["item_key"],
        "LAW": "6-9", "OOS": "6-9", "OOC": "6.4-8.6", "alert": "6.9-8.1",
        "source_id": row["sourceid"], "remark": "item_key 往返",
    })
    assert r.status_code == 200, r.text

    b_db.expire_all()
    spec = b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "pH1")
    ).scalar_one()
    assert float(spec.ooc_low) == pytest.approx(6.4)
    assert float(spec.alert_high) == pytest.approx(8.1)


def test_spec_update_without_item_key_fails_loudly_not_silently(client, b_db):
    """沒帶 item_key 時**不做 display_name 反查**（display_name 不唯一，反查會靜默改到別筆）：
    寧可誠實回「找不到資料!」。這條鎖住「不要為了修 bug 加模糊 fallback」的設計決定。"""
    r = client.post("/spec/update", json={
        "plantno": TEST_PLANT_NO, "item": "pH",  # 只給顯示名
        "LAW": "6-9", "OOS": "6-9", "OOC": "6.4-8.6", "alert": "6.9-8.1", "source_id": 1,
    })
    assert r.status_code == 400 and "找不到資料" in r.text

    b_db.expire_all()  # 且不可誤改到任何一列
    spec = b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "pH1")
    ).scalar_one()
    assert float(spec.ooc_low) == pytest.approx(6.5)  # 仍是 seed 的原值


@pytest.fixture()
def k14b_cod2(b_db):
    """建 K14B/COD2（顯示名 COD）——**廠區在**別名硬編清單內的既有案例，用來確認沒被改壞。"""
    from sqlalchemy import func

    from models_b import Item, Plant

    max_pid = b_db.execute(select(func.max(Plant.plant_id))).scalar() or 0
    max_iid = b_db.execute(select(func.max(Item.item_id))).scalar() or 0
    b_db.add(Plant(plant_id=max_pid + 1, plant_no="K14B", kind="normal", is_show=True, sort=998))
    b_db.add(Item(item_id=max_iid + 1, item="COD2", display_name="COD", unit="mg/L", is_active=True))
    b_db.flush()
    b_db.add(Spec(plant_no="K14B", item="COD2", source_id=1, seqno=1))
    b_db.commit()
    yield


def test_spec_update_alias_plant_still_works_with_item_key(client, b_db, k14b_cod2):
    """K14B/COD2（廠區在別名清單內）帶 item_key 一樣改得動。"""
    row = _spec_row(client, "K14B", "COD")
    assert row["item_key"] == "COD2"
    r = client.post("/spec/update", json={
        "plantno": "K14B", "item": row["item"], "item_key": row["item_key"],
        "LAW": "100", "OOS": "100", "OOC": "90", "alert": "80", "source_id": 1,
    })
    assert r.status_code == 200, r.text

    b_db.expire_all()
    spec = b_db.execute(select(Spec).where(Spec.plant_no == "K14B", Spec.item == "COD2")).scalar_one()
    assert float(spec.oos_high) == pytest.approx(100.0)


def test_spec_update_alias_plant_still_works_without_item_key(client, b_db, k14b_cod2):
    """回歸保護：K14B/'COD' 不帶 item_key（A 棧形狀的舊呼叫端）仍走 to_storage_item() 退路，
    行為與改版前完全相同——修新 bug 不可以把舊路徑弄壞。"""
    r = client.post("/spec/update", json={
        "plantno": "K14B", "item": "COD",  # 只給顯示名，靠硬編別名表換成 COD2
        "LAW": "120", "OOS": "120", "OOC": "90", "alert": "80", "source_id": 1,
    })
    assert r.status_code == 200, r.text

    b_db.expire_all()
    spec = b_db.execute(select(Spec).where(Spec.plant_no == "K14B", Spec.item == "COD2")).scalar_one()
    assert float(spec.oos_high) == pytest.approx(120.0)


@pytest.fixture()
def dual_bound_alias_item(b_db):
    """建一個「有顯示別名 ＋ 明確標示雙邊」的項目：item='溫度A'（儲存鍵）／display_name='溫度'。
    名稱推測絕對猜不到它是雙邊，只有拿對儲存鍵查 item.is_dual_bound 才會知道。"""
    from sqlalchemy import func

    from models_b import Item

    max_iid = b_db.execute(select(func.max(Item.item_id))).scalar() or 0
    b_db.add(Item(item_id=max_iid + 1, item="溫度A", display_name="溫度", unit="°C",
                  is_active=True, is_dual_bound=True))
    b_db.flush()
    b_db.add(Spec(plant_no=TEST_PLANT_NO, item="溫度A", source_id=1, seqno=95))
    b_db.commit()
    yield


def test_dual_bound_resolved_by_storage_key_for_alias_item(client, b_db, dual_bound_alias_item):
    """★ 雙邊判定也要吃 item_key：帶儲存鍵 → 查得到 is_dual_bound=True → 雙邊門檻存得進去。"""
    row = _spec_row(client, TEST_PLANT_NO, "溫度")
    assert row["item_key"] == "溫度A"
    r = client.post("/spec/update", json={
        "plantno": TEST_PLANT_NO, "item": row["item"], "item_key": row["item_key"],
        "LAW": "20-35", "OOS": "20-35", "OOC": "22-33", "alert": "23-32", "source_id": 1,
    })
    assert r.status_code == 200, r.text

    b_db.expire_all()
    spec = b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "溫度A")
    ).scalar_one()
    assert float(spec.oos_low) == pytest.approx(20.0)
    assert float(spec.oos_high) == pytest.approx(35.0)


def test_dual_bound_lookup_misses_without_item_key(client, dual_bound_alias_item):
    """對照組：只送顯示名 '溫度' 查不到 item（顯示名不是資料鍵），退回名稱推測猜成單邊 → 422。
    這正是「往返有損」在雙邊判定上的另一個症狀，證明 item_key 是必要的而非可有可無。"""
    r = client.post("/spec/update", json={
        "plantno": TEST_PLANT_NO, "item": "溫度",
        "LAW": "20-35", "OOS": "20-35", "OOC": "22-33", "alert": "23-32", "source_id": 1,
    })
    assert r.status_code == 422, r.text
    assert any("必須為單邊規格" in d["msg"] for d in r.json()["detail"])


def test_spec_apply_uses_item_key_as_storage_item(client, b_db):
    """送簽路徑：payload 記的 item 必須是儲存鍵（核准套用時要靠它找到 spec 那一列）。"""
    row = _spec_row(client, TEST_PLANT_NO, "Cu")
    assert row["item_key"] == "Cu1"
    r = client.post("/spec/apply", json={
        "plantno": TEST_PLANT_NO, "item": row["item"], "item_key": row["item_key"], "ftype": "M",
        "LAW": "3.0", "OOS": "3.0", "OOC": "2.4", "alert": "1.9", "source_id": 1,
    })
    assert r.status_code == 200, r.text
    sa = b_db.get(SpecApply, r.json()["formid"])
    assert sa.item == "Cu1"

    # 核准 → 套用回 spec（若 payload 記成顯示名 'Cu'，這一步會炸「找不到規格值資料可修改」）
    r = client.post("/spec/sign", json={"formid": sa.id, "flowid": 0, "actionid": 1, "comment": ""})
    assert r.status_code == 200, r.text
    b_db.expire_all()
    spec = b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "Cu1")
    ).scalar_one()
    assert float(spec.ooc_high) == pytest.approx(2.4)


def test_spec_delete_accepts_item_key(client, b_db, dual_bound_alias_item):
    """刪除端點同樣吃 item_key（查詢字串），別名項目刪得掉。"""
    r = client.request(
        "DELETE", f"/spec/delete?plantno={TEST_PLANT_NO}&item=溫度&item_key=溫度A&remark=t",
    )
    assert r.status_code == 200, r.text
    b_db.expire_all()
    assert b_db.execute(
        select(Spec).where(Spec.plant_no == TEST_PLANT_NO, Spec.item == "溫度A")
    ).scalar_one_or_none() is None
