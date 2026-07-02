"""
異常報表 VOCreport 移植（純線上統計報表：長條圖 + PIVOT 交叉表 + 排行，非 Excel/CSV 匯出）。

對應舊系統 legacy/VOCreport.aspx.cs + legacy/dbVOC.cs 的：
    Get廠棟異常件數統計 / Get廠棟異常件數總計 / GetPIVOT廠棟異常件數 / Get廠棟異常件數最大排行

⚠️ 已修正項（舊系統 bug，本次刻意不沿用）：
    舊系統 GetPIVOT廠棟異常件數() 使用全域共用實體暫存表 [VOC].[dbo].[VOC_report]
    （DELETE 後重填、多人同時查詢會互相覆蓋資料，見 docs/legacy_source_analysis.md 第三節）。
    Python 版改為：SQL 只負責撈「原始明細列」（query_report_data），
    彙整／交叉表／排行統計全部在 Python 端做（build_summary / build_pivot / build_ranking），
    每個請求各自處理自己的資料，天然無併發互蓋問題，也不需要任何暫存表。

⚠️ 與舊系統刻意的差異（母集合範圍）：
    舊系統 Get廠棟異常件數統計 等方法的 @DT 母集合只有 VOC_SPEC⋈VOC_item⋈VOC_plant，
    「未」像 VOChistory 的 ListVOClog 一樣 UNION 雨水溝（VOC_SCADA_WEB）項目。
    本次依需求規格，母集合組法統一比照 history_service.list_voclog（SPEC ∪ 雨水溝），
    使異常報表與異常查詢頁的統計基礎一致。此為刻意擴大範圍，非還原舊系統原始行為，
    如需與舊系統逐筆對帳請留意此差異（雨水溝相關項目的件數在新版報表中會被納入統計）。

排行 CASE_RANK 語意沿用舊系統 DENSE_RANK()：件數相同 → 並列同名次，
下一個不同件數的名次緊接（不跳號），例如 5,5,3 → 名次 1,1,2（不是 1,1,3）。
"""

from collections import Counter, OrderedDict
from sqlalchemy.orm import Session
from sqlalchemy import text

# 母集合組法 / 日期預設與驗證，直接沿用 history_service（不可修改該檔案，僅 import 其純函式）
from services.history_service import default_date_range, validate_date_range  # noqa: F401


def query_report_data(
    db: Session,
    plant: str,
    item: str,
    sdate: str,
    edate: str,
    mt: bool,
) -> list[dict]:
    """
    查詢異常報表原始明細列（不在 SQL 端做統計，統計交給 build_summary / build_pivot / build_ranking）。

    對應舊系統 Get廠棟異常件數統計／GetPIVOT廠棟異常件數 的 @DT 母集合建法，
    比照 history_service.list_voclog：VOC_SPEC⋈VOC_item⋈VOC_plant ∪ 雨水溝（VOC_SCADA_WEB）。
    msg1 LIKE '%|item|%' 判定該筆 VOC_MAIL_Log 是否屬於該項目的異常件數。
    mt=False（未勾選 MT 廠全部）時，額外套用 msg2 LIKE '%|item|%'（較嚴格，對應舊系統 MT!=true 分支）。

    回傳每一列 = 一筆異常紀錄的 (plantno, item)，供 Python 端彙整。
    """
    params: dict = {"sdate": sdate, "edate": edate}

    plant_filter = "AND D.plantno = :plant " if plant else ""
    item_filter = "AND D.item = :item " if item else ""
    mt_filter = "AND (L.msg2 LIKE CONCAT('%|',D.item,'|%')) " if not mt else ""

    if plant:
        params["plant"] = plant
    if item:
        params["item"] = item

    sql = text(f"""
    WITH DT AS (
        SELECT S2.plantno, REPLACE(REPLACE(I2.item,'COD2','COD'),'pH1','pH') AS item
        FROM [VOC].[dbo].[VOC_SPEC] S2
        JOIN [VOC].[dbo].[VOC_item] I2 ON S2.item = I2.item
        JOIN [VOC].[dbo].[VOC_plant] P2 ON S2.plantno = P2.plantno
        WHERE P2.plantno NOT IN ('環工部','GMO','ALL')
        UNION
        SELECT W.plantno, I.item
        FROM [VOC].[dbo].[VOC_SCADA_WEB] W
        JOIN [VOC].[dbo].[VOC_item] I ON W.item = I.item
        JOIN [VOC].[dbo].[VOC_plant] P ON W.plantno = P.plantno
        WHERE W.item LIKE '%雨水溝%'
          AND P.plantno NOT IN ('環工部','GMO','ALL')
    )
    SELECT D.plantno, D.item,
           REPLACE(CONVERT(nvarchar(16), L.cdatetime, 120),'-','/') AS cdatetime,
           L.logid
    FROM DT D
    JOIN [VOC].[dbo].[VOC_MAIL_Log] L
         ON D.plantno = L.plantno AND L.msg1 LIKE CONCAT('%|',D.item,'|%')
    WHERE CONVERT(nvarchar(10), L.cdatetime, 111) BETWEEN :sdate AND :edate
      {plant_filter}{item_filter}{mt_filter}
    ORDER BY D.plantno, D.item, L.cdatetime
    """)

    rows = db.execute(sql, params).mappings().fetchall()
    return [dict(r) for r in rows]


def build_summary(rows: list[dict]) -> list[dict]:
    """
    各廠異常件數統計（純函式，Python 彙整，取代舊系統 Get廠棟異常件數統計）。

    回傳依件數由大到小排序（同件數依廠區代碼排序）：
        [{"plantno": "K1", "count": 12, "pct": 100.0}, ...]

    pct = 相對於最大件數的百分比寬度（供長條圖用），件數為 0 或無資料時一律 0，避免除以零。
    """
    counter: Counter = Counter(r["plantno"] for r in rows)
    if not counter:
        return []

    max_count = max(counter.values())
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    result = []
    for plantno, count in items:
        pct = round(count / max_count * 100, 1) if max_count > 0 else 0.0
        result.append({"plantno": plantno, "count": count, "pct": pct})
    return result


def build_pivot(rows: list[dict]) -> dict:
    """
    廠區 × 項目交叉表（純函式，Python 端 pivot，取代舊系統 GetPIVOT廠棟異常件數 的
    實體暫存表 + T-SQL PIVOT 語法）。

    回傳：
        {
            "columns": ["K1", "K9", ..., "Total"],   # 廠區欄位 + 合計欄
            "rows": [
                {"item": "COD", "K1": 3, "K9": 0, "Total": 3},
                ...,
                {"item": "總計", "K1": 5, "K9": 2, "Total": 7},   # 每廠合計列（永遠排最後）
            ],
        }

    無資料時回傳 columns=[]、rows=[]（不顯示交叉表，對應舊系統 dtb3==null → showdata1.Visible=false）。
    缺格（該廠該項目本期無異常）一律補 0，不留空白。
    """
    if not rows:
        return {"columns": [], "rows": []}

    plants = sorted({r["plantno"] for r in rows})
    items = sorted({r["item"] for r in rows})

    counts: Counter = Counter((r["plantno"], r["item"]) for r in rows)

    pivot_rows = []
    plant_totals: dict = {p: 0 for p in plants}
    grand_total = 0

    for it in items:
        row = OrderedDict()
        row["item"] = it
        row_total = 0
        for p in plants:
            c = counts.get((p, it), 0)
            row[p] = c
            row_total += c
            plant_totals[p] += c
        row["Total"] = row_total
        grand_total += row_total
        pivot_rows.append(row)

    # 每廠合計列（比照舊系統 VOC_report 的 '總計' plantno 列，這裡改成最後一列）
    total_row = OrderedDict()
    total_row["item"] = "總計"
    for p in plants:
        total_row[p] = plant_totals[p]
    total_row["Total"] = grand_total
    pivot_rows.append(total_row)

    return {"columns": plants + ["Total"], "rows": pivot_rows}


def build_ranking(rows: list[dict]) -> dict:
    """
    件數排行（純函式，取代舊系統 Get廠棟異常件數統計(total=false) + Get廠棟異常件數最大排行）。

    名次語意沿用舊系統 DENSE_RANK() OVER (ORDER BY SUM(CASE_TTL) DESC)：
    件數相同 → 並列同名次；下一個不同件數的名次緊接不跳號。

    回傳：
        {
            "rows": [{"plantno": "K1", "count": 12, "rank": 1}, ...],  # 依件數大到小排列
            "max_rank": 3,   # 對應舊系統 Get廠棟異常件數最大排行()，供 UI 判斷前3/後3 (Top/Bottom) 上色
        }
    無資料時 rows=[]、max_rank=0。
    """
    counter: Counter = Counter(r["plantno"] for r in rows)
    if not counter:
        return {"rows": [], "max_rank": 0}

    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    result = []
    rank = 0
    prev_count = None
    for plantno, count in items:
        if count != prev_count:
            rank += 1
            prev_count = count
        result.append({"plantno": plantno, "count": count, "rank": rank})

    return {"rows": result, "max_rank": rank}
