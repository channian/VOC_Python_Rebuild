"""
tests_integration/test_ui_router_b_validation.py — 真 PG 整合測試：
B 棧 4 頁寫入端點接上 Pydantic 驗證（docs/標準化與待調整清單.md D5）

涵蓋 routers_b/ui_router_b.py 的四組端點，每一個都有：
  - 合法輸入 → 200 且資料真的進 DB；
  - 非法輸入 → 422 且錯誤訊息是**繁體中文、指得出是哪個欄位**，且 DB 沒有被寫入。

前端顯示：四頁模板的 `extractErrorMsg()` 讀 `detail[].msg`（Pydantic 422 形狀），
本檔一併驗證 detail 是 list、msg 內含中文欄位名，確保訊息真的傳得到畫面上。
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from models_b import AclUserRole, Dept, Employee, MailList, MailLog, MailLogItem, Plant  # noqa: E402
from scripts.seed_test_data import (  # noqa: E402
    TEST_DEPT_NO, TEST_PLANT_ID, TEST_PLANT_NO, WATER_RPTTYPE,
)
from services_b import history_service as hs  # noqa: E402


@pytest.fixture()
def client(b_db):
    """TestClient；路由共用測試 session（才看得到測試內尚未 commit 的前置資料）。"""
    from database_b import get_b_db
    import main_b

    def _override_get_b_db():
        yield b_db

    main_b.app.dependency_overrides[get_b_db] = _override_get_b_db
    try:
        yield TestClient(main_b.app)
    finally:
        main_b.app.dependency_overrides.pop(get_b_db, None)


def _msgs(resp) -> str:
    """把 422 的 detail 串成一個字串（同時驗證形狀就是前端 extractErrorMsg() 吃的那種）。"""
    detail = resp.json()["detail"]
    assert isinstance(detail, list), f"detail 應為 list（前端 extractErrorMsg 依賴此形狀）：{detail!r}"
    return " | ".join(d["msg"] for d in detail)


# ══════════════════════════════════════════════════════════════════════════
# 派送名單 POST /maillist/add|update|delete
# ══════════════════════════════════════════════════════════════════════════

def _maillist_payload(**over) -> dict:
    payload = {
        "plantno": TEST_PLANT_NO, "rpttype": WATER_RPTTYPE, "empno": "E_VAL1",
        "empname": "驗證測試", "notesid": "val one", "mailtype": "TO",
        "mail": True, "signgrp": False,
    }
    payload.update(over)
    return payload


def test_maillist_add_valid(client, b_db):
    r = client.post("/maillist/add", json=_maillist_payload())
    assert r.status_code == 200, r.text
    row = b_db.execute(
        select(MailList).where(MailList.plant_no == TEST_PLANT_NO, MailList.emp_no == "E_VAL1")
    ).scalar_one()
    assert row.mail_type == "TO" and row.mail_on is True


@pytest.mark.parametrize("over,expect", [
    ({"plantno": "   "}, "廠區代碼不可為空白"),
    ({"rpttype": ""}, "報表類型不可為空白"),
    ({"empno": " "}, "工號不可為空白"),
    ({"mailtype": "BCC"}, "派送方式只能是 TO（正本）或 CC（副本）"),
    ({"plantno": "K" * 51}, "廠區代碼長度不可超過 50 個字元"),
])
def test_maillist_add_invalid_rejected(client, b_db, over, expect):
    r = client.post("/maillist/add", json=_maillist_payload(**over))
    assert r.status_code == 422, r.text
    assert expect in _msgs(r)
    # 沒有任何東西被寫進 DB
    assert b_db.execute(
        select(MailList).where(MailList.emp_no == "E_VAL1")
    ).scalar_one_or_none() is None


def test_maillist_update_and_delete_valid(client, b_db):
    assert client.post("/maillist/add", json=_maillist_payload()).status_code == 200

    r = client.post("/maillist/update", json=_maillist_payload(
        old_empno="E_VAL1", empno="E_VAL2", mailtype="CC", mail=False, signgrp=True))
    assert r.status_code == 200, r.text
    row = b_db.execute(
        select(MailList).where(MailList.plant_no == TEST_PLANT_NO, MailList.emp_no == "E_VAL2")
    ).scalar_one()
    assert row.mail_type == "CC" and row.mail_on is False and row.sign_grp is True

    r = client.post("/maillist/delete", json={
        "plantno": TEST_PLANT_NO, "rpttype": WATER_RPTTYPE, "empno": "E_VAL2"})
    assert r.status_code == 200, r.text
    assert b_db.execute(
        select(MailList).where(MailList.emp_no == "E_VAL2")
    ).scalar_one_or_none() is None


def test_maillist_update_blank_old_empno_rejected(client):
    r = client.post("/maillist/update", json=_maillist_payload(old_empno="  "))
    assert r.status_code == 422, r.text
    assert "原工號" in _msgs(r)


def test_maillist_delete_blank_field_rejected(client):
    r = client.post("/maillist/delete", json={"plantno": "", "rpttype": WATER_RPTTYPE, "empno": "E1"})
    assert r.status_code == 422, r.text
    assert "廠區代碼不可為空白" in _msgs(r)


# ══════════════════════════════════════════════════════════════════════════
# 部門權限 POST /dept/add|update|delete
# ══════════════════════════════════════════════════════════════════════════

_PLANT2_ID = 992
_PLANT2_NO = "TESTVAL2"
_DEPT2_NO = "TESTDEPT2"


@pytest.fixture()
def dept_fixture(b_db):
    """另建一個廠區（種子廠區已經有 TESTDEPT，會撞防重複）＋一個在職員工代表 TESTDEPT2 部門。"""
    if b_db.execute(select(Plant).where(Plant.plant_id == _PLANT2_ID)).scalar_one_or_none() is None:
        b_db.add(Plant(plant_id=_PLANT2_ID, plant_no=_PLANT2_NO, kind="normal", is_show=True, sort=997))
    b_db.add(Employee(emp_no="E_DEPT2", emp_name="部門二員工", notes_id="dept two",
                       dept_no=_DEPT2_NO, is_leave=False, synced_at=datetime.now(timezone.utc)))
    b_db.commit()
    yield


def test_dept_add_update_delete_valid(client, b_db, dept_fixture):
    r = client.post("/dept/add", json={"plantid": _PLANT2_ID, "deptno": TEST_DEPT_NO, "remark": "驗證測試"})
    assert r.status_code == 200, r.text
    assert b_db.execute(
        select(Dept).where(Dept.plant_id == _PLANT2_ID, Dept.dept_no == TEST_DEPT_NO)
    ).scalar_one_or_none() is not None

    r = client.post("/dept/update", json={
        "plantid": _PLANT2_ID, "old_deptno": TEST_DEPT_NO, "deptno": _DEPT2_NO})
    assert r.status_code == 200, r.text
    assert b_db.execute(
        select(Dept).where(Dept.plant_id == _PLANT2_ID, Dept.dept_no == _DEPT2_NO)
    ).scalar_one_or_none() is not None

    r = client.post("/dept/delete", json={"plantid": _PLANT2_ID, "deptno": _DEPT2_NO})
    assert r.status_code == 200, r.text
    assert b_db.execute(
        select(Dept).where(Dept.plant_id == _PLANT2_ID)
    ).scalar_one_or_none() is None


@pytest.mark.parametrize("payload,expect", [
    ({"plantid": 0, "deptno": TEST_DEPT_NO}, "請選擇廠區"),
    ({"plantid": TEST_PLANT_ID, "deptno": "   "}, "部門代碼不可為空"),
    ({"plantid": TEST_PLANT_ID, "deptno": "D" * 51}, "部門代碼長度不可超過 50 個字元"),
])
def test_dept_add_invalid_rejected(client, payload, expect):
    r = client.post("/dept/add", json=payload)
    assert r.status_code == 422, r.text
    assert expect in _msgs(r)


def test_dept_update_blank_old_deptno_rejected(client):
    r = client.post("/dept/update", json={
        "plantid": TEST_PLANT_ID, "old_deptno": "  ", "deptno": TEST_DEPT_NO})
    assert r.status_code == 422, r.text
    assert "原部門代碼" in _msgs(r)


def test_dept_delete_invalid_plantid_rejected(client, b_db):
    r = client.post("/dept/delete", json={"plantid": 0, "deptno": TEST_DEPT_NO})
    assert r.status_code == 422, r.text
    assert "請選擇廠區" in _msgs(r)
    # 原本那筆種子部門資料還在（沒被誤刪）
    assert b_db.execute(
        select(Dept).where(Dept.plant_id == TEST_PLANT_ID, Dept.dept_no == TEST_DEPT_NO)
    ).scalar_one_or_none() is not None


# ══════════════════════════════════════════════════════════════════════════
# ACL 隔離權限 POST /acl/create|update|delete
# ══════════════════════════════════════════════════════════════════════════

def test_acl_create_update_delete_valid(client, b_db):
    r = client.post("/acl/create", json={
        "plantno": TEST_PLANT_NO, "role_id": 3, "empno": "E_ACLV1", "stype": "2"})
    assert r.status_code == 200, r.text
    row = b_db.execute(
        select(AclUserRole).where(AclUserRole.emp_no == "E_ACLV1")
    ).scalar_one()
    assert row.stype == "水"

    r = client.post("/acl/update", json={
        "plantno": TEST_PLANT_NO, "role_id": 3, "old_empno": "E_ACLV1",
        "empno": "E_ACLV2", "stype": "1"})
    assert r.status_code == 200, r.text
    assert b_db.execute(
        select(AclUserRole).where(AclUserRole.emp_no == "E_ACLV2")
    ).scalar_one().stype == "空"

    r = client.post("/acl/delete", json={
        "plantno": TEST_PLANT_NO, "role_id": 3, "empno": "E_ACLV2"})
    assert r.status_code == 200, r.text
    assert b_db.execute(
        select(AclUserRole).where(AclUserRole.emp_no == "E_ACLV2")
    ).scalar_one_or_none() is None


@pytest.mark.parametrize("over,expect", [
    ({"role_id": 99}, "roleid 只能是"),
    ({"role_id": 12}, "roleid 只能是"),      # 12=隔離時間修改，本頁不開放管理
    ({"stype": "9"}, "stype 只能是"),
    ({"plantno": "  "}, "廠區不可為空"),
    ({"empno": ""}, "工號不可為空"),
    ({"empno": "E" * 51}, "工號長度不可超過 50 個字元"),
])
def test_acl_create_invalid_rejected(client, b_db, over, expect):
    payload = {"plantno": TEST_PLANT_NO, "role_id": 3, "empno": "E_ACLBAD", "stype": "3"}
    payload.update(over)
    r = client.post("/acl/create", json=payload)
    assert r.status_code == 422, r.text
    assert expect in _msgs(r)
    assert b_db.execute(
        select(AclUserRole).where(AclUserRole.emp_no == "E_ACLBAD")
    ).scalar_one_or_none() is None


def test_acl_delete_rejects_role_outside_whitelist(client):
    r = client.post("/acl/delete", json={"plantno": TEST_PLANT_NO, "role_id": 99, "empno": "E1"})
    assert r.status_code == 422, r.text
    assert "roleid 只能是" in _msgs(r)


def test_acl_delete_null_role_id_rejected(client):
    """前端角色下拉載入失敗時會送 role_id=null（模板已補前置擋，後端也要擋得住）。"""
    r = client.post("/acl/delete", json={"plantno": TEST_PLANT_NO, "role_id": None, "empno": "E1"})
    assert r.status_code == 422, r.text


# ══════════════════════════════════════════════════════════════════════════
# 異常回覆 POST /history/reply
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def reply_item_id(b_db) -> str:
    """建一封含單一項目的派報信，回傳該項目的 item_id（逐項目複合鍵字串）。"""
    log = MailLog(plant_no=TEST_PLANT_NO, sent_at=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
                  subject="驗證測試通知", body_note="驗證測試通知")
    b_db.add(log)
    b_db.flush()
    b_db.add(MailLogItem(mail_log_id=log.id, item="Cu", condition_code="OOS",
                          detail="|Cu|：OOS", escalation_stage=0, is_maintenance=False))
    b_db.commit()
    rows = hs.list_voclog(b_db, plant=TEST_PLANT_NO, sdate="2026/07/01", edate="2026/07/31", mt=True)
    return next(r for r in rows if r["logid"] == log.id)["item_id"]


def test_history_reply_valid(client, b_db, reply_item_id):
    r = client.post("/history/reply", json={"item_id": reply_item_id, "reason": "  已確認為採樣誤差  "})
    assert r.status_code == 200, r.text
    li = b_db.execute(select(MailLogItem).where(MailLogItem.item == "Cu")).scalars().all()
    assert any(x.reply_reason == "已確認為採樣誤差" for x in li)


def test_history_reply_blank_reason_rejected(client, b_db, reply_item_id):
    r = client.post("/history/reply", json={"item_id": reply_item_id, "reason": "   "})
    assert r.status_code == 422, r.text
    assert "原因說明不可為空白" in _msgs(r)
    # 空白回覆沒有被寫進去（改動前會寫入空字串並蓋掉回覆人/回覆時間）
    li = b_db.execute(select(MailLogItem).where(MailLogItem.item == "Cu")).scalars().all()
    assert all(not x.reply_reason and x.reply_empno is None for x in li)


def test_history_reply_blank_item_id_rejected(client):
    r = client.post("/history/reply", json={"item_id": "", "reason": "有填原因"})
    assert r.status_code == 422, r.text
    assert "回覆對象（item_id）不可為空白" in _msgs(r)


def test_history_reply_malformed_item_id_still_400(client):
    """格式錯誤（非空白）維持由 service 判斷 → 400，訊息說得出是 item_id 出問題。"""
    r = client.post("/history/reply", json={"item_id": "not-a-valid-key", "reason": "有填原因"})
    assert r.status_code == 400, r.text
    assert "item_id" in r.json()["detail"]
