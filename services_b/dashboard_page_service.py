"""
services_b/dashboard_page_service.py — B 棧首頁儀表板頁面組裝（純轉換 + 薄 DB 入口）

職責：把 `services_b/dashboard_service.get_dashboard_rows()` 回傳的 DashboardRow 攤平列表，
轉成 `templates/b/dashboard.html`（design_handoff_voc_platform/VOC Dashboard.dc.html 高保真還原）
渲染所需的「廠區手風琴 + 摘要卡 + 異常速覽」形狀。

★ 純函式重用原則（CLAUDE.md）：
  燈號本身（R/O/Y/G/-）已由 `services/dashboard_service._calculate_light()` 算好，存在
  `DashboardRow.light_status`；本檔**不重算燈號**，只在 light_status=='O' 時，用既有的
  `_parse_bounds()` / `_bounds_mismatch()` 純函式，多分辨一次「是數值超標(O)還是管制值
  不同步(O≠/O2)」——因為 `_calculate_light()` 對外只回傳同一個 'O'，UI 需要進一步區分
  兩種橙燈語意（見 README「畫面 2」燈號 LEGEND 六種圖形）。

顯示狀態 key（7 種，供模板上色/分組用）：
  'R'  紅燈：讀值 >= OOS
  'O'  橙燈（數值超標）：OOC <= 讀值 < OOS
  'O2' 橙燈（管制值不同步）：light_status=='O' 但數值本身沒超出 OOC~OOS 區間，
       是 SCADA/CWMS 管制值與 SPEC 設定值不一致觸發的橙燈
  'Y'  黃燈：預警或超允收
  'G'  綠燈：正常
  'B'  斷訊：broken==1（JOB 寫），或讀值非數字但未被標記保養/斷訊的其他異常狀態
       （'異常'/'建置中' 等 broken==0 的邊界情形，比照舊系統「無法判讀」併入斷訊／保養統計卡）
  'M'  保養中／隔離中：broken==2（Web 寫）
"""

from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from models_b import ReadingCurrent
from schemas.dashboard_schema import DashboardRow
from services.dashboard_service import _bounds_mismatch, _parse_bounds, _safe_float
from services_b.dashboard_service import IsolationChecker, get_dashboard_rows

# 顯示狀態的嚴重度排序（數字越小越嚴重），供廠區排序與「取最高嚴重度」使用
_SEVERITY_ORDER: List[str] = ["R", "O", "O2", "Y", "B", "M", "G"]

# 廠區側欄 / 手風琴 pill 文字前綴
_PILL_LABEL: Dict[str, str] = {"R": "R", "O": "O", "O2": "O≠", "Y": "Y", "B": "斷", "M": "保"}

# counts / pills 固定輸出順序（不含 G——正常項目不需要 pill 提醒）
_COUNT_KEYS: List[str] = ["R", "O", "O2", "Y", "B", "M"]


def _classify_o(row: DashboardRow) -> str:
    """
    light_status=='O' 時，分辨是「數值超標」(O) 還是「管制值不同步」(O2)。

    對齊 `services/dashboard_service._calculate_light()` 的判斷順序：先比對讀值是否落在
    OOC~OOS 之間（數值超標），若不是，橙燈必然是由管制值不一致觸發（不然不會亮橙燈）。
    """
    rvalue = _safe_float(row.rvalue_raw)
    oos_b = _parse_bounds(row.oos)
    ooc_b = _parse_bounds(row.ooc)
    oos = oos_b[1] if oos_b else None
    ooc = ooc_b[1] if ooc_b else None
    if rvalue is not None and oos is not None and ooc is not None and ooc <= rvalue < oos:
        return "O"

    # 保險起見，仍實際重跑一次管制值不一致比對（而非單純假設「不是數值超標就一定是 O2」），
    # 讓這裡的判斷邏輯可獨立驗證，不依賴呼叫端保證只有 O 燈才會呼叫本函式。
    is_voc = "VOC" in row.item
    if (
        _bounds_mismatch(row.scada_oos, row.oos, voc_exception=is_voc)
        or _bounds_mismatch(row.scada_ooc, row.ooc, voc_exception=is_voc)
        or _bounds_mismatch(row.scada_alert, row.alert_spec)
        or _bounds_mismatch(row.cwms_oos, row.oos)
        or _bounds_mismatch(row.cwms_ooc, row.ooc)
    ):
        return "O2"

    # 理論上不會走到這裡（light_status=='O' 必屬於上述兩種原因之一），但保留安全網，
    # 避免未來 _calculate_light 邏輯變動時本函式默默吞掉未知狀態。
    return "O2"


def _classify_status(row: DashboardRow) -> str:
    """把 DashboardRow 的 (broken, light_status) 轉成本頁面用的 7 種顯示狀態 key。"""
    if row.broken == 1:
        return "B"
    if row.broken == 2:
        return "M"
    if row.light_status == "R":
        return "R"
    if row.light_status == "O":
        return _classify_o(row)
    if row.light_status == "Y":
        return "Y"
    if row.light_status == "G":
        return "G"
    # light_status == '-' 但 broken == 0：讀值本身是非數字異常字串（'異常'/'建置中' 等），
    # 未被 broken 欄位標記，比照舊系統「無法判讀」併入斷訊／保養統計卡（'B'）。
    return "B"


def _row_to_dict(row: DashboardRow, key: str, is_rain: bool, rain_24h: str) -> dict:
    """DashboardRow → 純 dict，供 Jinja2 `{{ ctx|tojson }}` 注入給前端 JS 篩選用。"""
    d = row.model_dump()
    d["key"] = key
    d["is_rain"] = is_rain
    d["rain_24h"] = rain_24h
    return d


def build_dashboard_context(
    rows: List[DashboardRow],
    rain_map: Optional[Dict[Tuple[str, str], str]] = None,
) -> dict:
    """
    純轉換函式（不碰 DB）：DashboardRow 列表 → `templates/b/dashboard.html` 渲染用 context。

    回傳形狀：
      {
        "plants": [
          {"plantno": str, "rows": [dict,...], "counts": {R,O,O2,Y,B,M}, "severity": int,
           "pills": [{"key": str, "txt": str}, ...]},
          ...
        ]（嚴重度高在前、同級按 plantno 排序）,
        "stats": {"R": int, "O": int, "Y": int, "BM": int}（四張摘要卡；O 已含 O2、BM 已含 B+M）,
        "active_anomalies": [{"plantno","item","rvalue_raw","key"}, ...]（R/O/O2 全列）,
      }
    """
    rain_map = rain_map or {}

    plant_order: List[str] = []
    plant_rows: Dict[str, List[dict]] = {}

    stats = {"R": 0, "O": 0, "Y": 0, "BM": 0}
    active_anomalies: List[dict] = []

    for row in rows:
        key = _classify_status(row)
        is_rain = "雨水溝" in row.item
        rain_24h = ""
        if is_rain:
            rain_24h = row.rain_24h or rain_map.get((row.plantno, row.item), "") or ""

        if row.plantno not in plant_rows:
            plant_order.append(row.plantno)
            plant_rows[row.plantno] = []
        plant_rows[row.plantno].append(_row_to_dict(row, key, is_rain, rain_24h))

        if key == "R":
            stats["R"] += 1
        elif key in ("O", "O2"):
            stats["O"] += 1
        elif key == "Y":
            stats["Y"] += 1
        elif key in ("B", "M"):
            stats["BM"] += 1

        if key in ("R", "O", "O2"):
            active_anomalies.append(
                {"plantno": row.plantno, "item": row.item, "rvalue_raw": row.rvalue_raw, "key": key}
            )

    plants: List[dict] = []
    for plantno in plant_order:
        entries = plant_rows[plantno]
        counts = {k: 0 for k in _COUNT_KEYS}
        for e in entries:
            if e["key"] in counts:
                counts[e["key"]] += 1
        keys_present = [e["key"] for e in entries]
        severity = min(
            (_SEVERITY_ORDER.index(k) for k in keys_present),
            default=_SEVERITY_ORDER.index("G"),
        )
        # pills 用 {key, txt} 而非純字串：key 供模板選色（vb-pill-{{ key }}），
        # txt 是顯示文字（如 'R1'／'O≠2'）。
        pills = [{"key": k, "txt": f"{_PILL_LABEL[k]}{counts[k]}"} for k in _COUNT_KEYS if counts[k] > 0]
        plants.append(
            {
                "plantno": plantno,
                "rows": entries,
                "counts": counts,
                "severity": severity,
                "pills": pills,
            }
        )

    plants.sort(key=lambda p: (p["severity"], p["plantno"]))

    # 異常速覽依嚴重度排序（R > O > O2），對齊側欄／摘要卡的視覺優先序
    active_anomalies.sort(key=lambda a: _SEVERITY_ORDER.index(a["key"]))

    return {"plants": plants, "stats": stats, "active_anomalies": active_anomalies}


def get_dashboard_page_data(db: Session, isolation_checker: Optional[IsolationChecker] = None) -> dict:
    """
    薄 DB 入口：查 B 棧儀表板資料列 + reading_current.rain_24h 組雨量對照表，交給
    `build_dashboard_context()` 做純轉換。main_b 正式接線時呼叫本函式即可。
    """
    rows = get_dashboard_rows(db, isolation_checker=isolation_checker)

    rain_stmt = select(ReadingCurrent.plant_no, ReadingCurrent.item, ReadingCurrent.rain_24h).where(
        ReadingCurrent.rain_24h.is_not(None)
    )
    rain_map: Dict[Tuple[str, str], str] = {
        (plant_no, item): str(rain_24h) for plant_no, item, rain_24h in db.execute(rain_stmt).all()
    }

    return build_dashboard_context(rows, rain_map)
