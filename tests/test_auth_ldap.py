"""
test_auth_ldap.py — services_b/auth_ldap.py 純邏輯測試

原則：不連真的 DB、不連真的 LDAP。
    - AUTH_MOCK 分支：直接測。
    - AUTH_MOCK=False 分支：用假 ldap3 模組塞進 sys.modules（monkeypatch），
      驗證 bind 成功/失敗兩條路徑，以及 LDAP_USER_FORMAT 有沒有正確套用。
    - provision_user：用 sqlite in-memory + models_b 的 Employee/SignEmp
      兩張表（SQLAlchemy 泛型型別，sqlite 也能建表），驗證 upsert 行為。
"""
import itertools
import os
import sys
import types

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from config import settings
from models_b import BaseB, Employee, SignEmp
from services_b.auth_ldap import UserInfo, authenticate, provision_user

# sign_emp.emp_id 用 BigInteger + Identity()（PG/MSSQL 皆懂），但 sqlite 方言不認得
# Identity()，只在測試這裡補一個自增序號，讓 in-memory sqlite 也能跑 —— 正式環境
# (PG/MSSQL) 不受影響，這段只掛在測試檔案本身、不改 models_b.py。
_sign_emp_id_seq = itertools.count(1)


@event.listens_for(SignEmp, "before_insert")
def _assign_sign_emp_id_for_sqlite(mapper, connection, target):
    if target.emp_id is None:
        target.emp_id = next(_sign_emp_id_seq)


# ------------------------------------------------------------------
# AUTH_MOCK=True
# ------------------------------------------------------------------

def test_mock_login_success_with_non_empty_credentials():
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = True
    try:
        result = authenticate("E001", "任意密碼")
        assert result == UserInfo(empno="E001", name="E001")
    finally:
        settings.AUTH_MOCK = original


def test_mock_login_rejects_empty_username():
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = True
    try:
        assert authenticate("", "任意密碼") is None
    finally:
        settings.AUTH_MOCK = original


def test_mock_login_rejects_empty_password():
    original = settings.AUTH_MOCK
    settings.AUTH_MOCK = True
    try:
        assert authenticate("E001", "") is None
    finally:
        settings.AUTH_MOCK = original


# ------------------------------------------------------------------
# AUTH_MOCK=False（假 ldap3 模組）
# ------------------------------------------------------------------

class _FakeEntry:
    """模擬 ldap3 的 search 結果 entry：支援 `"displayName" in entry` 與屬性存取。"""

    def __init__(self, **kwargs):
        self._data = kwargs

    def __contains__(self, key):
        return bool(self._data.get(key))

    def __getattr__(self, key):
        return self._data.get(key, "")


def _install_fake_ldap3(monkeypatch, *, bind_ok=True, entries=None, search_should_fail=False,
                         captured_bind_users=None):
    """在 sys.modules 塞一個假 ldap3 模組，回傳給測試用來斷言呼叫細節。"""
    fake_module = types.ModuleType("ldap3")

    class FakeServer:
        def __init__(self, *args, **kwargs):
            pass

    class FakeConnection:
        def __init__(self, server, user=None, password=None, auto_bind=False):
            self.user = user
            self.password = password
            self.entries = []
            if captured_bind_users is not None:
                captured_bind_users.append(user)
            if auto_bind and not bind_ok:
                raise Exception("模擬 bind 失敗（帳密錯誤）")

        def search(self, base, filt, attributes=None):
            if search_should_fail:
                raise Exception("模擬 search 失敗")
            self.entries = entries or []

        def unbind(self):
            pass

    fake_module.Server = FakeServer
    fake_module.Connection = FakeConnection
    fake_module.ALL = "ALL"

    monkeypatch.setitem(sys.modules, "ldap3", fake_module)
    return fake_module


def test_ldap_bind_success_fetches_attributes(monkeypatch):
    original_mock = settings.AUTH_MOCK
    original_base_dn = settings.LDAP_BASE_DN
    original_user_format = settings.LDAP_USER_FORMAT
    settings.AUTH_MOCK = False
    settings.LDAP_BASE_DN = "DC=aseglobal,DC=com"
    settings.LDAP_USER_FORMAT = "{username}@aseglobal.com"
    try:
        _install_fake_ldap3(
            monkeypatch,
            bind_ok=True,
            entries=[_FakeEntry(displayName="王小明", department="D01", mail="e001@aseglobal.com")],
        )
        result = authenticate("E001", "correct-password")
        assert result == UserInfo(empno="E001", name="王小明", dept_no="D01", email="e001@aseglobal.com")
    finally:
        settings.AUTH_MOCK = original_mock
        settings.LDAP_BASE_DN = original_base_dn
        settings.LDAP_USER_FORMAT = original_user_format


def test_ldap_bind_failure_returns_none(monkeypatch):
    original_mock = settings.AUTH_MOCK
    settings.AUTH_MOCK = False
    try:
        _install_fake_ldap3(monkeypatch, bind_ok=False)
        assert authenticate("E001", "wrong-password") is None
    finally:
        settings.AUTH_MOCK = original_mock


def test_ldap_user_format_applied_to_bind(monkeypatch):
    original_mock = settings.AUTH_MOCK
    original_user_format = settings.LDAP_USER_FORMAT
    settings.AUTH_MOCK = False
    settings.LDAP_USER_FORMAT = "{username}@custom-domain.com"
    try:
        captured = []
        _install_fake_ldap3(monkeypatch, bind_ok=True, captured_bind_users=captured)
        authenticate("E001", "pw")
        assert captured == ["E001@custom-domain.com"]
    finally:
        settings.AUTH_MOCK = original_mock
        settings.LDAP_USER_FORMAT = original_user_format


def test_ldap_search_failure_does_not_block_login(monkeypatch):
    """bind 已經證明帳密正確，search 失敗不該擋登入，屬性給空值即可。"""
    original_mock = settings.AUTH_MOCK
    original_base_dn = settings.LDAP_BASE_DN
    settings.AUTH_MOCK = False
    settings.LDAP_BASE_DN = "DC=aseglobal,DC=com"
    try:
        _install_fake_ldap3(monkeypatch, bind_ok=True, search_should_fail=True)
        result = authenticate("E001", "pw")
        assert result == UserInfo(empno="E001", name="E001", dept_no="", email="")
    finally:
        settings.AUTH_MOCK = original_mock
        settings.LDAP_BASE_DN = original_base_dn


def test_ldap_skips_search_when_base_dn_empty(monkeypatch):
    """LDAP_BASE_DN 空字串＝不做屬性 search，只做 bind。"""
    original_mock = settings.AUTH_MOCK
    original_base_dn = settings.LDAP_BASE_DN
    settings.AUTH_MOCK = False
    settings.LDAP_BASE_DN = ""
    try:
        _install_fake_ldap3(monkeypatch, bind_ok=True, entries=[_FakeEntry(displayName="不該被讀到")])
        result = authenticate("E001", "pw")
        assert result == UserInfo(empno="E001", name="E001", dept_no="", email="")
    finally:
        settings.AUTH_MOCK = original_mock
        settings.LDAP_BASE_DN = original_base_dn


# ------------------------------------------------------------------
# provision_user（sqlite in-memory）
# ------------------------------------------------------------------

def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    BaseB.metadata.create_all(engine, tables=[Employee.__table__, SignEmp.__table__])
    return Session(engine)


def test_provision_user_creates_new_employee_and_sign_emp():
    db = _make_db()
    info = UserInfo(empno="E100", name="測試員", dept_no="D01", email="test_user@aseglobal.com")

    result = provision_user(db, info)
    db.commit()

    assert result.name == "測試員"
    assert result.dept_no == "D01"

    emp = db.execute(select(Employee).where(Employee.emp_no == "E100")).scalar_one()
    assert emp.emp_name == "測試員"
    assert emp.dept_no == "D01"
    assert emp.notes_id == "test user"  # email 反推：去網域、底線還原空白
    assert emp.is_leave is False

    sign_emp = db.execute(select(SignEmp).where(SignEmp.emp_no == "E100")).scalar_one()
    assert sign_emp.emp_name == "測試員"
    assert sign_emp.email == "test_user@aseglobal.com"
    assert sign_emp.dep_no == "D01"


def test_provision_user_upsert_does_not_duplicate_rows():
    db = _make_db()
    info = UserInfo(empno="E100", name="測試員", dept_no="D01", email="test_user@aseglobal.com")

    provision_user(db, info)
    db.commit()
    provision_user(db, info)
    db.commit()

    employees = db.execute(select(Employee)).scalars().all()
    sign_emps = db.execute(select(SignEmp)).scalars().all()
    assert len(employees) == 1
    assert len(sign_emps) == 1


def test_provision_user_name_fallback_prefers_existing_real_name():
    """AUTH_MOCK 補救：表內已有真名時，登入帶來的 username 佔位不該覆蓋。"""
    db = _make_db()
    db.add(Employee(emp_no="E200", emp_name="王小明", dept_no="D02", is_leave=False))
    db.commit()

    mock_info = UserInfo(empno="E200", name="E200")  # AUTH_MOCK 時 name 只是 username
    result = provision_user(db, mock_info)
    db.commit()

    assert result.name == "王小明"
    emp = db.execute(select(Employee).where(Employee.emp_no == "E200")).scalar_one()
    assert emp.emp_name == "王小明"


def test_provision_user_fills_empty_name_when_employee_has_none():
    db = _make_db()
    db.add(Employee(emp_no="E250", emp_name=None, is_leave=False))
    db.commit()

    result = provision_user(db, UserInfo(empno="E250", name="新姓名"))
    db.commit()

    assert result.name == "新姓名"
    emp = db.execute(select(Employee).where(Employee.emp_no == "E250")).scalar_one()
    assert emp.emp_name == "新姓名"


def test_provision_user_keeps_existing_notes_id_when_not_derivable():
    """email 非 @aseglobal.com 網域（或空白）時無法反推，應保留既有 notes_id 不覆蓋。"""
    db = _make_db()
    db.add(Employee(emp_no="E300", emp_name="舊姓名", notes_id="舊 筆記", dept_no="D03", is_leave=False))
    db.commit()

    provision_user(db, UserInfo(empno="E300", name="舊姓名", dept_no="", email=""))
    db.commit()

    emp = db.execute(select(Employee).where(Employee.emp_no == "E300")).scalar_one()
    assert emp.notes_id == "舊 筆記"


def test_provision_user_reactivates_is_leave_on_login():
    """能登入代表在職，重新登入應把 is_leave 重置為 False。"""
    db = _make_db()
    db.add(Employee(emp_no="E400", emp_name="離職員工", is_leave=True))
    db.commit()

    provision_user(db, UserInfo(empno="E400", name="離職員工"))
    db.commit()

    emp = db.execute(select(Employee).where(Employee.emp_no == "E400")).scalar_one()
    assert emp.is_leave is False
