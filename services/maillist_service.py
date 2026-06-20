"""
maillist_service.py — 派送名單維護（移植舊版 EditMailList.aspx）

VOC_Mail_List 存放異常 Email 通知的收件名單。
JOB 的 GetMailList(plantno, "TO"/"CC") 從此表取收件人，寄送異常 Email。
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from models.maillist_model import VocMailList
from models.acl_model import VocTranlog


def list_maillist(db: Session) -> list:
    """
    取得所有派送名單，依廠區、mailtype 排序。
    同時附上廠區清單供新增表單下拉選單使用。
    """
    sql = text("""
        SELECT seqno, plantno, empno, email, mailtype, isEnable
        FROM   [VOC].[dbo].[VOC_Mail_List]
        ORDER BY plantno, mailtype, seqno
    """)
    try:
        rows = db.execute(sql).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[list_maillist] DB 查詢失敗: {e}")
        return []


def get_plant_list(db: Session) -> list[str]:
    """取得所有廠區代號供下拉選單"""
    sql = text("""
        SELECT DISTINCT plantno
        FROM   [VOC].[dbo].[VOC_plant]
        WHERE  isShow = 1
        ORDER BY plantno
    """)
    try:
        rows = db.execute(sql).mappings().all()
        return [r["plantno"] for r in rows]
    except Exception as e:
        print(f"[get_plant_list] DB 查詢失敗: {e}")
        return []


def add_maillist(db: Session, current_user_empno: str,
                 plantno: str, empno: str, email: str, mailtype: str) -> int:
    """
    新增一筆派送名單。回傳新建的 seqno。
    防呆：同廠區同 email 同 mailtype 不可重複。
    """
    dup = db.execute(text("""
        SELECT 1 FROM [VOC].[dbo].[VOC_Mail_List]
        WHERE plantno = :plantno AND email = :email AND mailtype = :mailtype
    """), {"plantno": plantno, "email": email, "mailtype": mailtype}).first()
    if dup:
        raise ValueError(f"{plantno} / {email} ({mailtype}) 已存在，不可重複新增")

    entry = VocMailList(plantno=plantno, empno=empno,
                        email=email, mailtype=mailtype, isEnable=1)
    db.add(entry)
    db.flush()  # 取得 autoincrement seqno

    db.add(VocTranlog(
        empno=current_user_empno,
        logtype="I",
        databefore="",
        dataafter=f"派送名單新增: {plantno}/{mailtype}/{email}",
        cdatetime=datetime.now(),
        remark=""
    ))
    db.commit()
    return entry.seqno


def delete_maillist(db: Session, current_user_empno: str, seqno: int) -> bool:
    """刪除單筆派送名單"""
    entry = db.query(VocMailList).filter_by(seqno=seqno).first()
    if not entry:
        raise ValueError(f"找不到 seqno={seqno} 的派送名單")

    before = f"派送名單刪除: {entry.plantno}/{entry.mailtype}/{entry.email}"
    db.delete(entry)
    db.add(VocTranlog(
        empno=current_user_empno,
        logtype="D",
        databefore=before,
        dataafter="",
        cdatetime=datetime.now(),
        remark=""
    ))
    db.commit()
    return True


def get_maillist_for_notify(db: Session, plantno: str, mailtype: str = "TO") -> list[str]:
    """
    供 notify_service 使用：查詢指定廠區的收件人 Email 清單。
    mailtype: 'TO' 或 'CC'
    """
    sql = text("""
        SELECT email FROM [VOC].[dbo].[VOC_Mail_List]
        WHERE  plantno = :plantno AND mailtype = :mailtype AND isEnable = 1
    """)
    try:
        rows = db.execute(sql, {"plantno": plantno, "mailtype": mailtype}).mappings().all()
        return [r["email"] for r in rows]
    except Exception as e:
        print(f"[get_maillist_for_notify] DB 查詢失敗: {e}")
        return []
