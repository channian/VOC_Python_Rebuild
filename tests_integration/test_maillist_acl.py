"""
tests_integration/test_maillist_acl.py — 真 PG 整合測試：派送名單 CRUD + 收件人 + 暫停旗標 + ACL

涵蓋 services_b/maillist_service.py 與 services_b/acl_service.py。
使用 tests_integration/conftest.py 的 `b_db` fixture（每個測試前先 seed() 重灌基準資料，
沒有可連線的 PostgreSQL 時整個目錄會被自動 skip，見 conftest.py 說明）。
"""

import pytest
from sqlalchemy import select

from config import settings
from models_b import MailList, Plant
from scripts.seed_test_data import TEST_PLANT_NO, SIGNER_EMPNO, APPLICANT_EMPNO
from services_b import maillist_service as ml
from services_b import acl_service as acl


# ══════════════════════════════════════════════════════════════════════════
# maillist_service：CRUD
# ══════════════════════════════════════════════════════════════════════════

def test_add_list_update_delete_maillist(b_db):
    ml.add_maillist(
        b_db, current_user_empno="admin", plant_no=TEST_PLANT_NO, rpttype="水OOS",
        emp_no="E9001", emp_name="王小明", notes_id="wang_xiaoming@aseglobal.com",
        mail_type="TO", mail_on=True, sign_grp=False,
    )
    rows = ml.list_maillist(b_db, plant_no=TEST_PLANT_NO, rpttype="水OOS")
    assert len(rows) == 1
    assert rows[0]["empno"] == "E9001"
    # normalize_notesid 應該把 @aseglobal.com 去掉、底線換空格
    assert rows[0]["notesid"] == "wang xiaoming"

    # 防重複
    with pytest.raises(ValueError):
        ml.add_maillist(b_db, current_user_empno="admin", plant_no=TEST_PLANT_NO,
                         rpttype="水OOS", emp_no="E9001")

    # 修改（改工號）
    ml.update_maillist(
        b_db, current_user_empno="admin", plant_no=TEST_PLANT_NO, rpttype="水OOS",
        old_emp_no="E9001", emp_no="E9002", emp_name="李小華", notes_id="li xiaohua",
        mail_type="CC", mail_on=False, sign_grp=True,
    )
    rows = ml.list_maillist(b_db, plant_no=TEST_PLANT_NO, rpttype="水OOS")
    assert len(rows) == 1
    assert rows[0]["empno"] == "E9002"
    assert rows[0]["mailtype"] == "CC"
    assert rows[0]["mail"] is False
    assert rows[0]["signgrp"] is True

    # 刪除
    ml.delete_maillist(b_db, current_user_empno="admin", plant_no=TEST_PLANT_NO,
                        rpttype="水OOS", emp_no="E9002")
    assert ml.list_maillist(b_db, plant_no=TEST_PLANT_NO, rpttype="水OOS") == []

    with pytest.raises(ValueError):
        ml.delete_maillist(b_db, current_user_empno="admin", plant_no=TEST_PLANT_NO,
                            rpttype="水OOS", emp_no="E9002")


def test_get_plant_and_rpttype_list(b_db):
    plants = ml.get_plant_list(b_db)
    assert TEST_PLANT_NO in plants
    rpttypes = ml.get_rpttype_list(b_db)
    assert "水質異常" in rpttypes


def test_lookup_employee_manual_and_dept(b_db):
    assert ml.lookup_employee(b_db, "群組A")["manual"] is True
    result = ml.lookup_employee(b_db, SIGNER_EMPNO)
    # normalize_notesid（零修改重用）會把底線換成空格，種子資料 notes_id='TEST_PLACEHOLDER'
    # 正規化後應為 'TEST PLACEHOLDER'（與 A 版 services/maillist_service.py 行為一致）。
    assert result["notesid"] == "TEST PLACEHOLDER"
    assert ml.lookup_employee(b_db, "NOSUCHEMP")["empname"] == ""


# ══════════════════════════════════════════════════════════════════════════
# maillist_service：收件人（TO 綁廠 / CC 加虛擬廠區）+ 全域暫停旗標
# ══════════════════════════════════════════════════════════════════════════

def _seed_virtual_group_plant(db) -> str:
    """種子資料未提供虛擬廠區，測試內自建一個 kind='virtual_group' 的廠區（任務提示要求）。"""
    virtual_plant_no = "V-GMO"
    exists = db.execute(select(Plant).where(Plant.plant_no == virtual_plant_no)).scalar_one_or_none()
    if not exists:
        db.add(Plant(plant_id=991, plant_no=virtual_plant_no, kind="virtual_group", is_show=False, sort=998))
        db.flush()
    return virtual_plant_no


def test_get_mail_recipients_to_and_cc_with_virtual_group(b_db):
    virtual_plant_no = _seed_virtual_group_plant(b_db)

    # TO：只綁該廠
    b_db.add(MailList(plant_no=TEST_PLANT_NO, rpttype="水OOS", emp_no="E_TO",
                       emp_name="TO收件人", notes_id="to_person", mail_type="TO",
                       mail_on=True, sign_grp=False))
    # CC：該廠一筆 + 虛擬廠區一筆
    b_db.add(MailList(plant_no=TEST_PLANT_NO, rpttype="水OOS", emp_no="E_CC",
                       emp_name="CC收件人", notes_id="cc_person", mail_type="CC",
                       mail_on=True, sign_grp=False))
    b_db.add(MailList(plant_no=virtual_plant_no, rpttype="水OOS", emp_no="E_CC_V",
                       emp_name="虛擬廠區CC", notes_id="cc_virtual", mail_type="CC",
                       mail_on=True, sign_grp=False))
    # 另一廠區的 TO 不應該出現在本廠查詢結果內
    b_db.add(MailList(plant_no=virtual_plant_no, rpttype="水OOS", emp_no="E_TO_OTHER",
                       emp_name="別廠TO", notes_id="other_to", mail_type="TO",
                       mail_on=True, sign_grp=False))
    b_db.commit()

    to_list = ml.get_mail_recipients(b_db, "水OOS", TEST_PLANT_NO, "TO")
    assert to_list == ["to_person@aseglobal.com"]

    cc_list = ml.get_mail_recipients(b_db, "水OOS", TEST_PLANT_NO, "CC")
    assert set(cc_list) == {"cc_person@aseglobal.com", "cc_virtual@aseglobal.com"}


def test_mail_paused_blocks_all_recipients(b_db):
    b_db.add(MailList(plant_no=TEST_PLANT_NO, rpttype="水OOS", emp_no="E_TO2",
                       emp_name="收件人", notes_id="someone", mail_type="TO",
                       mail_on=True, sign_grp=False))
    b_db.commit()

    assert ml.is_mail_paused(b_db) is False
    assert ml.get_mail_recipients(b_db, "水OOS", TEST_PLANT_NO, "TO") == ["someone@aseglobal.com"]

    ml.set_mail_paused(b_db, True)
    assert ml.is_mail_paused(b_db) is True
    assert ml.get_mail_recipients(b_db, "水OOS", TEST_PLANT_NO, "TO") == []
    assert ml.get_mail_recipients(b_db, "水OOS", TEST_PLANT_NO, "CC") == []

    ml.set_mail_paused(b_db, False)
    assert ml.get_mail_recipients(b_db, "水OOS", TEST_PLANT_NO, "TO") == ["someone@aseglobal.com"]


# ══════════════════════════════════════════════════════════════════════════
# acl_service：CRUD + check_permission（ACL_ENFORCE 行為與 A 版一致）
# ══════════════════════════════════════════════════════════════════════════

def test_acl_user_crud(b_db):
    acl.create_acl_user(b_db, current_user_empno="admin", plantno=TEST_PLANT_NO,
                         role_id=3, empno="E_ACL1", stype="2")
    rows = acl.list_acl_users(b_db, plantno=TEST_PLANT_NO)
    assert any(r["empno"] == "E_ACL1" and r["stype"] == "水" for r in rows)

    with pytest.raises(ValueError):
        acl.create_acl_user(b_db, current_user_empno="admin", plantno=TEST_PLANT_NO,
                             role_id=3, empno="E_ACL1", stype="2")

    acl.update_acl_user(b_db, current_user_empno="admin", plantno=TEST_PLANT_NO, role_id=3,
                         old_empno="E_ACL1", empno="E_ACL2", stype="1", old_stype="水")
    rows = acl.list_acl_users(b_db, plantno=TEST_PLANT_NO)
    assert any(r["empno"] == "E_ACL2" and r["stype"] == "空" for r in rows)

    acl.delete_acl_user(b_db, current_user_empno="admin", plantno=TEST_PLANT_NO, role_id=3, empno="E_ACL2")
    assert not any(r["empno"] == "E_ACL2" for r in acl.list_acl_users(b_db, plantno=TEST_PLANT_NO))


def test_check_permission_acl_enforce_behavior(b_db, monkeypatch):
    """
    種子資料裡 APPLICANT_EMPNO/SIGNER_EMPNO 只有 role_id=3（隔離維護），對 rights_id=7（隔離查詢）
    沒有登記 → 權限不足。ACL_ENFORCE=False 應該放行（僅記 log），True 應該擋下。
    """
    monkeypatch.setattr(settings, "ACL_ENFORCE", False)
    assert acl.check_permission(b_db, empno=APPLICANT_EMPNO, rightsid=7, action="query") is True

    monkeypatch.setattr(settings, "ACL_ENFORCE", True)
    assert acl.check_permission(b_db, empno=APPLICANT_EMPNO, rightsid=7, action="query") is False

    # role_id=3 本身有登記，查 rightsid=3 的權限應該通過（種子 seed_test_data._seed_catalog
    # 給 role_id=3 對 rights_id=3 allow_rights=1，has_right(1,'query')=True）
    assert acl.check_permission(b_db, empno=APPLICANT_EMPNO, rightsid=3, action="query") is True


def test_has_right_pure_function_reused():
    """acl_service.has_right 是從 services.acl_service 零修改重用，這裡快速驗證位元判斷正確。"""
    assert acl.has_right(1, "query") is True
    assert acl.has_right(1, "modify") is False
    assert acl.has_right(31, "delete") is True
    with pytest.raises(ValueError):
        acl.has_right(1, "not_a_real_action")
