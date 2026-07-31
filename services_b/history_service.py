"""
services_b/history_service.py — 異常記錄查詢 + 原因回覆（Schema B 資料層版本）

對應 services/history_service.py（A/MSSQL 版：VOChistory/VOCreason，msg1 LIKE 字串比對）。
B 版資料層差異（schema_B_設計提案.md D 項決策）：

  - VOC_MAIL_Log.msg1 LIKE '%|item|%' 字串比對 → 直接查 mail_log_item.item 精確比對
    （不需要 A 版的 DT CTE 母集合／msg2 LIKE 排除保養中：B 版每筆 mail_log_item 已經是
    正規化的「這封信、這個項目、這個條件」一列，is_maintenance 欄位直接標記，
    mt=False 對應 A 版 msg2 篩選，直接 filter is_maintenance=False 即可）。
  - reason/rdatetime/empno 回覆欄位：A 版與 msg/msg1 同一列（VOC_MAIL_Log 一列涵蓋多項目，
    一封信只能回覆一次、分不清是回覆哪個項目）。
    **2026-07-31 C8 使用者確認變更**：B 版回覆欄位改掛在 mail_log_item（逐項目回覆），
    不再共用 mail_log 一組回覆——同一封信底下的每個異常項目可以各自獨立回覆。
    改排水記錄（change='Y'）因為本來就沒有 mail_log_item 明細（非監測項目通知），
    這條路徑目前無法附掛逐項目回覆，reason/rdatetime/emp 固定回空字串（見
    `_list_change_water_log`；B 棧 UI 目前也未串接 change='Y' 查詢，此為已知限制）。
  - change='Y'（改排水記錄）：A 版用 msg LIKE '%改排水%' 且 item 留空。B 版沿用同樣精神，
    改查 mail_log.body_note LIKE '%改排水%' 且該封信沒有 mail_log_item 明細
    （warning_service 的改排水/水質異常通知走同一張 mail_log 但不寫 mail_log_item，
    因為那不是「監測項目」派報，語意對應 A 版 item=''）。
  - stype='雨水溝母集合' 的 DT CTE 在 B 版不需要：雨水溝項目本來就跟一般監測項目一樣
    存在 mail_log_item.item 欄位（item 名稱含「雨水溝」），直接查即可，不必另外 UNION。

沿用重用（禁止複製，皆為不依賴 DB 的純函式）：
  - services.history_service.default_date_range / validate_date_range / align_to_5min / classify_msg
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import MailLog, MailLogItem, Plant, Item, Spec, Employee
from services.history_service import (  # noqa: F401
    default_date_range,
    validate_date_range,
    align_to_5min,
    classify_msg,
)

logger = logging.getLogger(__name__)


def _parse_ymd(s: str) -> datetime:
    """把 'yyyy/MM/dd' 解析成當天 00:00:00（UTC-naive 比較用，DB 欄位為 timestamptz，
    SQLAlchemy/psycopg2 會處理時區轉換，這裡假設輸入為本地日界線，Phase A 測試環境足夠使用）。"""
    return datetime.strptime(s.strip(), "%Y/%m/%d").replace(tzinfo=timezone.utc)


# ── 下拉選單 ──────────────────────────────────────────────────────────────

def list_plants(db: Session) -> list[str]:
    """廠區清單（排除虛擬廠區/全廠）。"""
    rows = db.execute(
        select(Plant.plant_no).where(Plant.kind == "normal").order_by(Plant.sort)
    ).scalars().all()
    return list(rows)


def list_items(db: Session, plant: str = "") -> list[str]:
    """
    項目清單。有 plant 時取該廠 spec 中的項目（顯示名稱）；無 plant 時取全部有效項目顯示名稱。
    """
    if plant:
        stmt = (
            select(Item.display_name, Item.item)
            .join(Spec, Spec.item == Item.item)
            .where(Spec.plant_no == plant)
            .distinct()
        )
    else:
        stmt = (
            select(Item.display_name, Item.item)
            .where(Item.is_active.is_(True))
            .distinct()
        )
    rows = db.execute(stmt).all()
    names = sorted({(r.display_name or r.item) for r in rows})
    return names


# ── 異常記錄查詢 ──────────────────────────────────────────────────────────

def list_voclog(db: Session, plant: str = "", item: str = "", sdate: str = "", edate: str = "",
                 mt: bool = True, stime: str = "", stype: str = "", change: str = "") -> list[dict]:
    """
    對應 A 版 list_voclog()。change='Y' 走改排水記錄（mail_log 無明細的通知列）；
    其餘走一般監測項目查詢（mail_log_item 精確比對，取代 msg1 LIKE）。
    """
    if change == "Y":
        return _list_change_water_log(db, plant, sdate, edate, stime)
    return _list_item_log(db, plant, item, sdate, edate, mt, stime)


def _time_bounds(sdate: str, edate: str, stime: str) -> tuple[datetime, datetime]:
    if stime:
        dt0 = datetime.strptime(stime.strip(), "%Y/%m/%d %H:%M").replace(tzinfo=timezone.utc)
        return dt0, dt0 + timedelta(minutes=1)
    start = _parse_ymd(sdate)
    end = _parse_ymd(edate) + timedelta(days=1)
    return start, end


def _make_item_id(mail_log_id: int, item: str, condition_code: str) -> str:
    """組出逐項目回覆用的複合鍵字串（mail_log_item 為 (mail_log_id, item, condition_code)
    複合主鍵，前端/API 一律用這組字串當作單一識別碼，不需要理解複合鍵細節）。"""
    return f"{mail_log_id}||{item}||{condition_code}"


def _parse_item_id(item_id: str) -> tuple[int, str, str]:
    parts = item_id.split("||", 2)
    if len(parts) != 3:
        raise ValueError(f"item_id 格式錯誤：{item_id!r}")
    mail_log_id_str, item, condition_code = parts
    try:
        mail_log_id = int(mail_log_id_str)
    except ValueError:
        raise ValueError(f"item_id 格式錯誤：{item_id!r}")
    return mail_log_id, item, condition_code


def _emp_label(db: Session, empno: str | None) -> str:
    if not empno:
        return ""
    emp = db.execute(select(Employee).where(Employee.emp_no == empno)).scalar_one_or_none()
    if not emp:
        return empno
    return f"{emp.emp_name or ''}/{emp.notes_id or ''}"


def _list_item_log(db: Session, plant: str, item: str, sdate: str, edate: str,
                    mt: bool, stime: str) -> list[dict]:
    start, end = _time_bounds(sdate, edate, stime)

    stmt = (
        select(MailLog, MailLogItem)
        .join(MailLogItem, MailLogItem.mail_log_id == MailLog.id)
        .where(MailLog.sent_at >= start, MailLog.sent_at < end)
    )
    if plant:
        stmt = stmt.where(MailLog.plant_no == plant)
    if item:
        stmt = stmt.where(MailLogItem.item == item)
    if not mt:
        # 對應 A 版 msg2 篩選：排除保養中項目
        stmt = stmt.where(MailLogItem.is_maintenance.is_(False))
    stmt = stmt.order_by(MailLog.sent_at)

    rows = db.execute(stmt).all()
    result = []
    for idx, (log, li) in enumerate(rows, start=1):
        result.append({
            "no": idx,
            "plantno": log.plant_no,
            "item": li.item,
            "cdatetime": log.sent_at.strftime("%Y/%m/%d %H:%M") if log.sent_at else "",
            "msg": log.body_note or li.detail or "",
            # C8：回覆改成逐項目（掛在 mail_log_item，不再共用 mail_log 一組回覆）
            "emp": _emp_label(db, li.reply_empno),
            "reason": li.reply_reason or "",
            "rdatetime": li.reply_at.strftime("%Y/%m/%d %H:%M") if li.reply_at else "",
            "logid": log.id,
            "item_id": _make_item_id(li.mail_log_id, li.item, li.condition_code),
            "msg1": li.detail or "",
        })
    return result


def _list_change_water_log(db: Session, plant: str, sdate: str, edate: str, stime: str) -> list[dict]:
    """改排水記錄：mail_log.body_note 含「改排水」且無 mail_log_item 明細（非監測項目通知）。"""
    start, end = _time_bounds(sdate, edate, stime)
    stmt = (
        select(MailLog)
        .where(MailLog.sent_at >= start, MailLog.sent_at < end, MailLog.body_note.contains("改排水"))
    )
    if plant:
        stmt = stmt.where(MailLog.plant_no == plant)
    stmt = stmt.order_by(MailLog.sent_at)

    logs = db.execute(stmt).scalars().all()
    result = []
    for idx, log in enumerate(logs, start=1):
        result.append({
            "no": idx,
            "plantno": log.plant_no,
            "item": "",
            "cdatetime": log.sent_at.strftime("%Y/%m/%d %H:%M") if log.sent_at else "",
            "msg": log.body_note or "",
            # 改排水通知沒有 mail_log_item 明細可掛回覆，逐項目回覆功能對這條路徑無法套用
            # （見檔頭說明；B 棧 UI 目前也未串接 change='Y' 查詢，屬已知限制）。
            "emp": "",
            "reason": "",
            "rdatetime": "",
            "logid": log.id,
            "item_id": "",
            "msg1": log.body_note or "",
        })
    return result


def update_reason(db: Session, item_id: str, reason: str, current_user_empno: str) -> None:
    """儲存異常原因回覆（逐項目，2026-07-31 C8）。

    對應 A 版 update_reason()，但 B 版改成以 mail_log_item 複合主鍵
    (mail_log_id, item, condition_code) 為單位回覆，不再是整封信共用一組回覆。
    `item_id` 是 `_make_item_id()` 組出的複合鍵字串，由 `list_voclog()` 回傳的每一列帶出，
    前端原樣送回即可，不需要理解複合鍵細節。
    """
    mail_log_id, item, condition_code = _parse_item_id(item_id)
    li = db.execute(
        select(MailLogItem).where(
            MailLogItem.mail_log_id == mail_log_id,
            MailLogItem.item == item,
            MailLogItem.condition_code == condition_code,
        )
    ).scalar_one_or_none()
    if not li:
        raise ValueError(f"找不到派報項目紀錄 item_id={item_id!r}")
    li.reply_empno = current_user_empno
    li.reply_reason = reason.strip()
    li.reply_at = datetime.now(timezone.utc)
    db.commit()
