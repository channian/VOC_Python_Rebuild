"""
migration/normalize/reading.py — A VOC_SCADA_WEB → B ReadingCurrent 純轉換函式。

契約（見 migration/normalize/__init__.py）：輸入 = list[dict]（key 為 A VOC_SCADA_WEB 原始 DB
欄位名，見 models/spec_model.py 的 VocScadaWeb），輸出 = list[ReadingCurrent]（未 save）。純函式，
不連 DB，可直接對回傳物件屬性單元測試。

A 端來源欄位（models/spec_model.py VocScadaWeb）：
    plantno, item, rvalue, cdatetime,
    OOS_HH, OOC_H, alert, OOS_LL, OOC_L, alert_L,   # SCADA 六欄門檻
    OOS_HH1, OOC_H1,                                 # CWMS 二欄門檻（僅上限）
    broken, TwentyFourHours

★ 這是 A→B 搬遷最需要小心的轉換：A 端 rvalue 是「數字與狀態文字混存」的 varchar
  （'1.16' / 'N.D' / '<0.05' / '斷訊' / '異常' / '建置中' / '保養中'），B 端拆成
  value（純數字）+ status（列舉字串）+ raw_text（原字串備查），並用獨立的 comm_ok
  取代舊 broken=1（斷訊）語意。

broken 欄位語意（VocScadaWeb 註解）：
    0 = 正常（或 None，A 端舊資料偶有缺值視同正常）
    1 = 斷訊（JOB 寫）        → B: value=None, status='broken',       comm_ok=False
    2 = 保養中/隔離中（Web 寫）→ B: value=None, status='maintenance', comm_ok=True
        （B 的 comm_ok 只對應「通訊斷訊」，隔離不是通訊問題，故仍為 True；
        dashboard 端會另外用 status=='maintenance' 顯示保養中，語意不靠 comm_ok。）

broken==0（或 None）時才進一步解析 rvalue 字串本身；rvalue 內也可能混存斷訊/異常/建置中/
保養中等狀態文字（舊系統的另一種寫法），一併判讀，避免漏掉「broken 欄位沒更新但 rvalue
已經是文字」的髒資料。

管制值（SCADA 六欄 + CWMS 二欄）一律重用 services.dashboard_service._parse_bounds 解析
（單邊字串回 (v, v)、雙邊 'low-high' 回 (low, high)、無效值回 None），只取需要的那一界：
SCADA/CWMS 上限欄位取高界、下限欄位取低界；CWMS 在 A 端只有上限二欄，B 的 cwms_*_low
固定為 None。*_limit_status 只要該組六（或二）欄任一解析出值就是 'valid'，否則 'na'。
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from models_b import ReadingCurrent
from services.dashboard_service import _parse_bounds
from services_b.sync_service import _ND_TOKENS, _normalize_text, _parse_decimal

__all__ = ["normalize_reading_current"]

# rvalue 字串本身混存的狀態文字（broken==0 但 rvalue 已經是文字時仍要判讀）。
_RVALUE_STATUS_TEXT = {
    "斷訊": "broken",
    "異常": "error",
    "建置中": "building",
    "保養中": "maintenance",
}


def _classify_rvalue(rvalue, broken) -> Tuple[Optional[Decimal], str]:
    """A 端一筆 (rvalue, broken) → B 端 (value, status)。

    - broken == 1（斷訊，JOB 寫）→ (None, 'broken')。
    - broken == 2（保養中/隔離中，Web 寫）→ (None, 'maintenance')。
    - broken == 0（或 None）→ 解析 rvalue 字串（全形/空白先用 _normalize_text 正規化）：
        空字串                → (None, 'error')
        N.D 系列（見 _ND_TOKENS）→ (None, 'nd')
        以 '<' 開頭（如 '<0.05'）→ (Decimal, 'below_lod')，解析失敗 → (None, 'error')
        '斷訊'/'異常'/'建置中'/'保養中' → 對映的狀態文字
        純數字                → (Decimal, 'normal')
        其餘無法解析           → (None, 'error')
    """
    if broken == 1:
        return None, "broken"
    if broken == 2:
        return None, "maintenance"

    raw = _normalize_text(rvalue)
    if raw == "":
        return None, "error"

    if raw.rstrip(".").lower() in _ND_TOKENS or raw.lower() in _ND_TOKENS:
        return None, "nd"

    if raw.startswith("<"):
        parsed = _parse_decimal(raw[1:])
        if parsed is None:
            return None, "error"
        return parsed, "below_lod"

    if raw in _RVALUE_STATUS_TEXT:
        return None, _RVALUE_STATUS_TEXT[raw]

    parsed = _parse_decimal(raw)
    if parsed is None:
        return None, "error"
    return parsed, "normal"


def _bound_value(raw, side: int) -> Optional[Decimal]:
    """單一管制值字串 → 取 _parse_bounds() 結果的 low(side=0)/high(side=1) 那一界，轉 Decimal。

    無法解析（None/'-'/'N/A'/'建置中'/空字串等）→ None。
    """
    bounds = _parse_bounds(raw)
    if bounds is None:
        return None
    return Decimal(str(bounds[side]))


def _parse_measured_at(raw) -> datetime:
    """cdatetime → tz-aware datetime，容忍 str/datetime/None。

    - None → 保底用當下 UTC 時間（正常情況下 A 端資料應皆有時間戳，屬防呆）。
    - datetime（含 tz-naive）→ 補 UTC。
    - str → ISO 格式解析（容忍結尾 'Z'）；解析失敗一併保底用當下 UTC 時間。
    """
    if raw is None:
        return datetime.now(timezone.utc)

    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_reading_current(rows: List[Dict[str, Any]]) -> List[ReadingCurrent]:
    """A VOC_SCADA_WEB{plantno, item, rvalue, cdatetime, OOS_HH, OOC_H, alert, OOS_LL, OOC_L,
    alert_L, OOS_HH1, OOC_H1, broken, TwentyFourHours} → ReadingCurrent(...)。

    每個 A 列（同一 plantno+item 在 A 端本就只留最新一筆）對映一個 B 列。
    """
    out: List[ReadingCurrent] = []
    for row in rows:
        value, status = _classify_rvalue(row.get("rvalue"), row.get("broken"))
        comm_ok = status != "broken"

        scada_oos_high = _bound_value(row.get("OOS_HH"), 1)
        scada_oos_low = _bound_value(row.get("OOS_LL"), 0)
        scada_ooc_high = _bound_value(row.get("OOC_H"), 1)
        scada_ooc_low = _bound_value(row.get("OOC_L"), 0)
        scada_alert_high = _bound_value(row.get("alert"), 1)
        scada_alert_low = _bound_value(row.get("alert_L"), 0)
        scada_limit_status = (
            "valid"
            if any(
                v is not None
                for v in (
                    scada_oos_high,
                    scada_oos_low,
                    scada_ooc_high,
                    scada_ooc_low,
                    scada_alert_high,
                    scada_alert_low,
                )
            )
            else "na"
        )

        cwms_oos_high = _bound_value(row.get("OOS_HH1"), 1)
        cwms_ooc_high = _bound_value(row.get("OOC_H1"), 1)
        cwms_limit_status = "valid" if (cwms_oos_high is not None or cwms_ooc_high is not None) else "na"

        rain = row.get("TwentyFourHours")

        out.append(
            ReadingCurrent(
                plant_no=row.get("plantno"),
                item=row.get("item"),
                value=value,
                status=status,
                raw_text=row.get("rvalue"),
                comm_ok=comm_ok,
                scada_oos_low=scada_oos_low,
                scada_oos_high=scada_oos_high,
                scada_ooc_low=scada_ooc_low,
                scada_ooc_high=scada_ooc_high,
                scada_alert_low=scada_alert_low,
                scada_alert_high=scada_alert_high,
                scada_limit_status=scada_limit_status,
                cwms_oos_low=None,
                cwms_oos_high=cwms_oos_high,
                cwms_ooc_low=None,
                cwms_ooc_high=cwms_ooc_high,
                cwms_limit_status=cwms_limit_status,
                rain_24h=Decimal(str(rain)) if rain is not None else None,
                measured_at=_parse_measured_at(row.get("cdatetime")),
            )
        )
    return out
