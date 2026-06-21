"""
maillist_service.py — 派送名單維護（移植舊版 EditMailList.aspx + dbVOC.cs 派送名單方法）

依 docs/legacy_source_analysis.md 第二節重寫。重點：
  - VOC_Mail_List 複合主鍵 (plantno, rpttype, empno)
  - notesid 存檔/寄信雙向轉換
  - 「群組/值班」工號特例：notesid 手動輸入、不查員工表
  - Mail1/SM1 全域暫停寄信切換
  - GetMailList：TO 嚴格綁該廠；CC 額外納入 GMO、環工部
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from models.maillist_model import VocMailList
from models.acl_model import VocTranlog

# 「群組」「值班」工號為共用信箱，不查員工主檔，notesid 由人工輸入
_MANUAL_EMPNO_KEYWORDS = ("群組", "值班")

# CC 寄信時，除指定廠區外固定納入的集團監督單位
_CC_EXTRA_PLANTS = ("GMO", "環工部")


# ── 純邏輯輔助函式（可單獨測試，不依賴 DB）─────────────────────────────────

def normalize_notesid(raw: str) -> str:
    """存檔正規化：底線換空格、去掉 @aseglobal.com（舊版 .Replace('_',' ').Replace('@aseglobal.com',''))。"""
    return (raw or "").replace("_", " ").replace("@aseglobal.com", "").strip()


def notesid_to_email(notesid: str) -> str:
    """寄信還原：空格換底線 + 補 @aseglobal.com（舊版寄信時 NotesID.Replace(' ','_')+'@aseglobal.com'）。"""
    notesid = (notesid or "").strip()
    if notesid == "":
        return ""
    return notesid.replace(" ", "_") + "@aseglobal.com"


def is_manual_empno(empno: str) -> bool:
    """工號是否為群組/值班共用信箱（不查員工主檔）。"""
    return any(kw in (empno or "") for kw in _MANUAL_EMPNO_KEYWORDS)


def _tranlog_str(plantno, rpttype, empno, empname, notesid, cellphone, mailtype, mail, sm, signgrp) -> str:
    """組 VOC_tranlog 的斜線串（與舊版 databefore/dataafter 格式一致）。"""
    return "/".join([
        plantno, rpttype, empno, empname or "", notesid or "", cellphone or "",
        mailtype,
        "要" if mail else "否",
        "要" if sm else "否",
        "是" if signgrp else "否",
    ])


# ── 查詢 ──────────────────────────────────────────────────────────────────

def list_maillist(db: Session, plantno: str = "", rpttype: str = "") -> list:
    """取得派送名單（可選廠區、報表類型篩選），供 maillist_modal 表格顯示。"""
    sql = """
        SELECT plantno, rpttype, empno, empname, notesid, cellphone,
               mailtype, mail, SM, signgrp
        FROM   [VOC].[dbo].[VOC_Mail_List]
        WHERE  1=1
    """
    params = {}
    if plantno:
        sql += " AND plantno = :plantno"
        params["plantno"] = plantno
    if rpttype:
        sql += " AND rpttype = :rpttype"
        params["rpttype"] = rpttype
    sql += " ORDER BY plantno, rpttype, mailtype, empno"
    try:
        rows = db.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[list_maillist] DB 查詢失敗: {e}")
        return []


def get_plant_list(db: Session) -> list[str]:
    """廠區下拉清單。"""
    try:
        rows = db.execute(text("""
            SELECT DISTINCT plantno FROM [VOC].[dbo].[VOC_plant]
            WHERE isShow = 1 ORDER BY plantno
        """)).mappings().all()
        return [r["plantno"] for r in rows]
    except Exception as e:
        print(f"[get_plant_list] DB 查詢失敗: {e}")
        return []


def get_rpttype_list(db: Session) -> list[str]:
    """報表類型下拉清單（VOC_Mail_Type.RptType）。"""
    try:
        rows = db.execute(text("""
            SELECT RptType FROM [VOC].[dbo].[VOC_Mail_Type] ORDER BY typeid
        """)).mappings().all()
        return [r["RptType"] for r in rows]
    except Exception as e:
        print(f"[get_rpttype_list] DB 查詢失敗: {e}")
        return []


def lookup_employee(db: Session, empno: str) -> dict:
    """
    依工號帶出姓名與 notesid（舊版 __empno_TextChanged → dbSignFlow.Get員工資訊）。
    群組/值班工號回空（由人工填）。查不到也回空，不擋使用者手動輸入。

    ⚠️ 員工主檔來源待確認（舊系統用 SignFlow DB 的 Get員工資訊）。
       此處先查 [UTIDB].[dbo].[Employee]，欄位/DB 名稱日後接 LDAP 時一併校正。
    """
    if is_manual_empno(empno):
        return {"empname": "", "notesid": "", "manual": True}
    try:
        row = db.execute(text("""
            SELECT TOP 1 empname, email
            FROM [UTIDB].[dbo].[Employee]
            WHERE empno = :empno
        """), {"empno": empno}).mappings().first()
        if row:
            return {
                "empname": row.get("empname") or "",
                "notesid": normalize_notesid(row.get("email") or ""),
                "manual": False,
            }
    except Exception as e:
        print(f"[lookup_employee] 查詢失敗（容許手動輸入）: {e}")
    return {"empname": "", "notesid": "", "manual": False}


# ── 新增 / 修改 / 刪除 ──────────────────────────────────────────────────────

def add_maillist(db: Session, current_user_empno: str, data) -> None:
    """
    新增一筆派送名單。
    防重複：同 (plantno, rpttype, empno) 已存在則拒（舊版「此筆資料已存在派送名單資料內!」）。
    """
    try:
        dup = db.execute(text("""
            SELECT 1 FROM [VOC].[dbo].[VOC_Mail_List]
            WHERE plantno = :plantno AND rpttype = :rpttype AND empno = :empno
        """), {"plantno": data.plantno, "rpttype": data.rpttype, "empno": data.empno}).first()
        if dup:
            raise ValueError("此筆資料已存在派送名單資料內!")

        notesid = normalize_notesid(data.notesid)
        entry = VocMailList(
            plantno=data.plantno, rpttype=data.rpttype, empno=data.empno,
            empname=data.empname, notesid=notesid, cellphone=data.cellphone,
            mailtype=data.mailtype, mail=data.mail, SM=data.SM, signgrp=data.signgrp,
            Mail1=data.mail, SM1=data.SM,   # 備份欄與當前值同步
        )
        db.add(entry)

        db.add(VocTranlog(
            empno=current_user_empno, logtype="I", databefore="",
            dataafter=_tranlog_str(data.plantno, data.rpttype, data.empno, data.empname,
                                   notesid, data.cellphone, data.mailtype,
                                   data.mail, data.SM, data.signgrp),
            cdatetime=datetime.now(), remark=getattr(data, "remark", "") or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"[add_maillist] 新增失敗: {e}")
        raise


def update_maillist(db: Session, current_user_empno: str, data) -> None:
    """
    修改一筆派送名單。定位用 (plantno, rpttype, old_empno)，允許改 empno。
    """
    try:
        entry = db.query(VocMailList).filter_by(
            plantno=data.plantno, rpttype=data.rpttype, empno=data.old_empno
        ).first()
        if not entry:
            raise ValueError("找不到要修改的派送名單資料")

        before = _tranlog_str(entry.plantno, entry.rpttype, entry.empno, entry.empname,
                              entry.notesid, entry.cellphone, entry.mailtype,
                              entry.mail, entry.SM, entry.signgrp)

        notesid = normalize_notesid(data.notesid)
        entry.empno     = data.empno
        entry.empname   = data.empname
        entry.notesid   = notesid
        entry.cellphone = data.cellphone
        entry.mailtype  = data.mailtype
        entry.mail      = data.mail
        entry.SM        = data.SM
        entry.signgrp   = data.signgrp

        db.add(VocTranlog(
            empno=current_user_empno, logtype="M", databefore=before,
            dataafter=_tranlog_str(data.plantno, data.rpttype, data.empno, data.empname,
                                   notesid, data.cellphone, data.mailtype,
                                   data.mail, data.SM, data.signgrp),
            cdatetime=datetime.now(), remark=getattr(data, "remark", "") or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"[update_maillist] 修改失敗: {e}")
        raise


def delete_maillist(db: Session, current_user_empno: str,
                    plantno: str, rpttype: str, empno: str) -> None:
    """刪除一筆派送名單。"""
    try:
        entry = db.query(VocMailList).filter_by(
            plantno=plantno, rpttype=rpttype, empno=empno
        ).first()
        if not entry:
            raise ValueError("找不到要刪除的派送名單資料")

        before = _tranlog_str(entry.plantno, entry.rpttype, entry.empno, entry.empname,
                              entry.notesid, entry.cellphone, entry.mailtype,
                              entry.mail, entry.SM, entry.signgrp)
        db.delete(entry)
        db.add(VocTranlog(
            empno=current_user_empno, logtype="D",
            databefore=before, dataafter="",
            cdatetime=datetime.now(), remark="",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"[delete_maillist] 刪除失敗: {e}")
        raise


# ── 全域暫停寄信切換（舊版 Mail停用/Mail啟用/CheckStatus，dbVOC.cs:2420-2440）──

def disable_all_mail(db: Session) -> None:
    """停用：先把現值備份到 Mail1/SM1，再把 Mail/SM 全設 0。"""
    db.execute(text("UPDATE [VOC].[dbo].[VOC_Mail_List] SET Mail1=Mail, SM1=SM"))
    db.execute(text("UPDATE [VOC].[dbo].[VOC_Mail_List] SET Mail=0, SM=0"))
    db.commit()


def enable_all_mail(db: Session) -> None:
    """啟用：從 Mail1/SM1 還原各筆原本的開關。"""
    db.execute(text("UPDATE [VOC].[dbo].[VOC_Mail_List] SET Mail=Mail1, SM=SM1"))
    db.commit()


def is_mail_disabled(db: Session) -> bool:
    """是否處於全域停用狀態（無任何 Mail=1 即視為停用）。"""
    cnt = db.execute(text(
        "SELECT COUNT(*) FROM [VOC].[dbo].[VOC_Mail_List] WHERE Mail=1"
    )).scalar()
    return (cnt or 0) == 0


# ── 寄信收件名單（供 notify_service 使用，對應 dbVOC.cs GetMailList）──────────

def build_maillist_where(rpttype_csv: str, plantno: str, mailtype: str) -> tuple[str, dict]:
    """
    組 GetMailList 的 WHERE 子句（參數化，取代舊版字串拼接）。
    rpttype_csv 可為逗號分隔多值。
    TO：嚴格 (rpttype=x AND plantno=指定廠)。
    CC：rpttype IN (...) AND plantno IN (指定廠, GMO, 環工部)。
    回傳 (where_sql, params)。
    """
    types = [t.strip() for t in rpttype_csv.split(",") if t.strip()]
    params: dict = {"mailtype": mailtype}
    if mailtype == "TO":
        ors = []
        for i, t in enumerate(types):
            params[f"rt{i}"] = t
            params["plantno"] = plantno
            ors.append(f"(rpttype = :rt{i} AND plantno = :plantno)")
        cond = " OR ".join(ors) if ors else "1=0"
        where = f"MailType = :mailtype AND NotesID != '' AND Mail = 1 AND ({cond})"
    else:  # CC
        in_types = []
        for i, t in enumerate(types):
            params[f"rt{i}"] = t
            in_types.append(f":rt{i}")
        plant_keys = []
        for i, p in enumerate((plantno,) + _CC_EXTRA_PLANTS):
            params[f"pl{i}"] = p
            plant_keys.append(f":pl{i}")
        type_in = ", ".join(in_types) if in_types else "''"
        plant_in = ", ".join(plant_keys)
        where = (f"MailType = :mailtype AND NotesID != '' AND Mail = 1 "
                 f"AND rpttype IN ({type_in}) AND plantno IN ({plant_in})")
    return where, params


def get_mail_recipients(db: Session, rpttype_csv: str, plantno: str,
                        mailtype: str = "TO") -> list[str]:
    """
    取得寄信收件 Email 清單（NotesID → email 還原）。
    對應舊版 GetMailList(sRed, plantno, MailType)。
    """
    where, params = build_maillist_where(rpttype_csv, plantno, mailtype)
    sql = f"SELECT DISTINCT NotesID FROM [VOC].[dbo].[VOC_Mail_List] WHERE {where}"
    try:
        rows = db.execute(text(sql), params).mappings().all()
        return [notesid_to_email(r["NotesID"]) for r in rows if r["NotesID"]]
    except Exception as e:
        print(f"[get_mail_recipients] DB 查詢失敗: {e}")
        return []
