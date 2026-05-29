"""
dashboard_service.py — 儀表板資料查詢與燈號計算

職責：
  1. 從 VOC_SPEC + VOC_SCADA_WEB JOIN 取得每個廠區/項目的最新讀值與規格值
  2. 依據三層門檻值（OOS / OOC / Alert）及 SCADA 與 SPEC 是否一致，計算燈號
  3. 回傳 DashboardRow list，供 home_router 傳給 Jinja2 模板渲染

燈號規則（與舊版 Home.aspx.cs 一致）：
  R（紅）: rvalue >= OOS
  O（橙）: OOC <= rvalue < OOS  ，或 SCADA/CWMS 管制值 ≠ SPEC 設定值
  Y（黃）: Alert < rvalue < OOC ，或 rvalue > recv（允收值）
  G（綠）: 其他（正常）
  -（無）: 斷訊 / 保養中 / N.D / 無資料
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from schemas.dashboard_schema import DashboardRow

# ── 判斷某個 SCADA/CWMS 管制值是否「有效」（可以拿來比對）──────────────
_INVALID_THRESHOLD = {"-", "N/A", "建置中", "異常", "保養中", ""}

def _is_valid_threshold(val: Optional[str]) -> bool:
    """管制值若為這些文字，代表 SCADA 尚未建點或無法讀取，不納入比對"""
    if val is None:
        return False
    return str(val).strip() not in _INVALID_THRESHOLD

def _safe_float(val, default: float = None) -> Optional[float]:
    """安全轉型為 float，失敗回傳 default"""
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default

def _spec_mismatch(scada_val: Optional[str], spec_val: Optional[str]) -> bool:
    """
    比對 SCADA 系統自設的管制值 vs SPEC 三階文件的設定值是否一致。
    不一致代表有人改了其中一邊但忘了同步 → 橙燈。

    只有兩邊都是有效數字時才比對，避免誤判。
    """
    if not _is_valid_threshold(scada_val) or not _is_valid_threshold(spec_val):
        return False
    s = _safe_float(scada_val)
    p = _safe_float(spec_val)
    if s is None or p is None:
        return False
    return s != p


def _calculate_light(row: dict) -> tuple[str, bool]:
    """
    計算燈號與是否異常旗標。

    回傳 (light_status, is_anomaly)
      light_status: 'R' / 'O' / 'Y' / 'G' / '-'
      is_anomaly  : True 代表斷訊 / 保養中 / 無資料

    broken 欄位含義（與 JOB 寫入及 Web 端維護一致）：
      0 → 正常
      1 → 斷訊（SCADA Tag 品質異常）
      2 → 保養中 / 隔離中（由 Web 端隔離申請觸發）
    """
    rvalue_raw: str = str(row.get("rvalue_raw") or "").strip()
    broken: int     = int(row.get("broken") or 0)

    # ── 無資料 / 斷訊 / 保養中 ──────────────────────────────────────────
    NON_NUMERIC = {"斷訊", "異常", "保養中", "N.D", "<0.05", "<0.02", "<0.01", ""}
    if broken != 0 or rvalue_raw in NON_NUMERIC:
        return "-", True

    # ── 嘗試解析讀值 ─────────────────────────────────────────────────────
    rvalue = _safe_float(rvalue_raw)
    if rvalue is None:
        return "-", True

    oos   = _safe_float(row.get("oos"))
    ooc   = _safe_float(row.get("ooc"))
    alert = _safe_float(row.get("alert_spec"))
    recv  = _safe_float(row.get("recv"))

    # ── 紅燈：讀值 >= OOS ────────────────────────────────────────────────
    if oos is not None and rvalue >= oos:
        return "R", False

    # ── 橙燈（條件 1）：讀值落在 OOC ~ OOS 之間 ─────────────────────────
    if ooc is not None and oos is not None and ooc <= rvalue < oos:
        return "O", False

    # ── 橙燈（條件 2）：SCADA/CWMS 管制值與 SPEC 設定值不一致 ─────────────
    # 意義：有人改了 SPEC 但忘了同步到 SCADA 或反過來
    if (
        _spec_mismatch(row.get("scada_oos"),   row.get("oos"))   or
        _spec_mismatch(row.get("scada_ooc"),   row.get("ooc"))   or
        _spec_mismatch(row.get("scada_alert"), row.get("alert_spec")) or
        _spec_mismatch(row.get("cwms_oos"),    row.get("oos"))   or
        _spec_mismatch(row.get("cwms_ooc"),    row.get("ooc"))
    ):
        return "O", False

    # ── 黃燈（條件 1）：讀值落在 Alert ~ OOC 之間 ────────────────────────
    if alert is not None and ooc is not None and alert < rvalue < ooc:
        return "Y", False

    # ── 黃燈（條件 2）：讀值超過允收值 ──────────────────────────────────
    if recv is not None and rvalue > recv:
        return "Y", False

    # ── 綠燈：正常 ───────────────────────────────────────────────────────
    return "G", False


def get_dashboard_data(db: Session, plant_permissions: str = "29") -> List[DashboardRow]:
    """
    取得首頁儀表板所有廠區 × 項目的合規狀態。

    plant_permissions:
        "29"        → 看所有廠區（系統管理員 / 環工部）
        "1,2,3"     → 只看 plantid 在清單內的廠區

    取代舊版：
        dbVOC.cs  ListVOC()
        Home.aspx.cs gvVOCList_RowCreated() 燈號判斷邏輯
    """

    # 廠區過濾（plantid=29 代表 ALL，直接不加 WHERE 條件）
    ids = [x.strip() for x in plant_permissions.split(",")]
    if "29" in ids:
        plant_filter = ""
    else:
        # 只允許數字，防止 SQL Injection
        safe_ids = [i for i in ids if i.isdigit()]
        plant_filter = f"AND P.plantid IN ({','.join(safe_ids)})" if safe_ids else "AND 1=0"

    sql = text(f"""
        SELECT
            S.plantno,
            REPLACE(REPLACE(S.item, 'COD2', 'COD'), 'pH1', 'pH') AS item,
            S.LAW       AS law_spec,
            S.OOS       AS oos,
            S.OOC       AS ooc,
            S.alert     AS alert_spec,
            S.recv      AS recv,
            S.source    AS source,
            S.seqno     AS seqno,
            I.unit,
            P.plantid,
            P.sort      AS plant_sort,
            W.OOS_HH    AS scada_oos,
            W.OOC_H     AS scada_ooc,
            W.alert     AS scada_alert,
            W.OOS_HH1   AS cwms_oos,
            W.OOC_H1    AS cwms_ooc,
            W.OOS_LL    AS scada_oos_ll,
            W.OOC_L     AS scada_ooc_l,
            W.alert_L   AS scada_alert_l,
            W.rvalue    AS rvalue_raw,
            REPLACE(REPLACE(REPLACE(REPLACE(
                W.rvalue, 'N.D', '0'), '<0.05', '0'), '<0.02', '0'), '<0.01', '0'
            )           AS rvalue,
            W.broken,
            C.URL       AS url,
            CONCAT(
                IIF(W.broken IS NULL OR W.broken = 0, '', '斷訊'),
                IIF(W.rvalue = 'N.D', 'N.D', ''),
                IIF(W.rvalue = '<0.05', '<0.05', ''),
                IIF(W.rvalue = '<0.02', '<0.02', ''),
                IIF(W.rvalue = '<0.01', '<0.01', ''),
                '|',
                CAST(S.source AS NVARCHAR)
            )           AS remark,
            E.emptycell
        FROM  [VOC].[dbo].[VOC_SPEC]      S
        JOIN  [VOC].[dbo].[VOC_item]      I  ON S.item    = I.item
        JOIN  [VOC].[dbo].[VOC_plant]     P  ON S.plantno = P.plantno AND P.isShow = 1
        LEFT JOIN [VOC].[dbo].[VOC_SCADA_WEB] W
                                             ON S.plantno = W.plantno AND S.item = W.item
        LEFT JOIN [VOC].[dbo].[VOC_Curve] C  ON S.plantno = C.plantno AND S.item = C.item
        LEFT JOIN [VOC].[dbo].[VOC_EmptyCell] E
                                             ON S.plantno = E.plantno AND S.item = E.item
        WHERE 1=1 {plant_filter}
        ORDER BY P.sort, S.seqno
    """)

    try:
        rows = db.execute(sql).mappings().all()
    except Exception as e:
        # 連線失敗時 log 錯誤，回傳空清單（讓頁面顯示「無資料」而非 500）
        print(f"[dashboard_service] DB 查詢失敗: {e}")
        return []

    result: List[DashboardRow] = []
    for row in rows:
        row = dict(row)
        light, is_anomaly = _calculate_light(row)

        result.append(DashboardRow(
            plantno    = str(row.get("plantno", "")),
            item       = str(row.get("item", "")),
            unit       = str(row.get("unit") or ""),
            law_spec   = str(row.get("law_spec") or ""),
            oos        = str(row.get("oos") or ""),
            ooc        = str(row.get("ooc") or ""),
            alert_spec = str(row.get("alert_spec") or ""),
            recv       = str(row.get("recv") or ""),
            source     = int(row.get("source") or 1),
            rvalue_raw = str(row.get("rvalue_raw") or ""),
            rvalue     = str(row.get("rvalue") or ""),
            scada_oos  = str(row.get("scada_oos") or ""),
            scada_ooc  = str(row.get("scada_ooc") or ""),
            scada_alert= str(row.get("scada_alert") or ""),
            cwms_oos   = str(row.get("cwms_oos") or ""),
            cwms_ooc   = str(row.get("cwms_ooc") or ""),
            broken     = int(row.get("broken") or 0),
            url        = str(row.get("url") or ""),
            remark     = str(row.get("remark") or ""),
            emptycell  = str(row.get("emptycell") or ""),
            light_status = light,
            is_anomaly   = is_anomaly,
        ))

    # 後處理：計算廠區 rowspan 與紅燈旗標，供 Jinja2 渲染 <td rowspan> 用
    return _annotate_plant_groups(result)


def _annotate_plant_groups(rows: List[DashboardRow]) -> List[DashboardRow]:
    """
    為每列標注廠區分組資訊，讓 Jinja2 模板可以渲染 rowspan：
      - plant_rowspan : 該廠區第一列設為列數，後續列設 0
      - show_plant    : 只有第一列為 True（後續列不渲染 <td>）
      - plant_has_red : 只要廠區內有任何紅燈，全廠區格背景變紅
    """
    from collections import defaultdict

    # 第一遍：統計每個廠區的資料列數 + 是否有紅燈
    plant_count: dict[str, int]  = defaultdict(int)
    plant_red:   dict[str, bool] = defaultdict(bool)
    for r in rows:
        plant_count[r.plantno] += 1
        if r.light_status == "R":
            plant_red[r.plantno] = True

    # 統計廠區「內部」的 emptycell 分隔行數（非第一列才算）。
    # 這些分隔行會在 template 插入額外 <tr>，必須計入 rowspan，
    # 否則廠區 <td rowspan> 提早用完，後續欄位往左位移。
    plant_inner_empty: dict[str, int] = defaultdict(int)
    first_seen: set[str] = set()
    for r in rows:
        if r.plantno in first_seen and r.emptycell:
            plant_inner_empty[r.plantno] += 1
        first_seen.add(r.plantno)

    # 第二遍：標注每列
    seen: set[str] = set()
    for r in rows:
        if r.plantno not in seen:
            r.plant_rowspan = plant_count[r.plantno] + plant_inner_empty[r.plantno]
            r.show_plant    = True
            seen.add(r.plantno)
        else:
            r.plant_rowspan = 0
            r.show_plant    = False
        r.plant_has_red = plant_red[r.plantno]

    return rows
