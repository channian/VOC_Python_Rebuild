"""
dashboard_service.py — 儀表板資料查詢與燈號計算

職責：
  1. 從 VOC_SPEC + VOC_SCADA_WEB JOIN 取得每個廠區/項目的最新讀值與規格值
  2. 依據三層門檻值（OOS / OOC / Alert）及 SCADA 與 SPEC 是否一致，計算燈號
  3. 回傳 DashboardRow list，供 home_router 傳給 Jinja2 模板渲染

燈號規則（與舊版 Home.aspx.cs 一致）：
  R（紅）: rvalue >= OOS
  O（橙）: OOC <= rvalue < OOS  ，或 SCADA/CWMS 管制值 ≠ SPEC 設定值
  Y（黃）: Alert < rvalue < OOC（且 alert > 0），或 rvalue > recv（且 recv > 0）
  G（綠）: 其他（正常）
  -（無）: 斷訊 / 保養中 / N.D / 無資料
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from schemas.dashboard_schema import DashboardRow

# ── 無效門檻值：SCADA 尚未建點或無法讀取，不納入比對 ──────────────────
# 注意：數值 "0" 不在此清單中（與舊系統 Home.aspx.cs 一致）——
# 若 SCADA 存 "0" 而 SPEC 有真實值，屬「未建點/設定不一致」，應亮橙燈提醒。
_INVALID_THRESHOLD = {"-", "N/A", "建置中", "異常", "保養中", ""}


def _safe_float(val, default: float = None) -> Optional[float]:
    """安全轉型為 float，失敗回傳 default"""
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


def _parse_bounds(val: Optional[str]) -> Optional[tuple]:
    """
    解析門檻值為 (低界, 高界)。

    - 單邊規格（多數項目）： '1.16' → (1.16, 1.16)
    - 雙邊規格（pH、K21 溫度）： '6-9' → (6.0, 9.0)
    - 無效值（'-' / 'N/A' / '建置中' / 空字串等）→ None

    對應舊系統 Home.aspx.cs：單邊直接 ToDecimal；雙邊先 Split('-') 取陣列。
    格式驅動，不需判斷項目名稱——值含 '-' 即雙邊，否則單邊，
    自然涵蓋「溫度只有 K21 是雙邊、其餘廠單邊」的差異。
    燈號比對一律使用「高界」[1]（與舊碼一致）。
    """
    if val is None:
        return None
    s = str(val).strip()
    if s in _INVALID_THRESHOLD:
        return None
    parts = s.split('-')
    # 雙邊規格 'low-high'（開頭非空，避免把負號誤判成分隔）
    if len(parts) >= 2 and parts[0] != '':
        lo = _safe_float(parts[0])
        hi = _safe_float(parts[1])
        if lo is None or hi is None:
            return None
        return (lo, hi)
    v = _safe_float(s)
    if v is None:
        return None
    return (v, v)


def _bounds_mismatch(scada_val, spec_val, voc_exception: bool = False) -> bool:
    """
    比對 SCADA/CWMS 管制值 vs SPEC 設定值是否一致（不一致 → 橙燈）。

    - 先四捨五入到小數 2 位再比，對齊舊系統 ChangeData(text, 2)，
      避免 SCADA 浮點精度（如 0.4999 vs 0.5）誤判。
    - 雙邊規格（pH/溫度）低界、高界都要相符才算一致。
    - voc_exception=True（僅用於 VOC 項目的 SCADA OOS/OOC 比對）：
      若 SCADA 高界 < SPEC 高界，視為「SCADA 設得更嚴」可接受，不亮橙燈。
    - 任一邊無效（'-'/'建置中'等）→ 不比對。
    """
    sb = _parse_bounds(scada_val)
    pb = _parse_bounds(spec_val)
    if sb is None or pb is None:
        return False
    if voc_exception and sb[1] < pb[1]:
        return False
    return round(sb[0], 2) != round(pb[0], 2) or round(sb[1], 2) != round(pb[1], 2)


def _calculate_light(row: dict, check_lower_bound: bool = False) -> tuple[str, bool]:
    """
    計算燈號與是否異常旗標。

    回傳 (light_status, is_anomaly)
      light_status: 'R' / 'O' / 'Y' / 'G' / '-'
      is_anomaly  : True 代表斷訊 / 保養中 / 無資料

    broken 欄位含義（與 JOB 寫入及 Web 端維護一致）：
      0 → 正常
      1 → 斷訊（SCADA Tag 品質異常）
      2 → 保養中 / 隔離中（由 Web 端隔離申請觸發）

    門檻比對說明：
      - 所有門檻經 _parse_bounds 取「高界」，自動相容單邊與雙邊（pH/溫度 '6-9'）。
      - VOC 項目：SCADA OOS/OOC 比 SPEC 嚴（更低）時不算不一致（不亮橙燈）。
      - 比對順序 R → O(範圍) → O(不一致) → Y → G，對齊舊 Home.aspx.cs
        last-wins 的等效優先序（紅 > 橙 > 黃）。

    check_lower_bound（2026-07-31 使用者確認新增）：
      - 舊系統（沿用至今的 A 棧預設行為）雙邊規格（pH/溫度 '6-9'）只比對上界，
        數值過低不示警——本參數 **預設 False**，維持這個舊行為完全不變，
        確保 A 棧（main.py，公司平行測試中）不受影響。
      - B 棧呼叫端固定傳 True：使用者已確認新系統要對雙邊規格的下界也示警
        （例如 pH 過低也要亮燈，不再只看過高）。
      - 為 True 時，僅對「雙邊規格」（_parse_bounds 回傳 low != high）額外用下界
        比對 R/O/Y，取「上界判定」與「下界判定」中較嚴重者；單邊規格（low==high）
        不受影響，因為沒有獨立的下界可比。
    """
    rvalue_raw: str = str(row.get("rvalue_raw") or "").strip()
    broken: int     = int(row.get("broken") or 0)
    item: str       = str(row.get("item") or "")

    # ── 無資料 / 斷訊 / 保養中 ──────────────────────────────────────────
    NON_NUMERIC = {"斷訊", "異常", "保養中", "N.D", "<0.05", "<0.02", "<0.01", ""}
    if broken != 0 or rvalue_raw in NON_NUMERIC:
        return "-", True

    # ── 嘗試解析讀值 ─────────────────────────────────────────────────────
    rvalue = _safe_float(rvalue_raw)
    if rvalue is None:
        return "-", True

    # 取各門檻高界（單邊 = 數值本身，雙邊 pH/溫度 = 上限）
    oos_b = _parse_bounds(row.get("oos"))
    ooc_b = _parse_bounds(row.get("ooc"))
    alert_b = _parse_bounds(row.get("alert_spec"))
    recv_b = _parse_bounds(row.get("recv"))
    oos = oos_b[1] if oos_b else None
    ooc = ooc_b[1] if ooc_b else None
    alert = alert_b[1] if alert_b else None
    recv = recv_b[1] if recv_b else None

    # VOC 項目：SCADA 管制值比 SPEC 嚴（更低）時不算不一致
    is_voc = "VOC" in item

    # ── 上界判定（既有邏輯，R → O(範圍) → Y(alert) → Y(recv) → G，不含不一致）──
    def _upper_verdict() -> str:
        if oos is not None and rvalue >= oos:
            return "R"
        if ooc is not None and oos is not None and ooc <= rvalue < oos:
            return "O"
        if alert is not None and ooc is not None and alert < rvalue < ooc:
            return "Y"
        if recv is not None and rvalue > recv:
            return "Y"
        return "G"

    # ── 下界判定（check_lower_bound=True 時才啟用，僅對雙邊規格 low != high 生效）──
    # 2026-07-31 使用者確認：pH/溫度等雙邊規格數值過低也要示警，鏡射上界的
    # R/O/Y 規則改用「<=」/「<」比對下界；單邊規格 low==high，_lo 一律為 None
    # （沒有獨立下界可比），因此對單邊項目完全不影響。
    def _lower_verdict() -> str:
        if not check_lower_bound:
            return "G"
        oos_lo = oos_b[0] if oos_b and oos_b[0] != oos_b[1] else None
        ooc_lo = ooc_b[0] if ooc_b and ooc_b[0] != ooc_b[1] else None
        alert_lo = alert_b[0] if alert_b and alert_b[0] != alert_b[1] else None
        if oos_lo is not None and rvalue <= oos_lo:
            return "R"
        if ooc_lo is not None and oos_lo is not None and oos_lo < rvalue <= ooc_lo:
            return "O"
        if alert_lo is not None and rvalue < alert_lo:
            return "Y"
        return "G"

    _RANK = {"R": 3, "O": 2, "Y": 1, "G": 0}
    light = max(_upper_verdict(), _lower_verdict(), key=lambda l: _RANK[l])

    # ── 橙燈（不一致）：SCADA/CWMS 管制值與 SPEC 設定值不一致 ─────────────
    # 意義：有人改了 SPEC 但忘了同步到 SCADA 或反過來。
    # 只在目前判定比 O 弱（Y/G）時才拉高到 O，維持與既有 R/O(範圍) 判定同序。
    if _RANK[light] < _RANK["O"] and (
        _bounds_mismatch(row.get("scada_oos"),   row.get("oos"), voc_exception=is_voc) or
        _bounds_mismatch(row.get("scada_ooc"),   row.get("ooc"), voc_exception=is_voc) or
        _bounds_mismatch(row.get("scada_alert"), row.get("alert_spec")) or
        _bounds_mismatch(row.get("cwms_oos"),    row.get("oos")) or
        _bounds_mismatch(row.get("cwms_ooc"),    row.get("ooc"))
    ):
        light = "O"

    return light, False


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
