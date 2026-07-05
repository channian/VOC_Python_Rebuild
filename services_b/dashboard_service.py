"""
services_b/dashboard_service.py — 儀表板資料查詢與燈號計算（Schema B 資料層版本）

職責與 services/dashboard_service.py（A/MSSQL 版）完全一致：
  1. 從 spec JOIN reading_current JOIN plant/item/curve 取得每個廠區/項目的最新讀值與規格值。
  2. 依三層門檻值（OOS/OOC/Alert）及 SCADA/CWMS 與 SPEC 是否一致計算燈號。
  3. 回傳 DashboardRow list（沿用既有 schemas/dashboard_schema.py，供未來模板直接重用）。

★ 純函式重用原則（CLAUDE.md／PhaseA執行規格書 第七節強制條款）：
  燈號計算 `_calculate_light` / `_parse_bounds` / `_bounds_mismatch` 與廠區分組後處理
  `_annotate_plant_groups` 一律 import 既有 `services/dashboard_service.py`，**不重寫、不複製**。
  本檔案只負責「B 資料層新形狀 → 這些純函式吃的舊字串形狀」的轉接（`_bounds_to_str` /
  `_reading_raw_and_broken`），確保 A、B 兩棧永遠算出同一個燈號（同源保證）；
  一致性由 tests_integration/test_dashboard_spec.py 的表格驅動測試驗證。

★ B 架構差異（schema_B_設計提案.md C 項決策）：
  舊系統「隔離中」是把 VOC_SCADA_WEB.broken 竄改成 2、rvalue 覆寫成「保養中」字串，且連歷史表
  也一併竄改（真實讀值因此永久遺失）。B 版隔離**不落地竄改** reading_current／reading_history，
  改由呼叫端注入 `isolation_checker(plant_no, item) -> bool`，本函式只在「組出要給燈號純函式看的
  資料列」這一刻，把「目前是否被隔離覆蓋中」轉換成舊系統看得懂的顯示文字（'保養中'）與
  broken=2；reading_current 本身的 value/status 完全不受影響。main_b 組裝時會傳入 WP3 提供的
  真正查 isolation 表函式，測試時可注入假函式（見本檔測試）。
"""

from datetime import datetime
from decimal import Decimal
from typing import Callable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import Spec, ReadingCurrent, Plant, Item, Curve
from schemas.dashboard_schema import DashboardRow
from services.dashboard_service import _calculate_light, _annotate_plant_groups

# 呼叫端注入的隔離判斷函式型別：(plant_no, item) -> 是否目前在有效隔離區間內
IsolationChecker = Callable[[str, str], bool]


def _bounds_to_str(low: Optional[Decimal], high: Optional[Decimal], status: Optional[str]) -> str:
    """
    B 版 numeric low/high（+status）→ A 版純函式 `_parse_bounds()` 吃的字串形狀。

    - status 為 'na'/'building'/'broken'（門檻未設定/建置中/取值異常）→ 回傳 '-'
      （`_parse_bounds` 視為無效門檻，不納入燈號比對，與 A 版 VOC_SPEC 存 '-'/'建置中' 的
      行為一致）。
    - 雙邊（low 有值且 low != high，如 pH/溫度）→ 'low-high'（`_parse_bounds` 用 '-' 切開，
      取上界比對）。
    - 單邊（low 為 None，或 low == high）→ 只留 high（或 low）的字串（`_parse_bounds` 視為
      單邊數值，low==high 時回傳 (v, v) 效果相同）。
    - low/high 皆為 None → 回傳 '-'（無門檻）。
    """
    if status in ("na", "building", "broken"):
        return "-"
    if low is None and high is None:
        return "-"
    if low is None or low == high:
        return str(high if high is not None else low)
    return f"{low}-{high}"


# 非數字顯示字串（含 below_lod 的 '<X'）一律視為 0，供模板做數字比較用；
# 對齊 A 版 SQL 的 REPLACE(rvalue,'N.D','0')...REPLACE(rvalue,'<0.05','0') 清洗規則。
_NON_NUMERIC_DISPLAY = {"N.D", "異常", "斷訊", "保養中", "建置中", ""}


def _rvalue_numeric_string(raw: str) -> str:
    """把非數字顯示字串轉成 '0'（供模板數字比較用），對齊 A 版 SQL 清洗規則。"""
    if raw in _NON_NUMERIC_DISPLAY or raw.startswith("<"):
        return "0"
    return raw


def _reading_raw_and_broken(rc: Optional[ReadingCurrent], is_isolated: bool) -> Tuple[str, int]:
    """
    把 reading_current 的 value/status/comm_ok 新形狀，轉成舊系統燈號純函式看得懂的
    (rvalue_raw, broken) 組合。

    優先序（對齊 CLAUDE.md「broken 欄位」語意：0=正常/1=斷訊(JOB寫)/2=保養中(Web寫)，
    B 版 Web 與 JOB 不再共用同一個欄位互蓋，而是分成 isolation 表 JOIN 推導 vs comm_ok）：
      1. isolation_checker 判定目前被隔離覆蓋中 → '保養中' + broken=2（C 項決策：純粹是
         「顯示層」推導出來的保養中，reading_current 實際讀值/狀態完全不受影響）。
      2. 尚無 reading_current 資料（尚未同步過的新設項目）→ '建置中' + broken=1，避免誤算綠燈。
      3. comm_ok=False（同步 JOB 判定通訊異常，取代舊 broken=1 語意）→ '斷訊' + broken=1。
      4. status='broken'（理論上應與 comm_ok=False 同時出現，這裡多一層防護）→ '斷訊' + broken=1。
      5. status='maintenance'（同步 JOB 也可能在寫入新列時直接標記，見 schema_B_設計提案.md C 項
         決策原文）→ '保養中' + broken=2，與 isolation_checker 殊途同歸。
      6. status='error'（quality=good 但 value 空/無法解析，PhaseA執行規格書已知陷阱）→ '異常'。
      7. status='nd' → 'N.D'。
      8. status='building' → '建置中'。
      9. status='below_lod' → 優先用 raw_text（同步 JOB 寫入時保留的原始 '<0.05' 字串），
         沒有 raw_text 時退回用 value 組出 '<{value}'。
      10. status='normal'（或其他未表列狀態，安全網）→ 直接用 value 的字串，走一般數字比對路徑。
    """
    if is_isolated:
        return "保養中", 2
    if rc is None:
        return "建置中", 1
    if not rc.comm_ok:
        return "斷訊", 1
    if rc.status == "broken":
        return "斷訊", 1
    if rc.status == "maintenance":
        return "保養中", 2
    if rc.status == "error":
        return "異常", 0
    if rc.status == "nd":
        return "N.D", 0
    if rc.status == "building":
        return "建置中", 0
    if rc.status == "below_lod":
        return (rc.raw_text or (f"<{rc.value}" if rc.value is not None else "")), 0
    return (str(rc.value) if rc.value is not None else ""), 0


def get_dashboard_rows(db: Session, isolation_checker: Optional[IsolationChecker] = None) -> List[DashboardRow]:
    """
    取得 B 資料層版本的儀表板全部廠區 × 項目資料列。

    對應 `services/dashboard_service.get_dashboard_data()`，差異：
      - 資料來源 spec + reading_current（B 新形狀）取代 VOC_SPEC + VOC_SCADA_WEB。
      - 目前不含 plant_permissions ACL 過濾參數（WP4 範圍不含權限守門，見 CLAUDE.md
        已知待辦「check_permission 尚未掛到各 router」；main_b 串接 ACL 後可在呼叫端另外
        用回傳結果的 plantno 過濾，或未來擴充本函式增加篩選參數）。
      - isolation_checker：由呼叫端注入「(plant_no, item) 是否目前在有效隔離區間內」的判斷
        函式；main_b 正式接線時會換成 WP3 查 isolation 表的真實實作，測試時可注入假函式；
        預設 None 等同「都沒有隔離中」。
    """
    checker: IsolationChecker = isolation_checker or (lambda plant_no, item: False)

    stmt = (
        select(Spec, ReadingCurrent, Plant, Item, Curve)
        .join(Plant, Plant.plant_no == Spec.plant_no)
        .join(Item, Item.item == Spec.item)
        .outerjoin(
            ReadingCurrent,
            (ReadingCurrent.plant_no == Spec.plant_no) & (ReadingCurrent.item == Spec.item),
        )
        .outerjoin(Curve, (Curve.plant_no == Spec.plant_no) & (Curve.item == Spec.item))
        .where(Plant.is_show.is_(True))
        .order_by(Plant.sort, Spec.seqno)
    )
    rows = db.execute(stmt).all()

    result: List[DashboardRow] = []
    for spec, rc, plant, item_row, curve in rows:
        is_isolated = checker(spec.plant_no, spec.item)
        rvalue_raw, broken = _reading_raw_and_broken(rc, is_isolated)

        # 組出既有純函式 `_calculate_light` 吃的字串形狀（僅供計算，不對外回傳）
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

        light, is_anomaly = _calculate_light(dict(
            item=spec.item,
            rvalue_raw=rvalue_raw,
            oos=oos_str, ooc=ooc_str, alert_spec=alert_str, recv=recv_str,
            scada_oos=scada_oos_str, scada_ooc=scada_ooc_str, scada_alert=scada_alert_str,
            cwms_oos=cwms_oos_str, cwms_ooc=cwms_ooc_str,
            broken=broken,
        ))

        # G 項決策：pH1/COD2 顯示用 item.display_name，取代程式硬編 to_display_item() 字串替換
        display_item = item_row.display_name or spec.item

        result.append(DashboardRow(
            plantno=spec.plant_no,
            item=display_item,
            unit=item_row.unit or "",
            law_spec=spec.law_text or "",
            oos=oos_str, ooc=ooc_str, alert_spec=alert_str, recv=recv_str,
            source=spec.source_id,
            rvalue_raw=rvalue_raw,
            rvalue=_rvalue_numeric_string(rvalue_raw),
            scada_oos=scada_oos_str, scada_ooc=scada_ooc_str, scada_alert=scada_alert_str,
            cwms_oos=cwms_oos_str, cwms_ooc=cwms_ooc_str,
            broken=broken,
            url=(curve.url if curve else "") or "",
            remark="",
            emptycell="",
            light_status=light,
            is_anomaly=is_anomaly,
            rain_24h=str(rc.rain_24h) if (rc is not None and rc.rain_24h is not None) else "",
        ))

    return _annotate_plant_groups(result)
