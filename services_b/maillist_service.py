"""
services_b/maillist_service.py — 派送名單維護（Schema B 資料層版本）

對應 services/maillist_service.py（A/MSSQL 版）。B 版資料層差異（schema_B_設計提案.md F/I 項決策）：

  1. mail_list 新形狀：PK (plant_no, rpttype, emp_no)，欄位為
     emp_name/notes_id/mail_type('TO'/'CC')/mail_on(bool)/sign_grp(bool)，
     **無 SM/cellphone/Mail1/SM1**（簡訊停用 + 全域暫停改用 system_config.mail_paused，見下）。
  2. 全域暫停寄信（F 項）：A 版靠把每列 Mail/SM 抄到 Mail1/SM1 再歸零；B 版改讀寫
     `system_config.mail_paused` 單一旗標，名單資料本身完全不動，`get_mail_recipients()`
     內部檢查此旗標，暫停時一律回傳空清單（不論 mail_on 個別設定）。
  3. CC 虛擬廠區（G 項）：A 版 CC 收件人寫死納入 ('GMO','環工部') 兩個廠區代碼字串；
     B 版改查 `plant.kind='virtual_group'` 的廠區清單，不在程式碼寫死廠區名稱
     （新增/移除虛擬廠區只需改 plant 表資料，不必動程式碼）。

沿用重用（禁止複製，皆為不依賴 DB 的純函式）：
  - services.maillist_service.normalize_notesid / notesid_to_email / is_manual_empno
"""

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import MailList, MailTypeModel, Plant, Employee, SystemConfig, Tranlog
from services.maillist_service import normalize_notesid, notesid_to_email, is_manual_empno  # noqa: F401

logger = logging.getLogger(__name__)

MAIL_PAUSED_KEY = "mail_paused"


# ── 全域暫停寄信旗標（F 項決策：取代 Mail1/SM1 備份欄）───────────────────────

def is_mail_paused(db: Session) -> bool:
    """讀 system_config['mail_paused']，找不到視為未暫停（false）。"""
    row = db.execute(select(SystemConfig.value).where(SystemConfig.key == MAIL_PAUSED_KEY)).scalar_one_or_none()
    return (row or "false").strip().lower() == "true"


def set_mail_paused(db: Session, paused: bool) -> None:
    """設定全域暫停旗標（對應 A 版 disable_all_mail/enable_all_mail 的等價操作）。"""
    row = db.execute(select(SystemConfig).where(SystemConfig.key == MAIL_PAUSED_KEY)).scalar_one_or_none()
    value = "true" if paused else "false"
    if row is None:
        db.add(SystemConfig(key=MAIL_PAUSED_KEY, value=value))
    else:
        row.value = value
    db.commit()


# ── 虛擬廠區（G 項：取代寫死 'GMO'/'環工部'）──────────────────────────────────

def get_virtual_group_plant_nos(db: Session) -> List[str]:
    """CC 寄信時額外納入的集團監督單位廠區清單（plant.kind='virtual_group'）。"""
    rows = db.execute(select(Plant.plant_no).where(Plant.kind == "virtual_group")).scalars().all()
    return list(rows)


# ── 查詢 ──────────────────────────────────────────────────────────────────

def list_maillist(db: Session, plant_no: str = "", rpttype: str = "") -> List[dict]:
    """取得派送名單（可選廠區、報表類型篩選），供 maillist_modal 表格顯示。"""
    stmt = select(MailList)
    if plant_no:
        stmt = stmt.where(MailList.plant_no == plant_no)
    if rpttype:
        stmt = stmt.where(MailList.rpttype == rpttype)
    stmt = stmt.order_by(MailList.plant_no, MailList.rpttype, MailList.mail_type, MailList.emp_no)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "plantno": r.plant_no, "rpttype": r.rpttype, "empno": r.emp_no,
            "empname": r.emp_name, "notesid": r.notes_id,
            "mailtype": r.mail_type, "mail": r.mail_on, "signgrp": r.sign_grp,
        }
        for r in rows
    ]


def get_plant_list(db: Session) -> List[str]:
    """廠區下拉清單（is_show=true）。"""
    rows = db.execute(select(Plant.plant_no).where(Plant.is_show.is_(True)).order_by(Plant.sort)).scalars().all()
    return list(rows)


def get_rpttype_list(db: Session) -> List[str]:
    """報表類型下拉清單（mail_type 主檔）。"""
    rows = db.execute(select(MailTypeModel.rpttype).order_by(MailTypeModel.type_id)).scalars().all()
    return list(rows)


def lookup_employee(db: Session, empno: str) -> dict:
    """依工號帶出姓名與 notesid（群組/值班工號回空，由人工填）。查不到也回空，不擋手動輸入。"""
    if is_manual_empno(empno):
        return {"empname": "", "notesid": "", "manual": True}
    emp = db.execute(select(Employee).where(Employee.emp_no == empno)).scalar_one_or_none()
    if emp:
        return {
            "empname": emp.emp_name or "",
            "notesid": normalize_notesid(emp.notes_id or ""),
            "manual": False,
        }
    return {"empname": "", "notesid": "", "manual": False}


# ── 新增 / 修改 / 刪除 ──────────────────────────────────────────────────────

def add_maillist(db: Session, current_user_empno: str, plant_no: str, rpttype: str, emp_no: str,
                  emp_name: str = "", notes_id: str = "", mail_type: str = "TO",
                  mail_on: bool = True, sign_grp: bool = False, remark: str = "") -> None:
    """新增一筆派送名單。防重複：同 (plant_no, rpttype, emp_no) 已存在則拒。"""
    try:
        existing = db.execute(
            select(MailList).where(
                MailList.plant_no == plant_no, MailList.rpttype == rpttype, MailList.emp_no == emp_no
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError("此筆資料已存在派送名單資料內!")

        notesid_norm = normalize_notesid(notes_id)
        db.add(MailList(
            plant_no=plant_no, rpttype=rpttype, emp_no=emp_no, emp_name=emp_name,
            notes_id=notesid_norm, mail_type=mail_type, mail_on=mail_on, sign_grp=sign_grp,
        ))
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="I", data_before={},
            data_after={"plant_no": plant_no, "rpttype": rpttype, "emp_no": emp_no, "emp_name": emp_name,
                        "notes_id": notesid_norm, "mail_type": mail_type, "mail_on": mail_on, "sign_grp": sign_grp},
            remark=remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[add_maillist] 新增失敗: {e}")
        raise


def update_maillist(db: Session, current_user_empno: str, plant_no: str, rpttype: str, old_emp_no: str,
                     emp_no: str, emp_name: str = "", notes_id: str = "", mail_type: str = "TO",
                     mail_on: bool = True, sign_grp: bool = False, remark: str = "") -> None:
    """修改一筆派送名單。定位用 (plant_no, rpttype, old_emp_no)，允許改 emp_no。"""
    try:
        entry = db.execute(
            select(MailList).where(
                MailList.plant_no == plant_no, MailList.rpttype == rpttype, MailList.emp_no == old_emp_no
            )
        ).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要修改的派送名單資料")

        before = {
            "emp_no": entry.emp_no, "emp_name": entry.emp_name, "notes_id": entry.notes_id,
            "mail_type": entry.mail_type, "mail_on": entry.mail_on, "sign_grp": entry.sign_grp,
        }

        notesid_norm = normalize_notesid(notes_id)
        if emp_no != old_emp_no:
            # emp_no 是複合主鍵一部分，改鍵值一律用「刪除舊列＋新增新列」達成（比照 acl_service 手法）
            db.delete(entry)
            db.flush()
            db.add(MailList(
                plant_no=plant_no, rpttype=rpttype, emp_no=emp_no, emp_name=emp_name,
                notes_id=notesid_norm, mail_type=mail_type, mail_on=mail_on, sign_grp=sign_grp,
            ))
        else:
            entry.emp_name = emp_name
            entry.notes_id = notesid_norm
            entry.mail_type = mail_type
            entry.mail_on = mail_on
            entry.sign_grp = sign_grp

        db.add(Tranlog(
            emp_no=current_user_empno, log_type="M", data_before=before,
            data_after={"emp_no": emp_no, "emp_name": emp_name, "notes_id": notesid_norm,
                        "mail_type": mail_type, "mail_on": mail_on, "sign_grp": sign_grp},
            remark=remark or "",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[update_maillist] 修改失敗: {e}")
        raise


def delete_maillist(db: Session, current_user_empno: str, plant_no: str, rpttype: str, emp_no: str) -> None:
    """刪除一筆派送名單。"""
    try:
        entry = db.execute(
            select(MailList).where(
                MailList.plant_no == plant_no, MailList.rpttype == rpttype, MailList.emp_no == emp_no
            )
        ).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要刪除的派送名單資料")

        before = {
            "plant_no": entry.plant_no, "rpttype": entry.rpttype, "emp_no": entry.emp_no,
            "emp_name": entry.emp_name, "notes_id": entry.notes_id,
            "mail_type": entry.mail_type, "mail_on": entry.mail_on, "sign_grp": entry.sign_grp,
        }
        db.delete(entry)
        db.add(Tranlog(
            emp_no=current_user_empno, log_type="D", data_before=before, data_after={}, remark="",
        ))
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[delete_maillist] 刪除失敗: {e}")
        raise


# ── 寄信收件名單（供 dispatch_service / warning_service 使用）──────────────────

def get_mail_recipients(db: Session, rpttype_csv: str, plant_no: str, mail_type: str = "TO") -> List[str]:
    """
    取得寄信收件 Email 清單（notes_id → email 還原）。
    對應 A 版 get_mail_recipients(rpttype_csv, plantno, mailtype)。

    全域暫停（is_mail_paused）時一律回傳空清單，不論各筆 mail_on 設定為何。
    TO：嚴格 (rpttype IN types AND plant_no = 指定廠)。
    CC：rpttype IN types AND plant_no IN (指定廠, *虛擬廠區*)（G 項：不寫死廠區字串）。
    """
    if is_mail_paused(db):
        return []

    types = [t.strip() for t in rpttype_csv.split(",") if t.strip()]
    if not types:
        return []

    stmt = select(MailList.notes_id).distinct().where(
        MailList.mail_type == mail_type,
        MailList.mail_on.is_(True),
        MailList.notes_id.is_not(None),
        MailList.notes_id != "",
        MailList.rpttype.in_(types),
    )
    if mail_type == "TO":
        stmt = stmt.where(MailList.plant_no == plant_no)
    else:  # CC
        plants = [plant_no] + get_virtual_group_plant_nos(db)
        stmt = stmt.where(MailList.plant_no.in_(plants))

    rows = db.execute(stmt).scalars().all()
    return [notesid_to_email(n) for n in rows if n]
