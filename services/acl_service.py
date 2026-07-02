"""
acl_service.py — ACL 權限系統真實實作 + EditAclUser 頁面移植

對應舊版 dbAclRights.cs（Check權限 / GetIsAdmin）+ dbVOC.cs 隔離權限名單相關方法
（List廠區6 / List權限 / List隔離權限名單資料 / InsertAclUserList / UpdateAclUserList / DeleteAclUserList）。

權限模型（見 docs/legacy_source_analysis.md「權限（位元）」章節）：
  - sys_acluserrole(roleid, empno, deptno, plantno, stype)：某工號/部門被授予某角色，plantno 可為 'ALL'。
  - sys_aclrolerights(roleid, rightsid, allowrights)：某角色對某功能（rightsid）具備的權限位元
    （查詢1 / 修改2 / 新增4 / 刪除8 / 執行16，可複合）。
  - roleid 定義：1系統管理員 / 2規格維護 / 3隔離維護 / 4派報簡訊啟用 / 5停用 / 6派送名單 /
    7隔離查詢 / 8隔離權限 / 9QA / 10部門 / 11中水通知 / 12隔離時間修改。

⚠️ EditAclUser.aspx 舊版只開放管理 roleid In (3,7)（隔離維護／隔離查詢）兩種角色
   （List權限()/List隔離權限名單資料() 皆寫死 T.roleid In (3,7)），本檔沿用此限制。
   若要管理其餘角色（如 1系統管理員），舊系統本身也沒有網頁介面可管理，需直接操作 DB。
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from config import settings
from models.acl_model import SysAclUserRole, SysAclRole, VocTranlog
from schemas.acl_schema import AclUserCreate, AclUserUpdate, AclUserBase, AclUserResponse

logger = logging.getLogger(__name__)

# sys_aclrolerights.allowrights 位元定義（對應 dbAclRights.AclPermit enum）
_RIGHT_BITS = {
    "query": 1,     # 查詢
    "modify": 2,    # 修改
    "add": 4,       # 新增
    "delete": 8,    # 刪除
    "execute": 16,  # 執行
}

# 使用者權限 roleid=1「系統管理員」——同時也是 sys_aclrolerights.rightsid 的值，
# 對應舊版 dbAclRights.GetIsAdmin()：只要該工號的角色在 rightsid=1 有任一筆登記即視為系統管理員。
ROLE_SYSADMIN = 1

# EditAclUser.aspx 舊版只管理這兩種角色（隔離維護=3 / 隔離查詢=7），見上方檔頭說明
_EDITACLUSER_ROLEIDS = (3, 7)


# ── 純邏輯函式（可單獨測試，不依賴 DB）──────────────────────────────────────

def has_right(allowrights: int, action: str) -> bool:
    """
    位元判斷純函式：sys_aclrolerights.allowrights 是否包含 action 對應的權限位元。
    action 必須是 'query'/'modify'/'add'/'delete'/'execute' 之一。
    allowrights 可能是複合位元（如 31 = 全部權限），用 AND 判斷即可。
    """
    if action not in _RIGHT_BITS:
        raise ValueError(f"未知的權限動作 action={action!r}，"
                          f"應為 {list(_RIGHT_BITS.keys())} 之一")
    allowrights = allowrights or 0
    return bool(allowrights & _RIGHT_BITS[action])


def stype_code_to_text(code: str) -> str:
    """表單送出的 '1'/'2'/'3' 轉存檔用文字（舊版 InsertAclUserList/UpdateAclUserList 同款轉換）。"""
    if code == "1":
        return "空"
    if code == "2":
        return "水"
    return "ALL"


def stype_text_to_code(text_value: str) -> str:
    """DB 存的 '空'/'水'/'ALL' 轉回表單用代碼，供編輯表單回填。"""
    if text_value == "空":
        return "1"
    if text_value == "水":
        return "2"
    return "3"


# ── 權限檢查（真實 DB 實作）──────────────────────────────────────────────────

def is_admin(db: Session, empno: str) -> bool:
    """
    對應舊版 dbAclRights.GetIsAdmin()。
    empno 所屬的任一角色，在 sys_aclrolerights 對 rightsid=系統管理員(1) 有登記即視為系統管理員，
    無條件通過所有權限檢查。
    """
    try:
        cnt = db.execute(
            text(
                "SELECT COUNT(*) FROM [VOC].[dbo].[sys_acluserrole] R "
                "JOIN [VOC].[dbo].[sys_aclrolerights] AR ON R.roleid = AR.roleid "
                "WHERE R.empno = :empno AND AR.rightsid = :admin_rightsid"
            ),
            {"empno": empno, "admin_rightsid": ROLE_SYSADMIN},
        ).scalar()
        return (cnt or 0) > 0
    except Exception as e:
        logger.warning(f"[is_admin] 查詢失敗，視為非管理員 empno={empno}: {e}")
        return False


def check_permission(
    db: Session,
    empno: str,
    rightsid: int,
    action: str,
    plantno: str = "",
    deptno: str = "",
) -> bool:
    """
    對應舊版 dbAclRights.Check權限(rights, permits)，真實查 sys_acluserrole × sys_aclrolerights。

    empno   ：操作者工號
    rightsid：功能代碼（同 roleid 定義，如 3=隔離維護）
    action  ：'query'/'modify'/'add'/'delete'/'execute' 之一，對應位元 1/2/4/8/16
    plantno ：可選，帶入時只承認 R.plantno = plantno 或 R.plantno = 'ALL' 的角色（廠區範圍限制）
    deptno  ：可選，比照舊版 (R.empno=@empno Or R.deptno=@deptno) 額外允許部門角色

    行為：
      - 系統管理員（is_admin）無條件放行。
      - settings.ACL_ENFORCE = False（預設）：權限不足只記 log warning，仍然放行，
        避免 sys_acluserrole/sys_aclrolerights 資料尚未建置完成就把整個系統鎖死。
      - settings.ACL_ENFORCE = True：權限不足直接回傳 False。
      - DB 查詢例外：視為未取得授權，交由上述 ACL_ENFORCE 規則決定要不要擋。
    """
    try:
        if is_admin(db, empno):
            return True

        sql = (
            "SELECT AR.allowrights "
            "FROM [VOC].[dbo].[sys_acluserrole] R "
            "JOIN [VOC].[dbo].[sys_aclrolerights] AR ON R.roleid = AR.roleid "
            "WHERE (R.empno = :empno"
        )
        params: dict = {"empno": empno, "rightsid": rightsid}
        if deptno:
            sql += " OR R.deptno = :deptno"
            params["deptno"] = deptno
        sql += ") AND AR.rightsid = :rightsid"

        if plantno:
            sql += " AND (R.plantno = :plantno OR R.plantno = 'ALL')"
            params["plantno"] = plantno

        rows = db.execute(text(sql), params).mappings().all()
        allowed = any(has_right(row["allowrights"], action) for row in rows)
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
    """
    回傳 empno 可視的廠區清單（sys_acluserrole.plantno），供其他模組做廠區過濾用。
    plantno='ALL' 語意 = 不限廠區，此時回傳特殊值 ['ALL']（呼叫端應判斷 'ALL' in plants 代表全廠可見，
    不在此展開成實際廠區清單，避免多一層對 VOC_plant 的相依）。
    查詢失敗回傳空清單（呼叫端應視為「無可視廠區」，而非放行全部，避免權限資料異常時洩漏資料）。
    """
    try:
        rows = db.execute(
            text("SELECT DISTINCT plantno FROM [VOC].[dbo].[sys_acluserrole] WHERE empno = :empno"),
            {"empno": empno},
        ).mappings().all()
        plants = [r["plantno"] for r in rows if r["plantno"]]
        if "ALL" in plants:
            return ["ALL"]
        return plants
    except Exception as e:
        logger.warning(f"[get_user_plants] 查詢失敗 empno={empno}: {e}")
        return []


# ── EditAclUser 頁面移植：下拉選單資料來源 ────────────────────────────────────

def get_role_list(db: Session) -> List[dict]:
    """對應舊版 List權限()。EditAclUser 頁面只開放管理隔離維護(3)/隔離查詢(7) 兩種角色。"""
    rows = db.execute(
        text(
            "SELECT roleid, rolename AS roletype FROM [VOC].[dbo].[sys_aclrole] "
            "WHERE roleid IN (3, 7) ORDER BY roleid"
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def get_plant_list(db: Session) -> List[dict]:
    """對應舊版 List廠區6()：有規格資料（source<3，即 SCADA/CWMS）的廠區 + 'ALL'。"""
    rows = db.execute(
        text(
            "SELECT DISTINCT P.plantid, P.plantno "
            "FROM [VOC].[dbo].[VOC_SPEC] S "
            "JOIN [VOC].[dbo].[VOC_plant] P ON S.plantno = P.plantno "
            "WHERE S.source < 3 "
            "UNION "
            "SELECT plantid, plantno FROM [VOC].[dbo].[VOC_plant] WHERE plantno = 'ALL' "
            "ORDER BY plantid"
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def lookup_employee(db: Session, empno: str) -> dict:
    """
    依工號帶出姓名與 notesid（對應舊版 __empno_TextChanged → dbSignFlow.Get員工資訊）。
    查不到回空，不擋使用者手動輸入。

    ⚠️ 員工主檔來源比照 maillist_service.lookup_employee，先查 [UTIDB].[dbo].[Employee]，
       待 LDAP 串接後可能需要改用 dbSignFlow 對應的資料源，一併校正。
    """
    if not empno:
        return {"empname": "", "notesid": ""}
    try:
        row = db.execute(
            text("SELECT TOP 1 empname, email FROM [UTIDB].[dbo].[Employee] WHERE empno = :empno"),
            {"empno": empno},
        ).mappings().first()
        if row:
            notesid = (row.get("email") or "").replace("_", " ").replace("@aseglobal.com", "")
            return {"empname": row.get("empname") or "", "notesid": notesid}
    except Exception as e:
        logger.warning(f"[lookup_employee] 查詢失敗（容許手動輸入） empno={empno}: {e}")
    return {"empname": "", "notesid": ""}


def _get_rolename(db: Session, roleid: int) -> str:
    """查 sys_aclrole.rolename，供 VOC_tranlog 訊息使用；查不到時退回 roleid 數字字串。"""
    try:
        role = db.query(SysAclRole).filter_by(roleid=roleid).first()
        if role and role.rolename:
            return role.rolename
    except Exception as e:
        logger.warning(f"[_get_rolename] 查詢失敗 roleid={roleid}: {e}")
    return str(roleid)


# ── 查詢：隔離權限名單 ────────────────────────────────────────────────────────

def list_acl_users(
    db: Session, plantno: str = "", roletype: str = "", empno: str = ""
) -> List[AclUserResponse]:
    """
    對應舊版 dbVOC.List隔離權限名單資料()。真實 DB 查詢，不再有 mock fallback：
    連線/查詢失敗直接 raise（並記 log），由呼叫端（router）轉成 500 錯誤，不要偷偷回假資料。
    """
    sql = (
        "SELECT R.plantno AS plantno, T.rolename AS roletype, R.empno AS empno, "
        "       E.empname AS empname, E.notesid AS notesid, R.stype AS stype "
        "FROM [VOC].[dbo].[sys_acluserrole] R "
        "JOIN [VOC].[dbo].[sys_aclrole] T ON R.roleid = T.roleid "
        "LEFT JOIN [UTIDB].[dbo].[Employee] E ON R.empno = E.empno "
        f"WHERE T.roleid IN ({','.join(str(r) for r in _EDITACLUSER_ROLEIDS)})"
    )
    params: dict = {}
    if plantno:
        sql += " AND R.plantno = :plantno"
        params["plantno"] = plantno
    if roletype:
        sql += " AND T.rolename = :roletype"
        params["roletype"] = roletype
    if empno:
        sql += " AND R.empno = :empno"
        params["empno"] = empno
    sql += " ORDER BY R.plantno, T.roleid"

    try:
        rows = db.execute(text(sql), params).mappings().all()
    except Exception as e:
        logger.error(f"[list_acl_users] DB 查詢失敗: {e}")
        raise

    # 注意：stype 保留 DB 原值（空/水/ALL），不在此轉成「全區」顯示字樣，
    # 讓前端編輯表單能用原值正確回填；顯示層的「全區」轉換交給 template 處理。
    return [
        AclUserResponse(
            plantno=row["plantno"],
            roletype=row["roletype"],
            empno=row["empno"],
            empname=row.get("empname") or "",
            notesid=(row.get("notesid") or "").replace("@aseglobal.com", ""),
            stype=row["stype"] or "ALL",
        )
        for row in rows
    ]


# ── 新增 / 修改 / 刪除（對應 InsertAclUserList / UpdateAclUserList / DeleteAclUserList）──

def create_acl_user(db: Session, current_user_empno: str, data: AclUserCreate) -> None:
    """
    對應舊版 InsertAclUserList。防重複：同 (roleid, plantno, empno) 已存在則拒。
    失敗（含防重複）一律 raise ValueError，由 router 轉成 400；其餘例外原樣往上拋。
    """
    try:
        existing = db.query(SysAclUserRole).filter_by(
            roleid=data.role_id, plantno=data.plantno, empno=data.empno
        ).first()
        if existing:
            raise ValueError("此筆資料已存在隔離權限名單資料內!")

        stype_val = stype_code_to_text(data.stype)
        rolename = _get_rolename(db, data.role_id)

        db.add(SysAclUserRole(
            roleid=data.role_id, plantno=data.plantno, empno=data.empno, stype=stype_val,
        ))
        db.add(VocTranlog(
            empno=current_user_empno, logtype="I", databefore="",
            dataafter=f"{data.plantno}/{rolename}/{data.empno}/{stype_val}",
            cdatetime=datetime.now(), remark=data.remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[create_acl_user] 新增失敗: {e}")
        raise


def update_acl_user(db: Session, current_user_empno: str, data: AclUserUpdate) -> None:
    """
    對應舊版 UpdateAclUserList(hrow, pempno, pstype)。
    roleid + plantno + 舊工號(old_empno) 定位，可修改 empno / stype。

    ⚠️ 與舊版差異：empno 是 Python 端 sys_acluserrole 複合主鍵的一部分（roleid, plantno, empno），
    若 empno 改變，UPDATE 會撞主鍵，因此改 empno 時採「刪除舊列＋新增新列」，效果等同舊版 UPDATE。
    """
    try:
        entry = db.query(SysAclUserRole).filter_by(
            roleid=data.role_id, plantno=data.plantno, empno=data.old_empno
        ).first()
        if not entry:
            raise ValueError("找不到要修改的隔離權限名單資料")

        rolename = _get_rolename(db, data.role_id)
        stype_val = stype_code_to_text(data.stype)
        before = f"{data.plantno}/{rolename}/{data.old_empno}/{data.old_stype}"

        if data.empno != data.old_empno:
            db.delete(entry)
            db.flush()
            db.add(SysAclUserRole(
                roleid=data.role_id, plantno=data.plantno, empno=data.empno, stype=stype_val,
            ))
        else:
            entry.stype = stype_val

        db.add(VocTranlog(
            empno=current_user_empno, logtype="M", databefore=before,
            dataafter=f"{data.plantno}/{rolename}/{data.empno}/{stype_val}",
            cdatetime=datetime.now(), remark=data.remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[update_acl_user] 修改失敗: {e}")
        raise


def delete_acl_user(db: Session, current_user_empno: str, data: AclUserBase) -> None:
    """對應舊版 DeleteAclUserList。找不到資料則 raise ValueError。"""
    try:
        entry = db.query(SysAclUserRole).filter_by(
            roleid=data.role_id, plantno=data.plantno, empno=data.empno
        ).first()
        if not entry:
            raise ValueError("找不到要刪除的隔離權限名單資料")

        rolename = _get_rolename(db, data.role_id)
        stype_before = entry.stype

        db.delete(entry)
        db.add(VocTranlog(
            empno=current_user_empno, logtype="D",
            databefore=f"{data.plantno}/{rolename}/{data.empno}/{stype_before}",
            dataafter="",
            cdatetime=datetime.now(), remark=data.remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[delete_acl_user] 刪除失敗: {e}")
        raise
