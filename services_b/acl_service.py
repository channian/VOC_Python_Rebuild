"""
services_b/acl_service.py — ACL 權限系統（Schema B 資料層版本）

對應 services/acl_service.py（A/MSSQL 版：dbAclRights.cs Check權限/GetIsAdmin + EditAclUser 頁面）。
B 版差異：
  - sys_acluserrole/sys_aclrolerights/sys_aclrole → models_b.AclUserRole/AclRoleRights/AclRole，
    位元旗標語意完全不變（1查詢/2修改/4新增/8刪除/16執行）。
  - 員工查詢改用 B 內 employee 快取表（models_b.Employee），取代 A 版查 [UTIDB].[dbo].[Employee]。
  - ACL_ENFORCE 行為與 A 版一致：沿用 config.settings.ACL_ENFORCE 開關，
    False（預設）僅記 log 仍放行、True 才真的擋下（尚未接 LDAP 前不鎖死系統，見 CLAUDE.md）。

沿用重用（禁止複製，皆為不依賴 DB 的純函式）：
  - services.acl_service.has_right / stype_code_to_text / stype_text_to_code
  - services.acl_service.ROLE_SYSADMIN（系統管理員 rightsid 常數）
"""

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from models_b import AclUserRole, AclRole, AclRoleRights, Employee, Tranlog
from services.acl_service import (  # noqa: F401
    has_right,
    stype_code_to_text,
    stype_text_to_code,
    ROLE_SYSADMIN,
)

logger = logging.getLogger(__name__)

# EditAclUser.aspx 舊版只管理這兩種角色（隔離維護=3 / 隔離查詢=7），與 A 版一致
_EDITACLUSER_ROLEIDS = (3, 7)


# ── 權限檢查（真實 DB 實作）──────────────────────────────────────────────────

def is_admin(db: Session, empno: str) -> bool:
    """對應 A 版 is_admin()：empno 所屬任一角色在 acl_role_rights 對 rights_id=系統管理員(1) 有登記。"""
    try:
        cnt = db.execute(
            select(AclRoleRights.role_id)
            .join(AclUserRole, AclUserRole.role_id == AclRoleRights.role_id)
            .where(AclUserRole.emp_no == empno, AclRoleRights.rights_id == ROLE_SYSADMIN)
            .limit(1)
        ).first()
        return cnt is not None
    except Exception as e:
        logger.warning(f"[is_admin] 查詢失敗，視為非管理員 empno={empno}: {e}")
        return False


def check_permission(db: Session, empno: str, rightsid: int, action: str,
                      plantno: str = "", deptno: str = "") -> bool:
    """對應 A 版 check_permission()：真實查 acl_user_role × acl_role_rights，ACL_ENFORCE 行為一致。"""
    try:
        if is_admin(db, empno):
            return True

        stmt = (
            select(AclRoleRights.allow_rights)
            .join(AclUserRole, AclUserRole.role_id == AclRoleRights.role_id)
            .where(AclRoleRights.rights_id == rightsid)
        )
        if deptno:
            stmt = stmt.where((AclUserRole.emp_no == empno) | (AclUserRole.dept_no == deptno))
        else:
            stmt = stmt.where(AclUserRole.emp_no == empno)
        if plantno:
            stmt = stmt.where((AclUserRole.plant_no == plantno) | (AclUserRole.plant_no == "ALL"))

        rows = db.execute(stmt).scalars().all()
        allowed = any(has_right(v, action) for v in rows)
    except Exception as e:
        logger.warning(f"[check_permission] 查詢失敗，視為未取得授權 "
                        f"empno={empno} rightsid={rightsid} action={action}: {e}")
        allowed = False

    if not allowed:
        if settings.ACL_ENFORCE:
            logger.warning(f"[ACL] empno={empno} 對 rightsid={rightsid} action={action} "
                            f"權限不足，ACL_ENFORCE=True，已阻擋")
            return False
        logger.warning(f"[ACL] empno={empno} 對 rightsid={rightsid} action={action} "
                        f"權限不足，ACL_ENFORCE=False，僅記錄仍放行")
        return True
    return True


def get_user_plants(db: Session, empno: str) -> list[str]:
    """回傳 empno 可視的廠區清單（plant_no='ALL' 語意=不限廠區，回傳特殊值 ['ALL']）。"""
    try:
        rows = db.execute(
            select(AclUserRole.plant_no).where(AclUserRole.emp_no == empno).distinct()
        ).scalars().all()
        plants = [p for p in rows if p]
        if "ALL" in plants:
            return ["ALL"]
        return plants
    except Exception as e:
        logger.warning(f"[get_user_plants] 查詢失敗 empno={empno}: {e}")
        return []


# ── EditAclUser 頁面移植：下拉選單資料來源 ────────────────────────────────────

def get_role_list(db: Session) -> List[dict]:
    """對應 A 版 get_role_list()：EditAclUser 頁面只開放管理隔離維護(3)/隔離查詢(7) 兩種角色。"""
    rows = db.execute(
        select(AclRole.role_id, AclRole.role_name)
        .where(AclRole.role_id.in_(_EDITACLUSER_ROLEIDS))
        .order_by(AclRole.role_id)
    ).all()
    return [{"roleid": r.role_id, "roletype": r.role_name} for r in rows]


def get_plant_list(db: Session) -> List[dict]:
    """
    對應 A 版 get_plant_list()（List廠區6：有規格資料的廠區 + 'ALL'）。
    B 版簡化：直接回傳所有 is_show=true 的廠區（規格資料是否存在交由申請時驗證，
    不在下拉選單這層額外篩選 source<3，避免多一層與 spec 表耦合；'ALL' 語意由 plant.kind='all' 表達）。
    """
    from models_b import Plant
    rows = db.execute(
        select(Plant.plant_id, Plant.plant_no).where(Plant.is_show.is_(True)).order_by(Plant.plant_id)
    ).all()
    return [{"plantid": r.plant_id, "plantno": r.plant_no} for r in rows]


def lookup_employee(db: Session, empno: str) -> dict:
    """依工號帶出姓名與 notesid，查不到回空，不擋手動輸入。"""
    if not empno:
        return {"empname": "", "notesid": ""}
    emp = db.execute(select(Employee).where(Employee.emp_no == empno)).scalar_one_or_none()
    if emp:
        notesid = (emp.notes_id or "").replace("_", " ").replace("@aseglobal.com", "")
        return {"empname": emp.emp_name or "", "notesid": notesid}
    return {"empname": "", "notesid": ""}


def _get_rolename(db: Session, roleid: int) -> str:
    role = db.execute(select(AclRole.role_name).where(AclRole.role_id == roleid)).scalar_one_or_none()
    return role or str(roleid)


# ── 查詢：隔離權限名單 ────────────────────────────────────────────────────────

def list_acl_users(db: Session, plantno: str = "", roletype: str = "", empno: str = "") -> List[dict]:
    """對應 A 版 list_acl_users()：真實 DB 查詢，連線/查詢失敗直接 raise（不回傳假資料）。"""
    stmt = (
        select(AclUserRole.plant_no, AclRole.role_name, AclUserRole.emp_no,
               Employee.emp_name, Employee.notes_id, AclUserRole.stype)
        .join(AclRole, AclRole.role_id == AclUserRole.role_id)
        .outerjoin(Employee, Employee.emp_no == AclUserRole.emp_no)
        .where(AclRole.role_id.in_(_EDITACLUSER_ROLEIDS))
    )
    if plantno:
        stmt = stmt.where(AclUserRole.plant_no == plantno)
    if roletype:
        stmt = stmt.where(AclRole.role_name == roletype)
    if empno:
        stmt = stmt.where(AclUserRole.emp_no == empno)
    stmt = stmt.order_by(AclUserRole.plant_no, AclRole.role_id)

    try:
        rows = db.execute(stmt).all()
    except Exception as e:
        logger.error(f"[list_acl_users] DB 查詢失敗: {e}")
        raise

    return [
        {
            "plantno": r.plant_no,
            "roletype": r.role_name,
            "empno": r.emp_no,
            "empname": r.emp_name or "",
            "notesid": (r.notes_id or "").replace("@aseglobal.com", ""),
            "stype": r.stype or "ALL",
        }
        for r in rows
    ]


# ── 新增 / 修改 / 刪除 ──────────────────────────────────────────────────────

def create_acl_user(db: Session, current_user_empno: str, plantno: str, role_id: int, empno: str,
                     stype: str = "3", remark: str = "") -> None:
    """對應 A 版 create_acl_user()。stype 為表單代碼 '1'/'2'/'3'，防重複：同 (role_id,plantno,empno)。"""
    try:
        existing = db.execute(
            select(AclUserRole).where(
                AclUserRole.role_id == role_id, AclUserRole.plant_no == plantno, AclUserRole.emp_no == empno
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError("此筆資料已存在隔離權限名單資料內!")

        stype_val = stype_code_to_text(stype)
        rolename = _get_rolename(db, role_id)

        db.add(AclUserRole(role_id=role_id, plant_no=plantno, emp_no=empno, stype=stype_val))
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="I", data_before={},
            data_after={"plantno": plantno, "rolename": rolename, "empno": empno, "stype": stype_val},
            remark=remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[create_acl_user] 新增失敗: {e}")
        raise


def update_acl_user(db: Session, current_user_empno: str, plantno: str, role_id: int, old_empno: str,
                     empno: str, stype: str, old_stype: str = "", remark: str = "") -> None:
    """對應 A 版 update_acl_user()。roleid + plantno + 舊工號(old_empno) 定位，可改 empno / stype。"""
    try:
        entry = db.execute(
            select(AclUserRole).where(
                AclUserRole.role_id == role_id, AclUserRole.plant_no == plantno, AclUserRole.emp_no == old_empno
            )
        ).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要修改的隔離權限名單資料")

        rolename = _get_rolename(db, role_id)
        stype_val = stype_code_to_text(stype)
        before = {"plantno": plantno, "rolename": rolename, "empno": old_empno, "stype": old_stype}

        if empno != old_empno:
            db.delete(entry)
            db.flush()
            db.add(AclUserRole(role_id=role_id, plant_no=plantno, emp_no=empno, stype=stype_val))
        else:
            entry.stype = stype_val

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="M", data_before=before,
            data_after={"plantno": plantno, "rolename": rolename, "empno": empno, "stype": stype_val},
            remark=remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[update_acl_user] 修改失敗: {e}")
        raise


def delete_acl_user(db: Session, current_user_empno: str, plantno: str, role_id: int, empno: str,
                     remark: str = "") -> None:
    """對應 A 版 delete_acl_user()。找不到資料則 raise ValueError。"""
    try:
        entry = db.execute(
            select(AclUserRole).where(
                AclUserRole.role_id == role_id, AclUserRole.plant_no == plantno, AclUserRole.emp_no == empno
            )
        ).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要刪除的隔離權限名單資料")

        rolename = _get_rolename(db, role_id)
        stype_before = entry.stype
        db.delete(entry)
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="D",
            data_before={"plantno": plantno, "rolename": rolename, "empno": empno, "stype": stype_before},
            data_after={}, remark=remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[delete_acl_user] 刪除失敗: {e}")
        raise
