"""
services_b/report_service.py — 異常報表（Schema B 資料層版本）

對應 services/report_service.py（A/MSSQL 版：VOCreport，母集合 CTE + msg1 LIKE 統計）。
B 版資料層差異：查詢改直接對 mail_log_item.item 精確比對（取代 DT CTE + msg1 LIKE），
理由與 services_b/history_service.py 相同（D 項決策：mail_log_item 已正規化，
不再需要「先建母集合再 LIKE 比對」這道手續）。

彙整純函式（build_summary / build_pivot / build_ranking）與 A 版邏輯完全相同、
不依賴任何資料表形狀（只吃 [{"plantno":..,"item":..}] 這種通用列表），
因此直接 import 既有 services/report_service.py 重用，不重寫、不複製。

⚠️ 與 A 版刻意的差異範圍說明：A 版母集合刻意 UNION 雨水溝（見 services/report_service.py
頂端註解），本檔不需要另外處理這件事——B 版 mail_log_item.item 本來就是「這封信實際派報的
項目」（含雨水溝項目本身），沒有 A 版那種「先框出合法項目全集、再比對是否曾經派報過」的
兩階段設計，統計基礎與 A 版刻意擴大後的範圍一致（雨水溝相關派報一樣會被計入）。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import MailLog, MailLogItem
from services.report_service import build_summary, build_pivot, build_ranking  # noqa: F401
from services.history_service import default_date_range, validate_date_range  # noqa: F401


def _parse_ymd(s: str) -> datetime:
    return datetime.strptime(s.strip(), "%Y/%m/%d").replace(tzinfo=timezone.utc)


def query_report_data(db: Session, plant: str, item: str, sdate: str, edate: str, mt: bool) -> list[dict]:
    """
    查詢異常報表原始明細列（不在 SQL 端做統計，統計交給 build_summary / build_pivot / build_ranking）。
    對應 A 版 query_report_data()，B 版改直接查 mail_log_item（見本檔頂端說明）。
    """
    start = _parse_ymd(sdate)
    end = _parse_ymd(edate) + timedelta(days=1)

    stmt = (
        select(MailLog.plant_no, MailLogItem.item, MailLog.sent_at, MailLog.id)
        .join(MailLogItem, MailLogItem.mail_log_id == MailLog.id)
        .where(MailLog.sent_at >= start, MailLog.sent_at < end)
    )
    if plant:
        stmt = stmt.where(MailLog.plant_no == plant)
    if item:
        stmt = stmt.where(MailLogItem.item == item)
    if not mt:
        stmt = stmt.where(MailLogItem.is_maintenance.is_(False))
    stmt = stmt.order_by(MailLog.plant_no, MailLogItem.item, MailLog.sent_at)

    rows = db.execute(stmt).all()
    return [
        {
            "plantno": r.plant_no,
            "item": r.item,
            "cdatetime": r.sent_at.strftime("%Y/%m/%d %H:%M") if r.sent_at else "",
            "logid": r.id,
        }
        for r in rows
    ]
