"""
warning_service.py — 雨水溝預警 + 中水緊急通知（WaterUrgent 移植）

依 legacy/WaterUrgent.aspx.cs + legacy/dbVOC.cs 精讀重寫，相關方法：
  GetData水質廠區(type)   — 中水示警可通知廠區清單（type=1 排除 K14B 自己，改排水用）
  GetData水質異常(cdatetime) — K14B 中水水質異常項目最新讀值（OOS/OOC/現值）
  List改排水原因()        — 改排水原因下拉（VOC_reason 主檔）
  GetMailList / GetCellPhoneList — 收件人名單（本檔只做 Email，SM 簡訊已確認不移植）
  SendMail_水質異常通知() — 人工按鈕：對每個有 SCADA Tag 的廠區各發一封「請回覆水質狀況」信
  SendMail_改排水通知()   — 人工按鈕：對勾選廠區發「改排水，請回覆處理狀況」信，並額外 CC K14B

⚠️ 與舊版刻意差異：
  - GetMailList 若 mailto 為空，舊版 SendMail_* 直接 return false（中止該次通知）；
    這裡只跳過該廠（continue），不中止其他廠區的通知（避免忠實重現舊系統的隱藏 bug，
    詳見 docs/legacy_source_analysis.md「JOB 派報流程完整還原」第 6 點）。
  - SMS 簡訊派送已於 2026-06-11 與使用者確認不移植，本檔只保留 Email 邏輯。

依 CLAUDE.md 規則：DB 查詢失敗一律 raise + log，不回傳假資料掩蓋錯誤
（原本 get_raingutter_list/get_current_anomalies 的 mock fallback 已移除）。
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from datetime import datetime, timedelta
import logging

from fastapi import BackgroundTasks

from schemas.warning_schema import RainGutterItem, WaterUrgentRequest
from services.notify_service import add_notification_task
# 只 import maillist_service 既有函式（notesid 雙向轉換），不修改該檔
from services.maillist_service import notesid_to_email

logger = logging.getLogger(__name__)

# CC 寄信時，除指定廠區外固定納入的集團監督單位（比照 dbVOC.cs GetMailList 的 CC 規則）
_CC_EXTRA_PLANTS = ("GMO", "環工部")

# 中水水質異常/改排水通知固定的報表類型（舊版 GetMailList("水質異常", plantno, ...) 硬寫死）
WATER_RPTTYPE = "水質異常"

# K14B：中水放流廠區代號，改排水通知額外 CC 名單、水質異常讀值固定來源
K14B = "K14B"


def get_raingutter_list(db: Session) -> List[RainGutterItem]:
    """
    移植 dbVOC.List雨水溝預警() 與 RainGutter.aspx.cs GetData雨水溝() 的燈號判斷邏輯。
    DB 查詢失敗一律往上拋出，不再回傳假資料掩蓋錯誤（CLAUDE.md 要求）。
    """
    sql = text("SELECT plantno, item, sum24h, rvalue, remark FROM VOC_raingutter")
    try:
        result = db.execute(sql).mappings().all()
    except Exception as e:
        logger.error(f"[get_raingutter_list] DB 查詢失敗: {e}")
        raise

    out = []
    for row in result:
        s24h = row['sum24h'] or '0.0'
        rval = row['rvalue'] or '異常'

        # 燈號邏輯: 紅燈條件：最新讀值=1 且 24H累積雨量=0
        # 橘燈條件：斷訊 或 異常
        # 綠燈條件：正常狀態
        status = 'G'
        if s24h == "0.0" and rval == "1":
            status = 'R'
        elif rval in ["斷訊", "異常"] or (s24h == "異常" and rval == "1"):
            status = 'O'

        out.append(RainGutterItem(
            plantno=row['plantno'],
            item=row['item'],
            sum24h=str(s24h),
            rvalue=str(rval),
            status=status,
            remark=row['remark'] or ''
        ))
    return out


def get_current_anomalies(db: Session) -> list:
    """
    取得目前儀表板上紅燈／橙燈的項目，供預警紀錄 Modal 顯示。
    直接讀 VOC_SCADA_WEB.light 欄位（JOB 寫入），無需重跑燈號計算
    （CLAUDE.md 不可違反的技術決策 #1 的例外情形）。
    DB 查詢失敗一律往上拋出，不再回傳空清單掩蓋錯誤。
    """
    sql = text("""
        SELECT W.plantno,
               REPLACE(REPLACE(W.item, 'COD2', 'COD'), 'pH1', 'pH') AS item,
               W.rvalue, W.cdatetime, W.light
        FROM  [VOC].[dbo].[VOC_SCADA_WEB] W
        JOIN  [VOC].[dbo].[VOC_plant]     P ON W.plantno = P.plantno AND P.isShow = 1
        WHERE W.light IN ('R', 'O')
          AND (W.broken IS NULL OR W.broken = 0)
        ORDER BY W.light, P.sort, W.item
    """)
    try:
        rows = db.execute(sql).mappings().all()
    except Exception as e:
        logger.error(f"[get_current_anomalies] DB 查詢失敗: {e}")
        raise
    return [dict(r) for r in rows]


# ── 中水緊急通知收件名單 WHERE 組裝（純函式，比照 maillist_service.build_maillist_where）──

def build_water_mail_where(plantno: str, mailtype: str, rpttype: str = WATER_RPTTYPE) -> tuple[str, dict]:
    """
    組中水緊急通知收件人的 WHERE 子句（參數化，取代舊版 dbVOC.cs GetMailList 的字串拼接）。
    對應 GetMailList(sRed, plantno, MailType)，中水通知的 sRed 固定為單一報表類型「水質異常」。

    TO：嚴格 (rpttype = 水質異常 AND plantno = 指定廠)。
    CC：rpttype = 水質異常 AND plantno IN (指定廠, GMO, 環工部)。
    回傳 (where_sql, params)。
    """
    params: dict = {"mailtype": mailtype, "rpttype": rpttype, "plantno": plantno}
    if mailtype == "TO":
        where = ("MailType = :mailtype AND NotesID != '' AND Mail = 1 "
                 "AND rpttype = :rpttype AND plantno = :plantno")
    else:  # CC
        plant_keys = []
        for i, p in enumerate(_CC_EXTRA_PLANTS):
            params[f"pl{i}"] = p
            plant_keys.append(f":pl{i}")
        plant_in = ", ".join([":plantno"] + plant_keys)
        where = ("MailType = :mailtype AND NotesID != '' AND Mail = 1 "
                 f"AND rpttype = :rpttype AND plantno IN ({plant_in})")
    return where, params


def get_water_mail_recipients(db: Session, plantno: str, mailtype: str = "TO",
                               rpttype: str = WATER_RPTTYPE) -> list[str]:
    """
    取得中水緊急通知收件 Email 清單（NotesID → email 還原）。
    對應舊版 GetMailList(sRed, plantno, MailType)。DB 查詢失敗一律往上拋出。
    """
    where, params = build_water_mail_where(plantno, mailtype, rpttype)
    sql = text(f"SELECT DISTINCT NotesID FROM [VOC].[dbo].[VOC_Mail_List] WHERE {where}")
    try:
        rows = db.execute(sql, params).mappings().all()
    except Exception as e:
        logger.error(f"[get_water_mail_recipients] DB 查詢失敗: {e}")
        raise
    return [notesid_to_email(r["NotesID"]) for r in rows if r["NotesID"]]


# ── 中水示警查詢（舊版 GetData水質廠區 / List改排水原因 / GetData水質異常）──────

def get_water_plants(db: Session, exclude_k14b: bool = False) -> list[dict]:
    """
    中水示警可通知廠區清單（舊版 GetData水質廠區(type)）。
    exclude_k14b=True 對應 type=1（改排水通知廠區選單，排除 K14B 自己）。
    """
    sql = ("SELECT DISTINCT plantid, P.plantno FROM [VOC].[dbo].[VOC_SCADA_Tag] T "
           "JOIN [VOC].[dbo].[VOC_plant] P ON T.plantno = P.plantno ")
    params: dict = {}
    if exclude_k14b:
        sql += "WHERE T.plantno != :k14b "
        params["k14b"] = K14B
    sql += "ORDER BY plantid"
    try:
        rows = db.execute(text(sql), params).mappings().all()
    except Exception as e:
        logger.error(f"[get_water_plants] DB 查詢失敗: {e}")
        raise
    return [dict(r) for r in rows]


def list_change_reasons(db: Session) -> list[dict]:
    """改排水原因下拉選單（舊版 List改排水原因，VOC_reason 主檔）。"""
    try:
        rows = db.execute(text(
            "SELECT reasonid, reason FROM [VOC].[dbo].[VOC_reason]"
        )).mappings().all()
    except Exception as e:
        logger.error(f"[list_change_reasons] DB 查詢失敗: {e}")
        raise
    return [dict(r) for r in rows]


def get_water_abnormal_readings(db: Session, cdatetime: datetime) -> list[dict]:
    """
    K14B 中水水質異常項目最新讀值（舊版 GetData水質異常(DateTime)）。
    item 別名映射：COD/COD1→COD2，pH/pH2→pH1（比對 VOC_SPEC.item），舊版固定只查 K14B。
    """
    sql = text("""
        SELECT T.plantno, T.item, S.OOS, S.OOC, T.CurrentValue AS cValue
        FROM [VOC].[dbo].[VOC_SCADA_Tag] T
        JOIN [VOC].[dbo].[VOC_SPEC] S
          ON T.plantno = S.plantno
         AND (CASE T.item
                WHEN 'COD' THEN 'COD2' WHEN 'COD1' THEN 'COD2'
                WHEN 'pH'  THEN 'pH1'  WHEN 'pH2'  THEN 'pH1'
                ELSE T.item END) = S.item
        WHERE T.plantno = :k14b AND T.item NOT IN ('流量1', '流量2')
          AND T.cdatetime = :cdatetime
        ORDER BY T.item
    """)
    try:
        rows = db.execute(sql, {"k14b": K14B, "cdatetime": cdatetime}).mappings().all()
    except Exception as e:
        logger.error(f"[get_water_abnormal_readings] DB 查詢失敗: {e}")
        raise
    return [dict(r) for r in rows]


def _insert_mail_log(db: Session, plantno: str, msg: str, msg1: str,
                      cdatetime: datetime, msg2: str = "") -> None:
    """寫入 VOC_MAIL_Log（舊版 InsertMAIL），msg2 為空字串時不寫入該欄位。"""
    if msg2 == "":
        sql = text("""INSERT INTO [VOC].[dbo].[VOC_MAIL_Log] ([plantno],[cdatetime],[msg],[msg1])
                       VALUES (:plantno,:cdatetime,:msg,:msg1)""")
        params = {"plantno": plantno, "cdatetime": cdatetime, "msg": msg, "msg1": msg1}
    else:
        sql = text("""INSERT INTO [VOC].[dbo].[VOC_MAIL_Log] ([plantno],[cdatetime],[msg],[msg1],[msg2])
                       VALUES (:plantno,:cdatetime,:msg,:msg1,:msg2)""")
        params = {"plantno": plantno, "cdatetime": cdatetime, "msg": msg, "msg1": msg1, "msg2": msg2}
    db.execute(sql, params)


def _water_reading_table_html(readings: list[dict]) -> str:
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


def trigger_water_abnormal_notify(db: Session, bg_tasks: BackgroundTasks,
                                   cdatetime: datetime = None) -> bool:
    """
    中水水質異常通知（舊版 SendMail_水質異常通知，WaterUrgent.aspx「水質異常通知確定」按鈕）。

    人工按鈕觸發：對每個有 SCADA Tag 的廠區各發一封「請回覆水質狀況」信，內容固定為 K14B
    中水水質異常讀值（GetData水質異常 查詢固定 plantno='K14B'，這是舊系統既有行為，
    代表中水放流水質異常時要通知所有使用該中水的廠區回覆狀況，非本次移植新增的邏輯）。

    回傳 True 表示至少寄出一封，False 表示目前無異常讀值（不寄信，非錯誤）。
    """
    cdatetime = cdatetime or (datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=1))
    readings = get_water_abnormal_readings(db, cdatetime)
    if not readings:
        return False

    plants = get_water_plants(db, exclude_k14b=False)
    dt_str = cdatetime.strftime("%Y/%m/%d %H:%M")

    msg = msg1 = "中水水質異常，項目最新讀值-"
    for r in readings:
        msg += f"{r['item']}：{r['cValue']}；"
        msg1 += f"|{r['item']}|：{r['cValue']}；"
    table_html = _water_reading_table_html(readings)

    sent_any = False
    for row in plants:
        plantno = row["plantno"]
        mailto = get_water_mail_recipients(db, plantno, "TO")
        mailcc = get_water_mail_recipients(db, plantno, "CC")
        if not mailto:
            # Python 版修正：沒有收件人時跳過該廠，不像舊系統直接 return 中止整個迴圈
            logger.warning(f"[trigger_water_abnormal_notify] {plantno} 無收件人，略過")
            continue

        body = (f"<html><body>Dear Sir,<br/>您好, <b style='color:red'>中水水質異常</b>, "
                f"請回覆您所負責的 {plantno} 目前水質狀況, 謝謝!<br/><br/>{table_html}</body></html>")
        subj = f"請確認「法遵平台-中水放流管制」即時監控狀況 : {plantno}-{dt_str} (Security C)"
        add_notification_task(bg_tasks, subj, body, emails=mailto + mailcc)

        _insert_mail_log(db, plantno, msg, msg1, cdatetime, msg1)
        sent_any = True

    db.commit()
    return sent_any


def trigger_water_change_notify(db: Session, bg_tasks: BackgroundTasks,
                                 plantnos: list[str], reason: str,
                                 cdatetime: datetime = None) -> bool:
    """
    改排水通知（舊版 SendMail_改排水通知，WaterUrgent.aspx「改排水通知確定」按鈕）。

    人工勾選異常廠區 + 填改排水原因，逐廠寄送「請回覆處理狀況」信，並額外把 K14B
    「水質異常」TO 名單 CC 進去（舊系統既有規則：改排水一定要通知 K14B）。

    回傳 True 表示至少寄出一封，False 表示勾選的廠區都查無收件人（不寄信，非錯誤）。
    """
    if not plantnos:
        raise ValueError("請選擇廠區!")
    if not reason or not reason.strip():
        raise ValueError("請輸入改排水原因!")
    reason = reason.strip()

    cdatetime = cdatetime or datetime.now().replace(second=0, microsecond=0)
    dt_str = cdatetime.strftime("%Y/%m/%d %H:%M")

    sent_any = False
    for plantno in plantnos:
        mailto = get_water_mail_recipients(db, plantno, "TO")
        mailcc = get_water_mail_recipients(db, plantno, "CC")
        mailcc = mailcc + get_water_mail_recipients(db, K14B, "TO")  # 舊系統：改排水一定額外 CC K14B
        if not mailto:
            logger.warning(f"[trigger_water_change_notify] {plantno} 無收件人，略過")
            continue

        msg = msg1 = f"改排水原因：{reason}"
        body = (f"<html><body>Dear Sir,<br/>您好, 改排水原因：<b style='color:red'>{reason}</b><br/><br/>"
                f"請回覆您所負責的 {plantno} 處理狀況, 謝謝!</body></html>")
        subj = f"請確認「法遵平台-中水放流管制」即時監控狀況 : {plantno}-{dt_str} (Security C)"
        add_notification_task(bg_tasks, subj, body, emails=mailto + mailcc)

        _insert_mail_log(db, plantno, msg, msg1, cdatetime, msg1)
        sent_any = True

    db.commit()
    return sent_any


def trigger_water_notify(db: Session, req: WaterUrgentRequest, bg_tasks: BackgroundTasks) -> bool:
    """
    人工觸發中水緊急通知的統一入口，對應 WaterUrgent.aspx 兩個確定按鈕。
    寄信經 notify_service.add_notification_task 送出，TEST_MODE 由該函式內部保護。
    """
    if req.notify_type == "water_abnormal":
        return trigger_water_abnormal_notify(db, bg_tasks)
    elif req.notify_type == "water_change":
        return trigger_water_change_notify(db, bg_tasks, req.plantnos, req.reason)
    else:
        raise ValueError("不支援的通知類型")
