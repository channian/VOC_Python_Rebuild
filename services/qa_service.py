"""
qa_service.py — QA 手測值輸入（移植舊版 EditQA.aspx）

只有資料來源為 QA 手測（VOC_SPEC.source = 3）的項目才能手動輸入讀值。
更新目標是 VOC_SCADA_WEB.rvalue + cdatetime，與 JOB 寫入 SCADA 值的方式一致，
首頁儀表板即可直接反映新讀值並重新計算燈號。
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from models.spec_model import VocScadaWeb
from models.acl_model import VocTranlog

QA_SOURCE_ID = 3


def list_qa_items(db: Session) -> list:
    """取得所有 QA 手測項目與目前讀值，供 qa_modal 表格顯示"""
    sql = text("""
        SELECT S.plantno, S.item, I.unit,
               S.OOS, S.OOC, S.alert,
               W.rvalue, W.cdatetime, W.broken
        FROM  [VOC].[dbo].[VOC_SPEC] S
        JOIN  [VOC].[dbo].[VOC_item] I ON S.item = I.item
        LEFT JOIN [VOC].[dbo].[VOC_SCADA_WEB] W
               ON S.plantno = W.plantno AND S.item = W.item
        WHERE S.source = :source_id
        ORDER BY S.plantno, S.seqno
    """)
    try:
        rows = db.execute(sql, {"source_id": QA_SOURCE_ID}).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[list_qa_items] DB 查詢失敗: {e}")
        return []


def update_qa_value(db: Session, current_user_empno: str,
                    plantno: str, item: str, rvalue: str, remark: str = "") -> bool:
    """
    更新單筆 QA 手測值。
    防呆：該 (plantno, item) 必須真的是 QA 來源，避免覆蓋 JOB 寫入的 SCADA 值。
    """
    try:
        check = db.execute(text("""
            SELECT 1 FROM [VOC].[dbo].[VOC_SPEC]
            WHERE plantno = :plantno AND item = :item AND source = :source_id
        """), {"plantno": plantno, "item": item, "source_id": QA_SOURCE_ID}).first()
        if not check:
            raise ValueError("此項目非 QA 手測來源，不可手動輸入!")

        web = db.query(VocScadaWeb).filter_by(plantno=plantno, item=item).first()
        old_value = web.rvalue if web else ""

        now = datetime.now()
        if web:
            web.rvalue = rvalue
            web.cdatetime = now
        else:
            db.add(VocScadaWeb(plantno=plantno, item=item,
                               rvalue=rvalue, cdatetime=now, broken=0))

        db.add(VocTranlog(
            empno=current_user_empno,
            logtype="M",
            databefore=f"QA手測 {plantno}/{item}: {old_value}",
            dataafter=f"QA手測 {plantno}/{item}: {rvalue}",
            cdatetime=now,
            remark=remark
        ))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"[update_qa_value] 更新失敗: {e}")
        raise e
