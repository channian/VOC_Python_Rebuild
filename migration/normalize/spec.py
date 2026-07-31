"""
migration/normalize/spec.py — A VOC_SPEC → B Spec 純轉換函式。

契約（見 migration/normalize/__init__.py）：輸入 = list[dict]（key 為 A VOC_SPEC 原始
DB 欄位名，見 models/spec_model.py 的 VocSpec），輸出 = list[Spec]（未 save）。純函式，
不連 DB，可直接對回傳物件屬性單元測試。

A 端來源欄位（models/spec_model.py VocSpec）：
    plantno, item, LAW, OOS, OOC, alert, recv, source, status, tagname, seqno

規則：
    - 只搬 status==1（啟用）；status 非 1（含 0/停用、None）整列略過（B 的 Spec 無 enabled 欄位）。
    - OOS/OOC/alert/recv 四組門檻字串各自拆成 low/high/status 三欄，重用
      services.dashboard_service._parse_bounds 判讀（單邊/雙邊/無效），規則見 __init__.py。
    - 數值一律轉成 Decimal（B 欄位是 Numeric），用 Decimal(str(x)) 轉換避免 float 浮點雜訊
      （例如 Decimal(0.1) 會帶入二進位誤差，Decimal(str(0.1)) 才是乾淨的 0.1）。
    - 不設 updated_at，讓 DB server_default（func.now()）處理。
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from models_b import Spec
from services.dashboard_service import _parse_bounds

__all__ = ["normalize_spec"]

# 對映舊系統「建置中」的字面值判斷（_parse_bounds 對這個字串跟 '-'/'N/A'/'' 一樣都回 None，
# 需要在這裡另外分辨才能決定 status 該填 'building' 還是 'na'）。
_BUILDING = "建置中"


def _bounds_triplet(raw: Optional[str]) -> Tuple[Optional[Decimal], Optional[Decimal], str]:
    """單組門檻字串 → (low, high, status) 三元組。

    - 可解析（單邊/雙邊）→ (Decimal(low), Decimal(high), 'valid')。
    - 不可解析且原字串 strip 後 == '建置中' → (None, None, 'building')。
    - 其餘不可解析（'-'/'N/A'/''/None 等） → (None, None, 'na')。
    """
    b = _parse_bounds(raw)
    if b is not None:
        return Decimal(str(b[0])), Decimal(str(b[1])), "valid"

    s = str(raw).strip() if raw is not None else ""
    if s == _BUILDING:
        return None, None, "building"
    return None, None, "na"


def normalize_spec(rows: List[Dict[str, Any]]) -> List[Spec]:
    """A VOC_SPEC{plantno, item, LAW, OOS, OOC, alert, recv, source, status, tagname, seqno}
    → Spec(plant_no, item, law_text, oos_*, ooc_*, alert_*, recv_*, source_id, seqno)。

    ⚠️ 2026-07-12 tagname 收斂：spec 表已移除 tagname 欄位（同步 JOB 一律以 tag_mapping
    為唯一權威，spec.tagname 在 B 棧從未被任何邏輯讀取，留著只會誤導維護者以為改它有效）。
    舊 VOC_SPEC.tagname 的既有知識並未遺失——它仍在 export/VOC_SPEC.json 原始資料裡，
    Phase C 正式搬遷時應據以產生 tag_mapping 的初始列（待該階段連同真實 source_table 一併定案）。

    只搬 status==1（啟用）的列；門檻四組各拆 low/high/status（見 _bounds_triplet）。
    """
    out: List[Spec] = []
    for row in rows:
        if row.get("status") != 1:
            continue

        oos_low, oos_high, oos_status = _bounds_triplet(row.get("OOS"))
        ooc_low, ooc_high, ooc_status = _bounds_triplet(row.get("OOC"))
        alert_low, alert_high, alert_status = _bounds_triplet(row.get("alert"))
        recv_low, recv_high, recv_status = _bounds_triplet(row.get("recv"))

        seqno = row.get("seqno")

        out.append(
            Spec(
                plant_no=row.get("plantno"),
                item=row.get("item"),
                law_text=row.get("LAW"),
                oos_low=oos_low,
                oos_high=oos_high,
                oos_status=oos_status,
                ooc_low=ooc_low,
                ooc_high=ooc_high,
                ooc_status=ooc_status,
                alert_low=alert_low,
                alert_high=alert_high,
                alert_status=alert_status,
                recv_low=recv_low,
                recv_high=recv_high,
                recv_status=recv_status,
                source_id=row.get("source"),
                seqno=seqno if seqno is not None else 0,
            )
        )
    return out
