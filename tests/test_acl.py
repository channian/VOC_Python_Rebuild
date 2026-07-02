"""
test_acl.py — ACL 權限系統純邏輯測試

只 import services/schemas/config，不 import routers 或 database（環境無 ODBC 連不上真實 DB）。
DB 相關函式（check_permission/is_admin/get_user_plants）用 FakeDB 模擬 db.execute() 回傳值，
不需要真實連線即可驗證邏輯。
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from config import settings
from schemas.acl_schema import AclUserCreate, AclUserUpdate, AclUserBase
from services.acl_service import (
    has_right, stype_code_to_text, stype_text_to_code,
    check_permission, is_admin, get_user_plants,
)


# ── FakeDB：模擬 sqlalchemy Session.execute() 的最小行為 ──────────────────────

class _FakeResult:
    """模擬 sqlalchemy 的 CursorResult：支援 .scalar() 與 .mappings().all()/.first()。"""

    def __init__(self, scalar_value=None, mapping_rows=None):
        self._scalar_value = scalar_value
        self._mapping_rows = mapping_rows or []

    def scalar(self):
        return self._scalar_value

    def mappings(self):
        return self

    def all(self):
        return self._mapping_rows

    def first(self):
        return self._mapping_rows[0] if self._mapping_rows else None


class FakeDB:
    """依序回傳預先設定好的查詢結果，模擬 acl_service 內多次 db.execute() 呼叫。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((str(sql), params))
        if not self.responses:
            raise AssertionError("FakeDB: 沒有預先設定的回應可用，呼叫次數超出預期")
        return self.responses.pop(0)


class BrokenDB:
    """模擬 DB 連線失敗（無 ODBC driver 時的真實情境）。"""

    def execute(self, *args, **kwargs):
        raise RuntimeError("模擬 DB 連線失敗（無 ODBC driver）")


# ── has_right：5 種 action × 常見 allowrights 組合 ────────────────────────────

@pytest.mark.parametrize("action,bit", [
    ("query", 1), ("modify", 2), ("add", 4), ("delete", 8), ("execute", 16),
])
def test_has_right_single_bit_matches(action, bit):
    """單一位元剛好等於該 action 的位元時應為 True。"""
    assert has_right(bit, action) is True


@pytest.mark.parametrize("action,bit", [
    ("query", 1), ("modify", 2), ("add", 4), ("delete", 8), ("execute", 16),
])
def test_has_right_single_bit_others_denied(action, bit):
    """單一位元只允許自己對應的 action，其餘 4 種都應為 False。"""
    for other_action in ("query", "modify", "add", "delete", "execute"):
        if other_action == action:
            continue
        assert has_right(bit, other_action) is False


@pytest.mark.parametrize("action", ["query", "modify", "add", "delete", "execute"])
def test_has_right_allowrights_31_grants_all(action):
    """31 = 1+2+4+8+16，全部權限都應通過。"""
    assert has_right(31, action) is True


@pytest.mark.parametrize("action", ["query", "modify", "add", "delete", "execute"])
def test_has_right_allowrights_zero_denies_all(action):
    """allowrights=0 應全部拒絕。"""
    assert has_right(0, action) is False


def test_has_right_allowrights_none_treated_as_zero():
    """DB NULL（None）應視為 0，全部拒絕。"""
    for action in ("query", "modify", "add", "delete", "execute"):
        assert has_right(None, action) is False


def test_has_right_partial_combo():
    """allowrights=3（查詢1+修改2）：只有查詢/修改通過，新增/刪除/執行不通過。"""
    assert has_right(3, "query") is True
    assert has_right(3, "modify") is True
    assert has_right(3, "add") is False
    assert has_right(3, "delete") is False
    assert has_right(3, "execute") is False


def test_has_right_invalid_action_raises():
    with pytest.raises(ValueError):
        has_right(31, "not_a_real_action")


# ── stype 代碼 <-> DB 文字 轉換 ────────────────────────────────────────────

def test_stype_code_to_text():
    assert stype_code_to_text("1") == "空"
    assert stype_code_to_text("2") == "水"
    assert stype_code_to_text("3") == "ALL"
    assert stype_code_to_text("不明代碼") == "ALL"  # 未知代碼比照舊版行為退回 ALL


def test_stype_text_to_code_roundtrip():
    assert stype_text_to_code("空") == "1"
    assert stype_text_to_code("水") == "2"
    assert stype_text_to_code("ALL") == "3"
    for code in ("1", "2", "3"):
        assert stype_text_to_code(stype_code_to_text(code)) == code


# ── is_admin ────────────────────────────────────────────────────────────────

def test_is_admin_true_when_rightsid1_registered():
    db = FakeDB([_FakeResult(scalar_value=1)])
    assert is_admin(db, "admin") is True


def test_is_admin_false_when_no_registration():
    db = FakeDB([_FakeResult(scalar_value=0)])
    assert is_admin(db, "E001") is False


def test_is_admin_query_failure_treated_as_non_admin():
    """DB 查詢失敗（無 ODBC driver）時，不能誤判為管理員，應回 False。"""
    assert is_admin(BrokenDB(), "E001") is False


# ── get_user_plants：plantno='ALL' 語意 ───────────────────────────────────────

def test_get_user_plants_all_short_circuits():
    """只要清單中出現 'ALL'，就代表全廠可見，回傳特殊值 ['ALL'] 而非展開實際廠區清單。"""
    db = FakeDB([_FakeResult(mapping_rows=[
        {"plantno": "K1"}, {"plantno": "ALL"}, {"plantno": "K9"},
    ])])
    assert get_user_plants(db, "E001") == ["ALL"]


def test_get_user_plants_specific_list():
    db = FakeDB([_FakeResult(mapping_rows=[{"plantno": "K1"}, {"plantno": "K9"}])])
    assert set(get_user_plants(db, "E001")) == {"K1", "K9"}


def test_get_user_plants_query_failure_returns_empty():
    """DB 查詢失敗應回空清單（視為「無可視廠區」，而非放行全部）。"""
    assert get_user_plants(BrokenDB(), "E001") == []


# ── check_permission：ACL_ENFORCE 開關行為 ────────────────────────────────────

def test_check_permission_admin_always_allowed():
    """系統管理員（rightsid=1 有登記）無條件放行，即使 ACL_ENFORCE=True。"""
    original = settings.ACL_ENFORCE
    settings.ACL_ENFORCE = True
    try:
        db = FakeDB([_FakeResult(scalar_value=1)])  # is_admin -> True
        assert check_permission(db, "admin", rightsid=99, action="delete") is True
    finally:
        settings.ACL_ENFORCE = original


def test_check_permission_enforce_false_allows_even_without_rights():
    """ACL_ENFORCE=False（預設）：權限不足只記 log，仍然放行。"""
    original = settings.ACL_ENFORCE
    settings.ACL_ENFORCE = False
    try:
        db = FakeDB([
            _FakeResult(scalar_value=0),   # is_admin -> False
            _FakeResult(mapping_rows=[]),  # 無任何符合的角色權限
        ])
        assert check_permission(db, "E001", rightsid=3, action="modify") is True
    finally:
        settings.ACL_ENFORCE = original


def test_check_permission_enforce_true_blocks_without_rights():
    """ACL_ENFORCE=True：權限不足直接擋下。"""
    original = settings.ACL_ENFORCE
    settings.ACL_ENFORCE = True
    try:
        db = FakeDB([
            _FakeResult(scalar_value=0),
            _FakeResult(mapping_rows=[]),
        ])
        assert check_permission(db, "E001", rightsid=3, action="modify") is False
    finally:
        settings.ACL_ENFORCE = original


def test_check_permission_enforce_true_allows_when_right_matches():
    """ACL_ENFORCE=True 但確實擁有對應位元權限時，仍應放行。"""
    original = settings.ACL_ENFORCE
    settings.ACL_ENFORCE = True
    try:
        db = FakeDB([
            _FakeResult(scalar_value=0),                       # 非系統管理員
            _FakeResult(mapping_rows=[{"allowrights": 3}]),    # 查詢+修改
        ])
        assert check_permission(db, "E001", rightsid=3, action="modify") is True
    finally:
        settings.ACL_ENFORCE = original


def test_check_permission_db_failure_respects_enforce_flag():
    """DB 查詢例外時，視為未取得授權，仍交由 ACL_ENFORCE 決定要不要擋。"""
    original = settings.ACL_ENFORCE
    try:
        settings.ACL_ENFORCE = False
        assert check_permission(BrokenDB(), "E001", rightsid=3, action="query") is True
        settings.ACL_ENFORCE = True
        assert check_permission(BrokenDB(), "E001", rightsid=3, action="query") is False
    finally:
        settings.ACL_ENFORCE = original


# ── schema 驗證 ───────────────────────────────────────────────────────────────

def test_acl_user_create_valid():
    data = AclUserCreate(role_id=3, plantno="K1", empno="E001", stype="1")
    assert data.plantno == "K1"
    assert data.stype == "1"


@pytest.mark.parametrize("bad_role_id", [1, 2, 4, 5, 6, 8, 9, 10, 11, 12])
def test_acl_user_create_rejects_role_outside_editacluser_scope(bad_role_id):
    """EditAclUser 頁面舊版只開放管理 roleid 3(隔離維護)/7(隔離查詢)。"""
    with pytest.raises(Exception):
        AclUserCreate(role_id=bad_role_id, plantno="K1", empno="E001", stype="1")


@pytest.mark.parametrize("good_role_id", [3, 7])
def test_acl_user_create_accepts_allowed_roles(good_role_id):
    data = AclUserCreate(role_id=good_role_id, plantno="K1", empno="E001", stype="3")
    assert data.role_id == good_role_id


def test_acl_user_create_invalid_stype():
    with pytest.raises(Exception):
        AclUserCreate(role_id=3, plantno="K1", empno="E001", stype="9")


def test_acl_user_create_empty_plantno_rejected():
    with pytest.raises(Exception):
        AclUserCreate(role_id=3, plantno="  ", empno="E001", stype="1")


def test_acl_user_update_requires_old_empno():
    with pytest.raises(Exception):
        AclUserUpdate(role_id=3, plantno="K1", empno="E002", stype="1",
                      old_empno="", old_stype="空")


def test_acl_user_update_valid():
    data = AclUserUpdate(role_id=7, plantno="ALL", empno="E002", stype="3",
                         old_empno="E001", old_stype="空")
    assert data.old_empno == "E001"
    assert data.plantno == "ALL"


def test_acl_user_base_delete_payload_valid():
    data = AclUserBase(role_id=3, plantno="K1", empno="E001", stype="2")
    assert data.empno == "E001"
