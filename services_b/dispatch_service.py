"""
services_b/dispatch_service.py — 異常 Email 派報（Schema B 資料層版本，WP5 核心）

對應 services/dispatch_service.py（A/MSSQL 版：Job.dbVOC.GetDataRed + Job.SendMail）。
evaluate_row()（GetDataRed 的純函式版本）**零修改重用**，本檔只做兩件事：

  1. get_data_b()：把 B 新形狀（spec 數值欄 + reading_current value/status）轉成
     evaluate_row() 期待的舊字串形狀（oos/ooc/alert_spec/recv/scada_*/cwms_* 字串門檻、
     rvalue_raw/rvalue/broken）。轉接函式直接 import services_b.dashboard_service 的
     _bounds_to_str/_reading_raw_and_broken/_rvalue_numeric_string，與儀表板燈號同源，
     確保「派報判斷」與「畫面顯示」永遠一致。
  2. get_prev_mail()：把 mail_log_item 明細列轉成 evaluate_row 期待的 prev_mail 形狀
     {'cdatetime':.., 'msg1':..}（設計細節見函式註解）。

隔離判定 import services_b.control_service.is_item_isolated；若該模組尚未完成（ImportError），
退化成「永遠非隔離中」並記 log warning，不阻擋本檔案獨立運作（呼叫端也可用 isolation_checker
參數注入真正的判斷函式，優先權高於預設 import）。

D 項決策落地：mail_log（信件層級）＋ mail_log_item（每項目一列）取代 A 版 msg1/msg2 LIKE 比對。
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import Spec, ReadingCurrent, Plant, Item, MailLog, MailLogItem
from services.dispatch_service import (
    DispatchResult,
    evaluate_row,
    build_plant_msg,
    build_plant_msg2,
    plant_is_first,
    build_subject,
    render_dispatch_email,
    _rpttypes_for_plant,
    _row_to_html_dict,
)
from services.notify_service import send_email_sync
from services_b.maillist_service import get_mail_recipients
from services_b.dashboard_service import _bounds_to_str, _reading_raw_and_broken, _rvalue_numeric_string

logger = logging.getLogger(__name__)

# 呼叫端注入的隔離判斷函式型別：(db, plant_no, item) -> 是否目前在有效隔離區間內
IsolationChecker = Callable[..., bool]

K14B = "K14B"

try:
    from services_b.control_service import is_item_isolated as _wp3_is_item_isolated

    def _default_isolation_checker(db: Session, plant_no: str, item: str) -> bool:
        return _wp3_is_item_isolated(db, plant_no, item)
except ImportError:  # pragma: no cover - WP3 尚未完成時的防呆，不阻擋本模組獨立運作
    logger.warning("[dispatch_service] services_b.control_service 尚未提供，隔離判定退化為永遠 False")

    def _default_isolation_checker(db: Session, plant_no: str, item: str) -> bool:
        return False


# ── condition_code 分類（純函式，供 mail_log_item 寫入時挑一個代表性代碼）──────

def _primary_condition_code(codes: list[str]) -> str:
    """
    對應 mail_log_item.condition_code 分類（'OOS'/'OOC'/'ALERT'/'LIMIT_MISMATCH'/'MAINTENANCE'/'BROKEN'）。
    一個項目單次派報可能同時觸發多個 evaluate_row 內部條件（例如同時 Alert 又管制值不一致），
    這裡取「最嚴重」的一個做代表（優先序對齊燈號嚴重度 R(OOS) > O(OOC/管制值不一致/斷訊/保養中)
    > Y(Alert)），detail 欄位仍完整保留 evaluate_row 產生的 msg1 全文，不會漏資訊。
    """
    joined = "".join(codes)
    if "OOS" in joined:
        return "OOS"
    if "OOC" in joined:
        return "OOC"
    if "斷訊" in joined:
        return "BROKEN"
    if "保養中" in joined:
        return "MAINTENANCE"
    if "管制值不" in joined:
        return "LIMIT_MISMATCH"
    if "Alert" in joined:
        return "ALERT"
    return "OTHER"


def _escalation_stage(msg1: str) -> int:
    """從 evaluate_row 產生的 msg1 文字反推 escalation 階段（0/1/2），對齊 A 版 ArrOOCS 後綴。"""
    if "(30)" in msg1:
        return 2
    if "(15)" in msg1:
        return 1
    return 0


# ── prev_mail 轉接（★ 核心設計，見任務回報「prev_mail 轉接設計」）─────────────

def get_prev_mail(db: Session, plant_no: str, item: str) -> Optional[dict]:
    """
    對應 A 版 Get前筆派報資料(plantno, item)，B 版改查 mail_log_item 取代 msg1 LIKE '%|item|%'。

    設計：evaluate_row（零修改重用）內部用「上一筆 msg1 字串的子字串比對」判斷首發/再發/
    escalation 階段。寫入時（見 insert_mail_log_b）本檔把 evaluate_row 當次產生的
    `result.msg1`（含 `|item|：條件文字` 與 `(15)`/`(30)` escalation 後綴，格式與 A 版
    完全相同）原封不動存進 mail_log_item.detail；讀取時只要把 detail 當成 A 版的 msg0 餵回去，
    evaluate_row 的 check_first()/escalate() 子字串比對邏輯完全不需要修改就能正確運作。

    與 A 版的差異（更精確，非退化）：A 版 msg0 是整封信「所有項目」msg1 的大雜燴字串，
    子字串比對要靠 `|item|：` 前綴自然避免跨項目誤判；B 版每個項目只存自己的片段，
    天生不會有其他項目文字混入，對 evaluate_row 而言行為等價但更乾淨。
    """
    stmt = (
        select(MailLog.sent_at, MailLogItem.detail)
        .join(MailLogItem, MailLogItem.mail_log_id == MailLog.id)
        .where(MailLog.plant_no == plant_no, MailLogItem.item == item)
        .order_by(MailLog.sent_at.desc())
        .limit(1)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return {"cdatetime": row.sent_at, "msg1": row.detail or ""}


# ── get_data_b：B 新形狀 → evaluate_row 輸入形狀 ─────────────────────────────

def get_data_b(db: Session, isolation_checker: Optional[IsolationChecker] = None) -> list[dict]:
    """對應 A 版 get_data()：撈全廠即時資料，轉成 evaluate_row() 期待的輸入形狀。"""
    checker = isolation_checker or _default_isolation_checker

    stmt = (
        select(Spec, ReadingCurrent, Plant, Item)
        .join(Plant, Plant.plant_no == Spec.plant_no)
        .join(Item, Item.item == Spec.item)
        .outerjoin(
            ReadingCurrent,
            (ReadingCurrent.plant_no == Spec.plant_no) & (ReadingCurrent.item == Spec.item),
        )
        .where(Plant.is_show.is_(True))
        .order_by(Plant.sort, Spec.seqno)
    )
    rows = db.execute(stmt).all()

    result: list[dict] = []
    for spec, rc, plant, item_row in rows:
        is_isolated = checker(db, spec.plant_no, spec.item)
        rvalue_raw, broken = _reading_raw_and_broken(rc, is_isolated)
        display_item = item_row.display_name or spec.item

        oos_str = _bounds_to_str(spec.oos_low, spec.oos_high, spec.oos_status)
        ooc_str = _bounds_to_str(spec.ooc_low, spec.ooc_high, spec.ooc_status)
        alert_str = _bounds_to_str(spec.alert_low, spec.alert_high, spec.alert_status)
        recv_str = _bounds_to_str(spec.recv_low, spec.recv_high, spec.recv_status)
        if rc is not None:
            scada_oos_str = _bounds_to_str(rc.scada_oos_low, rc.scada_oos_high, rc.scada_limit_status)
            scada_ooc_str = _bounds_to_str(rc.scada_ooc_low, rc.scada_ooc_high, rc.scada_limit_status)
            scada_alert_str = _bounds_to_str(rc.scada_alert_low, rc.scada_alert_high, rc.scada_limit_status)
            cwms_oos_str = _bounds_to_str(rc.cwms_oos_low, rc.cwms_oos_high, rc.cwms_limit_status)
            cwms_ooc_str = _bounds_to_str(rc.cwms_ooc_low, rc.cwms_ooc_high, rc.cwms_limit_status)
        else:
            scada_oos_str = scada_ooc_str = scada_alert_str = cwms_oos_str = cwms_ooc_str = "-"

        result.append({
            "plantno": spec.plant_no,
            "item": display_item,
            "unit": item_row.unit or "",
            "law": spec.law_text or "",
            "oos": oos_str, "ooc": ooc_str, "alert_spec": alert_str, "recv": recv_str,
            "source": spec.source_id,
            "scada_oos": scada_oos_str, "scada_ooc": scada_ooc_str, "scada_alert": scada_alert_str,
            "cwms_oos": cwms_oos_str, "cwms_ooc": cwms_ooc_str,
            "rvalue_raw": rvalue_raw,
            "rvalue": _rvalue_numeric_string(rvalue_raw),
            "broken": broken,
        })
    return result


# ── mail_log / mail_log_item 寫入 ────────────────────────────────────────────

def insert_mail_log_b(db: Session, plantno: str, msg: str, sent_at: datetime, subject: str,
                       item_results: list[tuple[str, DispatchResult]]) -> int:
    """
    寫入 mail_log + mail_log_item（D 項決策，取代 A 版 InsertMAIL 寫 msg1/msg2 字串）。
    item_results：這個廠區「有觸發派報」的 (item, DispatchResult) 清單（codes 非空者）。
    回傳新建立的 mail_log.id。
    """
    log = MailLog(plant_no=plantno, sent_at=sent_at, subject=subject, body_note=msg)
    db.add(log)
    db.flush()  # 取得 log.id

    for item, result in item_results:
        db.add(MailLogItem(
            mail_log_id=log.id,
            item=item,
            condition_code=_primary_condition_code(result.codes),
            detail=result.msg1,
            escalation_stage=_escalation_stage(result.msg1),
            is_maintenance=any("保養中" in c for c in result.codes),
        ))
    db.commit()
    return log.id


# ── run_dispatch_b：主流程 ──────────────────────────────────────────────────

def run_dispatch_b(db: Session, isolation_checker: Optional[IsolationChecker] = None) -> dict:
    """
    對應 A 版 run_dispatch()（Job.SendMail.SendMail_廠務法規許可值標準化管控報表）。

    流程：
      1. get_data_b() 撈全廠即時資料。
      2. 逐列 get_prev_mail + evaluate_row（零修改重用）判斷是否派報。
      3. 依廠區分組，寄 HTML 信件、寫 mail_log + mail_log_item。
      4. K14B 跨廠通報：非 K14B 且 msg2 含「＞允收值」時，把「水Alert-K14B」TO 名單加進 CC
         （與 A 版一致，這裡的「水Alert」是 dispatch 專用報表類型，與 warning_service 的
         WATER_RPTTYPE「水質異常」是不同概念，互不相干）。

    ⚠️ 與 A 版刻意不同（沿用 services/dispatch_service.py 既有原則）：
      - mailto 為空時 continue 而非中止整個迴圈。
      - 全域暫停（system_config.mail_paused）由 maillist_service.get_mail_recipients 內部
        處理，回傳空清單即等同無收件人略過，本函式不需要另外檢查暫停旗標。
    """
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    data = get_data_b(db, isolation_checker)

    plant_rows: dict[str, list[dict]] = defaultdict(list)
    plant_results: dict[str, list[DispatchResult]] = defaultdict(list)

    for row in data:
        prev = get_prev_mail(db, row["plantno"], row["item"])
        result = evaluate_row(row, prev, now)
        plant_rows[row["plantno"]].append(row)
        plant_results[row["plantno"]].append(result)

    summary = {"sent": [], "skipped_no_recipient": [], "no_anomaly_plants": 0}

    for plantno, results in plant_results.items():
        if not any(r.codes for r in results):
            summary["no_anomaly_plants"] += 1
            continue

        msg = build_plant_msg(results)
        msg2 = build_plant_msg2(results)
        is_first = plant_is_first(results)

        data_red: list[str] = []
        for r in results:
            for c in r.codes:
                if c not in data_red:
                    data_red.append(c)

        rows_for_plant = plant_rows[plantno]
        rpttype_csv = _rpttypes_for_plant(data_red, plantno)
        mail_to = get_mail_recipients(db, rpttype_csv, plantno, "TO") if rpttype_csv else []
        mail_cc = get_mail_recipients(db, rpttype_csv, plantno, "CC") if rpttype_csv else []

        if plantno != K14B and "＞允收值" in msg2:
            k14b_rpttype = _rpttypes_for_plant(["水Alert-K14B"], K14B)
            k14b_to = get_mail_recipients(db, k14b_rpttype, K14B, "TO") if k14b_rpttype else []
            for e in k14b_to:
                if e not in mail_cc:
                    mail_cc.append(e)

        if not mail_to:
            logger.warning(f"[run_dispatch_b] 廠區 {plantno} 無收件人（TO 為空），略過此廠區信件")
            summary["skipped_no_recipient"].append(plantno)
            continue

        html_rows = [_row_to_html_dict(r, res) for r, res in zip(rows_for_plant, results)]
        body = render_dispatch_email(plantno, html_rows)
        subject = build_subject(plantno, is_first, now)

        send_email_sync(subject, body, mail_to, cc_addresses=mail_cc)

        item_results = [
            (row["item"], result) for row, result in zip(rows_for_plant, results) if result.codes
        ]
        insert_mail_log_b(db, plantno, msg, now, subject, item_results)
        summary["sent"].append(plantno)

    return summary
