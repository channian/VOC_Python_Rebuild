"""
services_b/sync_service.py — 同步 JOB 核心（Kepware/A 端 → Schema B）

依據：docs/PhaseA執行規格書.md 第三節「讀值分類規則」、第五節 WP2 工作包定義。

背景（為何重寫，而不是照抄舊 JOB）：
  舊系統 `legacy/Job_dbVOC.cs` 的 UpdateVOCData() 系列（本次僅取得摘要版原始碼，完整比對邏輯
  未附）用「Tag 名稱順序相符」的方式逐筆比對 iHistorian/Kepware DataTable 與
  VOC_SCADA_TagList（`docs/JOB確認清單.md` 第 23-25 行有精確記載：
  `while (TagsDT["Name"] != iHDT["tagname"]) iCount++`），只要兩邊順序或名稱有一絲落差就
  **靜默跳過**、不會報錯 —— 這正是 pH tag 改名後出現空值的根本原因。
  本檔改用 `tag_mapping` 表（(source_table, tagname) 唯一鍵）明確驅動每一筆同步，
  找不到對應資料只會計入 SyncResult.skipped/errors，不會有「靜默漏同步」的問題。

職責（本檔三個核心 + 一個骨架）：
  1. classify_reading()      純函式：A 端一筆 (value_raw, quality) → (value, status)。
  2. run_sync()              tag_mapping 驅動：A 端最新一筆 → 寫 reading_current +
                             （target_field='value' 時）append reading_history 含 SPEC 管制值快照。
  3. check_staleness()       看門狗：reading_current.measured_at 距今超過門檻 → comm_ok=False；
                             資料恢復新鮮時雙向切回 comm_ok=True。
  4. write_legacy_sink()     Track 1 骨架：把 reading_current 轉寫成舊 VOC_SCADA_WEB 字串格式，
                             供雙軌並行期間舊前端/報表過渡使用；本階段只在 PG 模擬表測試，
                             TODO 待 Track 1 於真 MSSQL 環境實測。

★ 引擎可攜規範（schema_B_設計提案.md 第五節，強制）：全部用 SQLAlchemy 2.0 select()/insert()/
  update() 表達式操作 ORM 物件，禁用 raw text()、禁用任何單邊方言語法（PG 的 ON CONFLICT 等）。
  write_legacy_sink() 的 upsert 因此刻意用「先 select 存在與否，再 insert 或 update」而非
  ON CONFLICT，才能在正式環境（PG 或 MSSQL 皆有可能）通用。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from models_b import ReadingCurrent, ReadingHistory, Spec, SystemConfig, TagMapping, KepwareSim
# ★ 重用既有 A 棧模型定義 VOC_SCADA_WEB 的表結構（唯讀 import，不修改該檔）——
#   write_legacy_sink() 只是要「轉寫成舊格式」，表結構本來就已經定義在這裡，不重複定義一份。
from models.spec_model import VocScadaWeb

logger = logging.getLogger(__name__)


# ============================================================
# 1. 讀值分類純函式（PhaseA執行規格書 第三節規則表）
# ============================================================

# 全形 ASCII 區（！-～，U+FF01-U+FF5E）→ 半形對應（!-~，U+0021-U+007E）的轉換表，
# 外加全形空白（U+3000）→ 半形空白，讓 '＜０．０５'、'Ｎ．Ｄ'、全形數字等輸入都能正確解析。
_FULLWIDTH_TRANS: Dict[int, int] = {0xFF01 + i: 0x21 + i for i in range(0x5E)}
_FULLWIDTH_TRANS[0x3000] = 0x20  # 全形空白 → 半形空白

# N.D（Not Detected，未檢出）常見寫法，全形/半形經正規化後统一比對
_ND_TOKENS = {"n.d", "n.d.", "nd"}


def _normalize_text(raw) -> str:
    """全形轉半形＋去頭尾空白。None 一律視為空字串（quality=good 但沒取到值的陷阱情境）。"""
    if raw is None:
        return ""
    return str(raw).translate(_FULLWIDTH_TRANS).strip()


def _parse_decimal(text: str) -> Optional[Decimal]:
    """安全轉 Decimal，非數字（含空字串）回傳 None，不丟例外。"""
    text = text.strip()
    if text == "":
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def classify_reading(value_raw, quality) -> Tuple[Optional[Decimal], str]:
    """
    讀值分類純函式：輸入 A 端一筆 (value_raw, quality)，輸出 (value, status)。

    規則（PhaseA執行規格書 第三節）：
      quality=good 且 value 為合法數字        → (數字, 'normal')
      quality=good 且 value 為 'N.D'          → (None, 'nd')
      quality=good 且 value 為 '<X'（如<0.05）→ (X, 'below_lod')
      quality=good 但 value 空/無法解析        → (None, 'error')   ← 使用者已知陷阱
      quality≠good                            → (None, 'broken')

    容錯：全形字元（全形數字/句點/less-than/空白）、前後空白、'<' 與數字間的空白皆會正規化後再判斷。
    負數（如 '-1.5'）視為合法數字，直接 Decimal 解析即可涵蓋。
    """
    q = _normalize_text(quality).lower()
    if q != "good":
        return None, "broken"

    raw = _normalize_text(value_raw)
    if raw == "":
        return None, "error"

    if raw.rstrip(".").lower() in _ND_TOKENS or raw.lower() in _ND_TOKENS:
        return None, "nd"

    if raw.startswith("<"):
        parsed = _parse_decimal(raw[1:])
        if parsed is None:
            return None, "error"
        return parsed, "below_lod"

    parsed = _parse_decimal(raw)
    if parsed is None:
        return None, "error"
    return parsed, "normal"


# ============================================================
# 2. run_sync：tag_mapping 驅動 A→B 同步
# ============================================================

@dataclass
class SyncResult:
    """一輪 run_sync() 的統計結果。errors 內為可讀訊息（tagname: 原因），不中斷其餘 tag 的同步。"""
    synced: int = 0     # 成功寫入 reading_current（含 target_field 為管制值欄位）的筆數
    skipped: int = 0    # A 端無資料 or reading_history 該 (plant_no,item,measured_at) 已存在（append-only 不重複寫）
    stale: int = 0      # 本輪處理時，A 端該筆資料本身已超過 staleness_minutes 門檻（僅統計，comm_ok 切換交由 check_staleness）
    errors: List[str] = field(default_factory=list)


# A 端來源表註冊表：source_table 字串 → ORM 模型類別。
# 目前只有 kepware_sim（PhaseA 測試期模擬表）；未來若新增其他 A 端來源（如 CWMS 若改走 tag_mapping），
# 只需要在這裡註冊，run_sync() 邏輯不用改（tag_mapping.source_table 已經是驅動鍵）。
_SOURCE_TABLE_MODELS = {
    "kepware_sim": KepwareSim,
}

# tag_mapping.target_field 除了 'value' 外，僅允許寫入 SCADA 自設管制值六欄
# （CWMS 完全不動，維持現行 HTTP API 路徑，見 PhaseA執行規格書 第一節決策紀錄）。
_CONTROL_LIMIT_FIELDS = {
    "scada_oos_low", "scada_oos_high",
    "scada_ooc_low", "scada_ooc_high",
    "scada_alert_low", "scada_alert_high",
}

_STATUS_TO_LIMIT_STATUS = {
    "normal": "valid",
    "below_lod": "valid",
    "nd": "na",
    "error": "na",
    "broken": "broken",
}


def _get_config_int(db: Session, key: str, default: int) -> int:
    """讀 system_config 單一鍵並轉 int，讀不到或格式錯誤時回傳 default（不中斷同步）。"""
    row = db.execute(select(SystemConfig.value).where(SystemConfig.key == key)).scalar_one_or_none()
    if row is None:
        return default
    try:
        return int(row)
    except (TypeError, ValueError):
        logger.warning("system_config[%s]=%r 無法轉為 int，改用預設值 %s", key, row, default)
        return default


def _latest_source_row(db: Session, source_table: str, tagname: str):
    """取某 A 端表某 tagname 的最新一筆（依 datetime_ 由新到舊取第一筆）。"""
    model = _SOURCE_TABLE_MODELS.get(source_table)
    if model is None:
        raise ValueError(f"未註冊的 source_table：{source_table!r}（見 _SOURCE_TABLE_MODELS）")
    stmt = (
        select(model)
        .where(model.tagname == tagname)
        .order_by(model.datetime_.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _get_or_create_reading_current(db: Session, plant_no: str, item: str, measured_at: datetime) -> ReadingCurrent:
    current = db.execute(
        select(ReadingCurrent).where(ReadingCurrent.plant_no == plant_no, ReadingCurrent.item == item)
    ).scalar_one_or_none()
    if current is None:
        # 理論上不會發生：reading_current(plant_no,item) 有 FK 依附 spec，spec 需先存在
        # （seed 已保證三個測試項目的 baseline）。這裡保守補一筆新列，避免單一項目缺 baseline
        # 就讓整批同步中斷；真正原因（tag_mapping 對到不存在的 plant_no/item）仍會反映在
        # 之後 flush 時的 FK IntegrityError，由呼叫端的 SAVEPOINT 隔離、計入 errors。
        current = ReadingCurrent(plant_no=plant_no, item=item, measured_at=measured_at)
        db.add(current)
    return current


def _build_limits_extra(current: ReadingCurrent) -> dict:
    """reading_history.limits_extra 快照：SCADA/CWMS 自設管制值（JSON 泛型型別，Decimal 需轉 float 才能序列化）。"""
    def _f(v):
        return float(v) if v is not None else None

    return {
        "scada_oos_low": _f(current.scada_oos_low), "scada_oos_high": _f(current.scada_oos_high),
        "scada_ooc_low": _f(current.scada_ooc_low), "scada_ooc_high": _f(current.scada_ooc_high),
        "scada_alert_low": _f(current.scada_alert_low), "scada_alert_high": _f(current.scada_alert_high),
        "scada_limit_status": current.scada_limit_status,
        "cwms_oos_low": _f(current.cwms_oos_low), "cwms_oos_high": _f(current.cwms_oos_high),
        "cwms_ooc_low": _f(current.cwms_ooc_low), "cwms_ooc_high": _f(current.cwms_ooc_high),
        "cwms_limit_status": current.cwms_limit_status,
        "rain_24h": _f(current.rain_24h),
    }


def _sync_value(db: Session, mapping: TagMapping, value, status: str, raw_text: str,
                 measured_at: datetime, result: SyncResult) -> None:
    """target_field='value'：覆寫 reading_current，並（若該 measured_at 尚未存在）append reading_history 快照。"""
    current = _get_or_create_reading_current(db, mapping.plant_no, mapping.item, measured_at)
    current.value = value
    current.status = status
    current.raw_text = raw_text
    current.comm_ok = status != "broken"
    current.measured_at = measured_at
    current.updated_at = datetime.now(timezone.utc)
    db.flush()

    # append-only：同 (plant_no,item,measured_at) 已存在就跳過，不 UPDATE 舊歷史列
    exists = db.execute(
        select(ReadingHistory.id).where(
            ReadingHistory.plant_no == mapping.plant_no,
            ReadingHistory.item == mapping.item,
            ReadingHistory.measured_at == measured_at,
        )
    ).first()
    if exists is not None:
        result.skipped += 1
        return

    spec = db.execute(
        select(Spec).where(Spec.plant_no == mapping.plant_no, Spec.item == mapping.item)
    ).scalar_one_or_none()

    history = ReadingHistory(
        plant_no=mapping.plant_no, item=mapping.item, value=value, status=status, raw_text=raw_text,
        measured_at=measured_at, limits_extra=_build_limits_extra(current),
    )
    if spec is not None:
        history.spec_oos_low, history.spec_oos_high = spec.oos_low, spec.oos_high
        history.spec_ooc_low, history.spec_ooc_high = spec.ooc_low, spec.ooc_high
        history.spec_alert_low, history.spec_alert_high = spec.alert_low, spec.alert_high
        history.spec_recv_low, history.spec_recv_high = spec.recv_low, spec.recv_high
    db.add(history)
    db.flush()
    result.synced += 1


def _sync_control_limit(db: Session, mapping: TagMapping, value, status: str, result: SyncResult) -> None:
    """target_field= SCADA 六種管制值欄位之一：只寫 reading_current 對應欄位，不 append history
    （管制值的逐時快照已經隨 target_field='value' 那筆的 limits_extra 一起記錄，不需要獨立歷史列）。
    """
    if mapping.target_field not in _CONTROL_LIMIT_FIELDS:
        result.errors.append(f"{mapping.tagname}: 未知的 target_field={mapping.target_field!r}")
        return

    current = _get_or_create_reading_current(db, mapping.plant_no, mapping.item, datetime.now(timezone.utc))
    setattr(current, mapping.target_field, value)
    current.scada_limit_status = _STATUS_TO_LIMIT_STATUS.get(status, current.scada_limit_status)
    current.updated_at = datetime.now(timezone.utc)
    db.flush()
    result.synced += 1


def _sync_one_mapping(db: Session, mapping: TagMapping, result: SyncResult,
                       staleness_minutes: int, now: datetime) -> None:
    latest = _latest_source_row(db, mapping.source_table, mapping.tagname)
    if latest is None:
        result.skipped += 1
        return

    value, status = classify_reading(latest.value, latest.quality)
    measured_at = latest.datetime_
    raw_text = latest.value

    if measured_at.tzinfo is None:
        measured_at = measured_at.replace(tzinfo=timezone.utc)
    if now - measured_at > timedelta(minutes=staleness_minutes):
        result.stale += 1  # 僅統計「本輪同步時來源資料本身已過期」，comm_ok 的實際切換交給 check_staleness

    if mapping.target_field == "value":
        _sync_value(db, mapping, value, status, raw_text, measured_at, result)
    else:
        _sync_control_limit(db, mapping, value, status, result)


def run_sync(db: Session, now: Optional[datetime] = None) -> SyncResult:
    """
    同步主流程：讀取全部 enabled 的 tag_mapping，逐筆取 A 端最新資料 → classify → 寫 B 端。

    每筆 tag_mapping 用 SAVEPOINT（Session.begin_nested）隔離，單一 tag 出錯（例如對到不存在
    的 plant_no/item 造成 FK 違反）只會記錄到 result.errors、回滾該筆的變更，不影響其他 tag
    的同步結果（對應舊 JOB「一個 tag 出錯拖垮整批」的脆弱性，見本檔頂部說明）。

    :param now: 供測試注入固定時間；預設現在時間（timezone-aware, UTC）。
    """
    if now is None:
        now = datetime.now(timezone.utc)

    result = SyncResult()
    staleness_minutes = _get_config_int(db, "staleness_minutes", 30)

    mappings = db.execute(
        select(TagMapping).where(TagMapping.enabled.is_(True)).order_by(TagMapping.id)
    ).scalars().all()

    for mapping in mappings:
        try:
            with db.begin_nested():
                _sync_one_mapping(db, mapping, result, staleness_minutes, now)
        except Exception as exc:  # noqa: BLE001 — 單一 tag 失敗不可讓整批同步中斷
            logger.exception("同步 tag 失敗：source_table=%s tagname=%s", mapping.source_table, mapping.tagname)
            result.errors.append(f"{mapping.source_table}.{mapping.tagname}: {exc}")

    db.commit()
    return result


# ============================================================
# 3. staleness 看門狗（雙向：過期切 False，恢復新鮮切回 True）
# ============================================================

@dataclass
class StalenessResult:
    stale: int = 0       # 本輪新標記為「斷訊」（comm_ok False<-True）的筆數
    recovered: int = 0   # 本輪自動恢復為「正常通訊」（comm_ok True<-False）的筆數


def check_staleness(db: Session, now: Optional[datetime] = None) -> StalenessResult:
    """
    看門狗：掃描 reading_current 全部列，依 measured_at 距 now 是否超過
    system_config['staleness_minutes'] 門檻，雙向切換 comm_ok：
      - 超過門檻              → comm_ok=False（value/status 保留不動，只標記通訊異常）
      - 未超過門檻（資料回來了）→ comm_ok=True（自動復原，不需人工介入解除斷訊標記）

    已經處於目標狀態的列不會被無謂 UPDATE（減少寫入量、也讓回傳統計只反映「本輪真正翻轉」的筆數）。

    :param now: 供測試注入固定時間；預設現在時間（timezone-aware, UTC）。
    """
    if now is None:
        now = datetime.now(timezone.utc)

    staleness_minutes = _get_config_int(db, "staleness_minutes", 30)
    cutoff = now - timedelta(minutes=staleness_minutes)

    result = StalenessResult()
    rows = db.execute(select(ReadingCurrent)).scalars().all()
    for row in rows:
        measured_at = row.measured_at
        if measured_at.tzinfo is None:
            measured_at = measured_at.replace(tzinfo=timezone.utc)

        is_stale = measured_at < cutoff
        if is_stale and row.comm_ok:
            row.comm_ok = False
            result.stale += 1
        elif not is_stale and not row.comm_ok:
            row.comm_ok = True
            result.recovered += 1

    db.commit()
    return result


# ============================================================
# 4. legacy sink 骨架（Track 1：轉寫舊 VOC_SCADA_WEB 格式）
# ============================================================

_STATUS_TO_RVALUE_LITERAL = {
    "nd": "N.D",
    "broken": "斷訊",
    "error": "異常",
    "maintenance": "保養中",  # B 端目前不會產生此狀態（C 決策：隔離不落地於 reading_current），保留供未來相容
    "building": "建置中",     # 同上，防禦性保留
}


def _format_rvalue(status: str, value: Optional[Decimal]) -> str:
    """把 B 端 (value, status) 轉回舊 VOC_SCADA_WEB.rvalue 的文字格式。"""
    if status == "below_lod":
        return f"<{value}" if value is not None else "<0"
    if status in _STATUS_TO_RVALUE_LITERAL:
        return _STATUS_TO_RVALUE_LITERAL[status]
    # normal（或未知狀態的保守 fallback）：直接輸出數字文字
    return str(value) if value is not None else ""


def _opt_str(value: Optional[Decimal]) -> Optional[str]:
    return str(value) if value is not None else None


def write_legacy_sink(rows: Iterable[ReadingCurrent], engine) -> int:
    """
    Track 1 骨架：把一批 reading_current 列轉寫成舊 VOC_SCADA_WEB 格式，寫入指定 engine
    （雙軌並行期間供舊前端/報表過渡讀取；也可能是同一顆 MSSQL VOC 資料庫的既有表）。

    ⚠️ TODO(Track 1)：本函式僅為骨架，尚未在真實 MSSQL 環境實測（PhaseA執行規格書 第五節
    WP2 任務描述：「介面留好、本階段不需連 MSSQL 實測」）。目前只用 PG 模擬表驗證：
      1. rvalue 字串轉換規則（nd→'N.D'、below_lod→'<X'、broken→'斷訊'、error→'異常'）正確；
      2. engine 可注入（不寫死連線字串），upsert 用「先查後 insert/update」而非 ON CONFLICT，
         確保正式環境不論用 PG 或 MSSQL 皆可運作。

    broken 欄位僅還原 0/1（正常/斷訊，對應 comm_ok），**不會**產生舊語意的 2（保養中）——
    C 決策後保養狀態改由 isolation 表 JOIN 推導、不落地於 reading_current，本函式沒有
    這個資訊來源，這是與 A 棧舊系統刻意的行為差異（見任務回報「與舊 UpdateVOCData 刻意差異」）。

    :param rows: 要轉寫的 reading_current 列（ORM 物件或具備同名屬性的物件）。
    :param engine: 目標 SQLAlchemy Engine（測試注入 PG，正式環境未定案時可換 MSSQL）。
    :return: 實際寫入（insert 或 update）的筆數。
    """
    table = VocScadaWeb.__table__
    table.create(bind=engine, checkfirst=True)

    written = 0
    with engine.begin() as conn:
        for row in rows:
            values = dict(
                rvalue=_format_rvalue(row.status, row.value),
                cdatetime=row.measured_at,
                broken=0 if row.comm_ok else 1,
                OOS_HH=_opt_str(row.scada_oos_high), OOC_H=_opt_str(row.scada_ooc_high),
                alert=_opt_str(row.scada_alert_high),
                OOS_LL=_opt_str(row.scada_oos_low), OOC_L=_opt_str(row.scada_ooc_low),
                alert_L=_opt_str(row.scada_alert_low),
                OOS_HH1=_opt_str(row.cwms_oos_high), OOC_H1=_opt_str(row.cwms_ooc_high),
                TwentyFourHours=float(row.rain_24h) if row.rain_24h is not None else None,
            )
            existing = conn.execute(
                select(table.c.plantno).where(table.c.plantno == row.plant_no, table.c.item == row.item)
            ).first()
            if existing is None:
                conn.execute(insert(table).values(plantno=row.plant_no, item=row.item, **values))
            else:
                conn.execute(
                    update(table)
                    .where(table.c.plantno == row.plant_no, table.c.item == row.item)
                    .values(**values)
                )
            written += 1
    return written
