"""
services_b/auth_ldap.py — LDAP/AD 驗證服務層（Schema B，Phase 3 AD 串接）

依 docs/ad_integration_guide.md 的標準四部曲實作：
    1. 使用者提供帳密
    2. 對公司 AD 做 Connection + bind（bind 成功＝密碼正確）
    3. bind 成功後 search 取得姓名/部門/信箱等屬性
    4. 回傳使用者資訊給呼叫端（呼叫端負責核發 session / JWT，不在本檔範圍）

AUTH_MOCK 語意比照 services/auth_service.py（A 棧既有版本，不動它），這裡是 B 棧的
對應實作：
    - AUTH_MOCK=True （開發用）：完全不連真的 LDAP，帳密皆非空即視為登入成功，
      姓名先用 username 頂著，真實姓名由 provision_user() 從 employee 表補回。
    - AUTH_MOCK=False（正式環境）：真的對 settings.LDAP_SERVER 做 bind 驗證。

ldap3 是選用相依套件（requirements.txt 已加入 ldap3==2.9.1），但沙盒/測試環境不一定裝了它，
所以本檔案在「模組層級」完全不 import ldap3，只在 authenticate() 真的要連線的分支內延遲
import——這樣 AUTH_MOCK=True（多數情境）就算環境沒裝 ldap3，import 本模組也不會炸掉。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from models_b import Employee, SignEmp

logger = logging.getLogger(__name__)

# notesid_to_email 的正向規則寫死 @aseglobal.com（見 services/maillist_service.notesid_to_email：
# notesid.replace(' ', '_') + '@aseglobal.com'）。這裡做反推：去尾網域、底線還原空白。
# 與 migration/context.py 的 Person.notes_id 屬性同一套規則（那裡是搬遷用途，這裡是登入建檔用途，
# 各自獨立實作避免不必要的跨模組耦合）。
EMAIL_DOMAIN = "@aseglobal.com"


@dataclass
class UserInfo:
    """LDAP／Mock 驗證成功後的使用者資訊。"""
    empno: str
    name: str
    dept_no: str = ""
    email: str = ""


def _derive_notes_id(email: str) -> str:
    """email 反推 notes_id：非 @aseglobal.com 網域視為無法反推，回傳空字串
    （呼叫端遇到空字串時應保留 employee 表既有的 notes_id，不覆蓋）。
    """
    local = (email or "").strip()
    if not local or not local.lower().endswith(EMAIL_DOMAIN):
        return ""
    local = local[: -len(EMAIL_DOMAIN)]
    return local.replace("_", " ")


def authenticate(username: str, password: str) -> Optional[UserInfo]:
    """驗證帳密，成功回傳 UserInfo，失敗回傳 None。

    AUTH_MOCK=True：帳密皆非空即通過（密碼不驗）。
    AUTH_MOCK=False：ldap3 對 settings.LDAP_SERVER 做 bind
        （user=settings.LDAP_USER_FORMAT.format(username=username)）；
        bind 失敗回 None。bind 成功後若設定了 settings.LDAP_BASE_DN，
        search 取 displayName/department/mail；search 失敗不擋登入
        （屬性給空值，記 warning）。
    """
    if not username or not password:
        return None

    if settings.AUTH_MOCK:
        # 開發用 Mock：不連真的 LDAP。姓名先用 username 頂著，真名由
        # provision_user() 從 employee 表補（表內已有姓名的話）。
        return UserInfo(empno=username, name=username)

    # --- 正式模式：真的連 LDAP ---
    import ldap3  # 延遲 import：沙盒/測試環境沒裝 ldap3 也不能讓模組 import 掛掉

    bind_user = settings.LDAP_USER_FORMAT.format(username=username)
    server = ldap3.Server(settings.LDAP_SERVER)
    try:
        conn = ldap3.Connection(server, user=bind_user, password=password, auto_bind=True)
    except Exception as exc:
        logger.warning("LDAP bind 失敗（帳號 %s）：%s", username, exc)
        return None

    name = username
    dept_no = ""
    email = ""
    if settings.LDAP_BASE_DN:
        try:
            conn.search(
                settings.LDAP_BASE_DN,
                f"(sAMAccountName={username})",
                attributes=["displayName", "department", "mail"],
            )
            if conn.entries:
                entry = conn.entries[0]
                if "displayName" in entry:
                    name = str(entry.displayName)
                if "department" in entry:
                    dept_no = str(entry.department)
                if "mail" in entry:
                    email = str(entry.mail)
        except Exception as exc:
            # search 失敗不擋登入（bind 已經證明帳密正確），屬性給空值即可。
            logger.warning("LDAP search 失敗（帳號 %s），屬性給空值：%s", username, exc)

    try:
        conn.unbind()
    except Exception:
        pass

    return UserInfo(empno=username, name=name, dept_no=dept_no, email=email)


def provision_user(db: Session, info: UserInfo) -> UserInfo:
    """首次登入自動建檔／既有工號更新快取。呼叫端負責 commit。

    - Employee：以 emp_no 查找。不存在則新增（emp_name/dept_no/is_leave=False，
      notes_id 能從 email 反推就填）。存在則：is_leave 重置為 False（能登入代表在職）、
      dept_no 有值才覆蓋、notes_id 能反推才覆蓋（否則保留既有值），emp_name 只在既有
      為空時才用這次登入帶來的姓名補上——表內已有姓名一律優先（AUTH_MOCK 時 username
      只是佔位補救，不該蓋掉真名）。
    - SignEmp：以 emp_no 唯一鍵查找，無則插入 emp_name/email/dep_no，有則同步更新
      （沿用上面決議出的姓名，email/dep_no 有值才覆蓋）。
    """
    derived_notes_id = _derive_notes_id(info.email)

    employee = db.execute(
        select(Employee).where(Employee.emp_no == info.empno)
    ).scalar_one_or_none()

    if employee is None:
        employee = Employee(
            emp_no=info.empno,
            emp_name=info.name,
            dept_no=info.dept_no or None,
            notes_id=derived_notes_id or None,
            is_leave=False,
        )
        db.add(employee)
    else:
        employee.is_leave = False
        if info.dept_no:
            employee.dept_no = info.dept_no
        if derived_notes_id:
            employee.notes_id = derived_notes_id
        if not employee.emp_name:
            employee.emp_name = info.name

    db.flush()

    result_name = employee.emp_name or info.name
    result_dept = employee.dept_no or info.dept_no or ""

    sign_emp = db.execute(
        select(SignEmp).where(SignEmp.emp_no == info.empno)
    ).scalar_one_or_none()

    if sign_emp is None:
        db.add(
            SignEmp(
                emp_no=info.empno,
                emp_name=result_name,
                email=info.email or None,
                dep_no=result_dept or None,
            )
        )
    else:
        sign_emp.emp_name = result_name
        if info.email:
            sign_emp.email = info.email
        if result_dept:
            sign_emp.dep_no = result_dept

    return UserInfo(empno=info.empno, name=result_name, dept_no=result_dept, email=info.email)
