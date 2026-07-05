"""
services_b/warning_service.py — 雨水溝預警 + 中水緊急通知（Schema B 資料層版本）

對應 services/warning_service.py（A/MSSQL 版：WaterUrgent.aspx + VOC_raingutter/VOC_SCADA_Tag/
VOC_reason 等表）。

⚠️ **models_b.py 已凍結，B 架構未建下列 A 版專用表**（超出 WP5 權限範圍，不可自行加表，
以下功能改用既有 B 表做「同精神、簡化版」實作，並在各函式註解標明差異，
待主控評估是否要為這些表補設計）：
  - VOC_raingutter（雨水溝專用表）→ 改用 reading_current + spec，篩 item 含「雨水溝」的列。
  - VOC_SCADA_Tag（水質廠區可通知清單、K14B 讀值來源）→ 無對應表：
      get_water_plants() 改用「該廠區在 mail_list 有登記水質異常(TO)收件人」作為可通知廠區的
      判斷依據（語意相近：能收到水質異常信的廠區，才有意義被列入可勾選通知名單）。
      get_water_abnormal_readings() 改用 spec ⋈ reading_current（K14B、排除流量類項目）
      取「目前最新讀值」，不再要求 cdatetime 完全相等（這正是 PhaseA執行規格書 第二節
      指出的 PMS 時間戳完全相等脆弱點，B 版直接改用最新一筆，避免同樣的靜默漏顯示問題）。
  - VOC_reason（改排水原因下拉主檔）→ 無對應表：list_change_reasons() 改讀
      system_config['water_change_reasons']（逗號分隔字串，未種子時回傳保守的預設清單），
      **待主控裁決**是否要新增 reason 主檔或改用其他來源。

沿用重用（禁止複製）：
  - schemas.warning_schema.RainGutterItem / WaterUrgentRequest（不依賴 DB 的 pydantic 驗證）。
  - services.maillist_service.notesid_to_email（純函式）——本檔透過 services_b.maillist_service
    取得收件人清單，不重複寫 SQL。
  - services.notify_service.send_email_sync（SMTP 寄信 + TEST_MODE 攔截，完全不重寫）。
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import Spec, ReadingCurrent, MailLog, MailList
from schemas.warning_schema import RainGutterItem, WaterUrgentRequest  # noqa: F401
from services.notify_service import add_notification_task
from services_b.maillist_service import get_mail_recipients

logger = logging.getLogger(__name__)

# 中水放流廠區代號（改排水通知額外 CC 名單、水質異常讀值固定來源），對應 A 版 K14B 常數
K14B = "K14B"
WATER_RPTTYPE = "水質異常"
_SYSTEM_CONFIG_REASONS_KEY = "water_change_reasons"
_DEFAULT_CHANGE_REASONS = ["設備維修", "製程調整", "上游異常排放", "其他"]


# ── 雨水溝預警（VOC_raingutter 簡化版：改讀 reading_current + spec）───────────

def get_raingutter_list(db: Session) -> List[RainGutterItem]:
    """
    雨水溝預警清單（B 簡化版）。篩選 spec.item 含「雨水溝」的項目，讀 reading_current 的
    value（對應 A 版 rvalue：1=異常訊號）與 rain_24h（對應 24H 累積雨量）。

    燈號規則沿用 A 版精神：
      紅燈：value=1 且 rain_24h=0（雨量降到 0 但訊號仍顯示異常，代表確定溢流）
      橙燈：comm_ok=False（斷訊）或 status 非 normal（異常/建置中等）
      綠燈：其餘（含 value!=1，代表正常狀態）
    """
    stmt = (
        select(Spec.plant_no, Spec.item, ReadingCurrent)
        .join(ReadingCurrent, (ReadingCurrent.plant_no == Spec.plant_no) & (ReadingCurrent.item == Spec.item))
        .where(Spec.item.contains("雨水溝"))
    )
    try:
        rows = db.execute(stmt).all()
    except Exception as e:
        logger.error(f"[get_raingutter_list] DB 查詢失敗: {e}")
        raise

    out = []
    for plant_no, item, rc in rows:
        s24h = str(rc.rain_24h) if rc.rain_24h is not None else "0.0"
        rval = str(rc.value) if rc.value is not None else (rc.raw_text or "異常")

        status = "G"
        if not rc.comm_ok or rc.status not in ("normal",):
            status = "O"
        if s24h in ("0", "0.0") and rval == "1":
            status = "R"

        out.append(RainGutterItem(
            plantno=plant_no, item=item, sum24h=s24h, rvalue=rval, status=status,
            remark=rc.raw_text or "",
        ))
    return out


# ── 目前紅/橙燈清單（B 版：燈號從不落地，必須即時算，取代 A 版讀 light 欄位捷徑）──

def get_current_anomalies(db: Session, isolation_checker=None) -> list[dict]:
    """
    取得目前儀表板上紅燈／橙燈的項目，供預警紀錄 Modal 顯示。

    ⚠️ 與 A 版的關鍵差異：A 版可以直接讀 VOC_SCADA_WEB.light 欄位做快速篩選（CLAUDE.md
    允許 get_current_anomalies 的唯一例外）；B 版 schema 根本沒有 light 欄位（燈號不落地是
    B 架構的既定決策，不只是「不建議讀」而是「無處可讀」），因此本函式改呼叫
    services_b.dashboard_service.get_dashboard_rows() 即時算完整燈號後，在 Python 端篩選
    light_status in ('R','O')，語意等價但改成應用層計算。
    """
    from services_b.dashboard_service import get_dashboard_rows

    rows = get_dashboard_rows(db, isolation_checker=isolation_checker)
    return [
        {
            "plantno": r.plantno, "item": r.item, "rvalue": r.rvalue_raw,
            "cdatetime": "", "light": r.light_status,
        }
        for r in rows if r.light_status in ("R", "O")
    ]


# ── 中水示警查詢（VOC_SCADA_Tag / VOC_reason 簡化版）─────────────────────────

def get_water_plants(db: Session, exclude_k14b: bool = False) -> List[dict]:
    """
    中水示警可通知廠區清單（B 簡化版：改用「該廠有登記水質異常(TO)收件人」判斷可通知廠區，
    見本檔頂端說明——VOC_SCADA_Tag 無 B 版對應表）。
    """
    stmt = select(MailList.plant_no).where(
        MailList.rpttype == WATER_RPTTYPE, MailList.mail_type == "TO"
    ).distinct()
    if exclude_k14b:
        stmt = stmt.where(MailList.plant_no != K14B)
    try:
        rows = db.execute(stmt).scalars().all()
    except Exception as e:
        logger.error(f"[get_water_plants] DB 查詢失敗: {e}")
        raise
    return [{"plantno": p} for p in rows]


def list_change_reasons(db: Session) -> List[dict]:
    """
    改排水原因下拉選單（B 簡化版：VOC_reason 無 B 版對應表，改讀
    system_config['water_change_reasons']，逗號分隔；未種子時回傳保守預設清單。
    **待主控裁決**是否要為改排水原因建立正式主檔。
    """
    from models_b import SystemConfig
    row = db.execute(select(SystemConfig.value).where(SystemConfig.key == _SYSTEM_CONFIG_REASONS_KEY)).scalar_one_or_none()
    reasons = [r.strip() for r in row.split(",")] if row else _DEFAULT_CHANGE_REASONS
    return [{"reasonid": i + 1, "reason": r} for i, r in enumerate(reasons) if r]


def get_water_abnormal_readings(db: Session, cdatetime: Optional[datetime] = None) -> List[dict]:
    """
    K14B 中水水質異常項目最新讀值（B 簡化版：取 reading_current 目前最新值，不要求
    cdatetime 完全相等——這正是修正 A 版 PMS 時間戳脆弱點的精神，見本檔頂端說明）。
    排除流量類項目（item 含「流量」）。
    """
    stmt = (
        select(Spec.item, Spec.oos_high, Spec.ooc_high, ReadingCurrent)
        .join(ReadingCurrent, (ReadingCurrent.plant_no == Spec.plant_no) & (ReadingCurrent.item == Spec.item))
        .where(Spec.plant_no == K14B, ~Spec.item.contains("流量"))
        .order_by(Spec.item)
    )
    try:
        rows = db.execute(stmt).all()
    except Exception as e:
        logger.error(f"[get_water_abnormal_readings] DB 查詢失敗: {e}")
        raise
    return [
        {
            "plantno": K14B, "item": it, "OOS": oos_high, "OOC": ooc_high,
            "cValue": (rc.value if rc.value is not None else (rc.raw_text or "")),
        }
        for it, oos_high, ooc_high, rc in rows
    ]


def _water_reading_table_html(readings: List[dict]) -> str:
    rows_html = "".join(
        f"<tr><td style='text-align:center'>{r['item']}</td>"
        f"<td style='text-align:center'>{r['OOS']}</td>"
        f"<td style='text-align:center'>{r['OOC']}</td>"
        f"<td style='text-align:center'>{r['cValue']}</td></tr>"
        for r in readings
    )
    return (f"<table style='border:1px solid black' width='450px'>"
            f"<tr style='background-color:#CCFFFF;font-weight:bold;'>"
            f"<td style='text-align:center'>項目</td><td style='text-align:center'>OOS</td>"
            f"<td style='text-align:center'>OOC</td><td style='text-align:center'>最新讀值</td></tr>"
            f"{rows_html}</table>")


def _insert_mail_log(db: Session, plantno: str, msg: str, cdatetime: datetime) -> None:
    """寫入 mail_log（不含 mail_log_item，語意同 A 版改排水/水質異常通知的「無項目」通知）。"""
    db.add(MailLog(plant_no=plantno, sent_at=cdatetime, subject=msg[:200], body_note=msg))


def trigger_water_abnormal_notify(db: Session, bg_tasks: BackgroundTasks,
                                   cdatetime: Optional[datetime] = None) -> bool:
    """中水水質異常通知（B 版：對每個已登記水質異常收件人的廠區各發一封）。"""
    cdatetime = cdatetime or datetime.now(timezone.utc)
    readings = get_water_abnormal_readings(db, cdatetime)
    if not readings:
        return False

    plants = get_water_plants(db, exclude_k14b=False)
    dt_str = cdatetime.strftime("%Y/%m/%d %H:%M")

    msg = "中水水質異常，項目最新讀值-"
    for r in readings:
        msg += f"{r['item']}：{r['cValue']}；"
    table_html = _water_reading_table_html(readings)

    sent_any = False
    for row in plants:
        plantno = row["plantno"]
        mailto = get_mail_recipients(db, WATER_RPTTYPE, plantno, "TO")
        mailcc = get_mail_recipients(db, WATER_RPTTYPE, plantno, "CC")
        if not mailto:
            logger.warning(f"[trigger_water_abnormal_notify] {plantno} 無收件人，略過")
            continue

        body = (f"<html><body>Dear Sir,<br/>您好, <b style='color:red'>中水水質異常</b>, "
                f"請回覆您所負責的 {plantno} 目前水質狀況, 謝謝!<br/><br/>{table_html}</body></html>")
        subj = f"請確認「法遵平台-中水放流管制」即時監控狀況 : {plantno}-{dt_str} (Security C)"
        add_notification_task(bg_tasks, subj, body, emails=mailto + mailcc)

        _insert_mail_log(db, plantno, msg, cdatetime)
        sent_any = True

    db.commit()
    return sent_any


def trigger_water_change_notify(db: Session, bg_tasks: BackgroundTasks, plantnos: List[str],
                                 reason: str, cdatetime: Optional[datetime] = None) -> bool:
    """改排水通知（B 版：額外把 K14B 水質異常 TO 名單併入 CC，語意同 A 版）。"""
    if not plantnos:
        raise ValueError("請選擇廠區!")
    if not reason or not reason.strip():
        raise ValueError("請輸入改排水原因!")
    reason = reason.strip()

    cdatetime = cdatetime or datetime.now(timezone.utc)
    dt_str = cdatetime.strftime("%Y/%m/%d %H:%M")

    sent_any = False
    for plantno in plantnos:
        mailto = get_mail_recipients(db, WATER_RPTTYPE, plantno, "TO")
        mailcc = get_mail_recipients(db, WATER_RPTTYPE, plantno, "CC")
        mailcc = mailcc + get_mail_recipients(db, WATER_RPTTYPE, K14B, "TO")
        if not mailto:
            logger.warning(f"[trigger_water_change_notify] {plantno} 無收件人，略過")
            continue

        msg = f"改排水原因：{reason}"
        body = (f"<html><body>Dear Sir,<br/>您好, 改排水原因：<b style='color:red'>{reason}</b><br/><br/>"
                f"請回覆您所負責的 {plantno} 處理狀況, 謝謝!</body></html>")
        subj = f"請確認「法遵平台-中水放流管制」即時監控狀況 : {plantno}-{dt_str} (Security C)"
        add_notification_task(bg_tasks, subj, body, emails=mailto + mailcc)

        _insert_mail_log(db, plantno, msg, cdatetime)
        sent_any = True

    db.commit()
    return sent_any


def trigger_water_notify(db: Session, req: WaterUrgentRequest, bg_tasks: BackgroundTasks) -> bool:
    """人工觸發中水緊急通知的統一入口，對應 WaterUrgent.aspx 兩個確定按鈕。"""
    if req.notify_type == "water_abnormal":
        return trigger_water_abnormal_notify(db, bg_tasks)
    elif req.notify_type == "water_change":
        return trigger_water_change_notify(db, bg_tasks, req.plantnos, req.reason)
    else:
        raise ValueError("不支援的通知類型")
