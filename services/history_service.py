from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import text


def default_date_range() -> tuple[str, str]:
    """回傳本月 1 日到今天（格式 yyyy/MM/dd）"""
    today = date.today()
    return today.strftime("%Y/%m/01"), today.strftime("%Y/%m/%d")


def validate_date_range(sdate: str, edate: str) -> None:
    """開始日期不可大於結束日期，否則 raise ValueError"""
    if sdate > edate:
        raise ValueError(f"開始日期 {sdate} 不可大於結束日期 {edate}")


def align_to_5min(dt_str: str) -> str:
    """
    把 'yyyy/MM/dd HH:mm' 或 'yyyy/MM/dd HH:mm:ss' 對齊到 5 分鐘邊界（向下取整）。
    對應舊系統 VOCreason gvList_RowUpdating 裡的 dt1.AddMinutes(-m) 邏輯。
    """
    fmt = "%Y/%m/%d %H:%M:%S" if dt_str.count(":") == 2 else "%Y/%m/%d %H:%M"
    try:
        dt = datetime.strptime(dt_str.strip(), fmt)
    except ValueError:
        return dt_str
    aligned = dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)
    return aligned.strftime("%Y/%m/%d %H:%M")


def classify_msg(msg: str) -> str:
    """
    依異常訊息內容分類，決定對應的 mail 函式（待 JOB 原始碼後補全）。
    對應舊系統 VOCreason gvList_RowUpdating 的 SendMail_* 判斷邏輯。
    """
    if "24H累積雨量" in msg:
        return "雨水溝"
    if "水質異常" in msg:
        return "水質異常"
    if "改排水" in msg:
        return "改排水"
    return "normal"


def list_plants(db: Session) -> list[str]:
    rows = db.execute(text(
        "SELECT plantno FROM [VOC].[dbo].[VOC_plant] "
        "WHERE plantno NOT IN ('環工部','GMO','ALL') ORDER BY sort"
    )).fetchall()
    return [r[0] for r in rows]


def list_items(db: Session, plant: str = "") -> list[str]:
    """
    回傳項目清單，對應舊系統 List項目1()（含雨水溝）。
    有 plant 時取該廠 VOC_SPEC 中的項目；無 plant 時取 VOC_item 全部有效項目。
    """
    if plant:
        rows = db.execute(text(
            "SELECT DISTINCT REPLACE(REPLACE(I.item,'COD2','COD'),'pH1','pH') AS item "
            "FROM [VOC].[dbo].[VOC_SPEC] S "
            "JOIN [VOC].[dbo].[VOC_item] I ON S.item = I.item "
            "WHERE S.item NOT IN ('pH2') AND S.plantno = :plant "
            "ORDER BY item"
        ), {"plant": plant}).fetchall()
    else:
        rows = db.execute(text(
            "SELECT DISTINCT item FROM [VOC].[dbo].[VOC_item] "
            "WHERE item NOT IN ('COD1','COD2','pH1','pH2') AND IsActive = 1 "
            "ORDER BY itemid"
        )).fetchall()
    return [r[0] for r in rows]


def list_voclog(
    db: Session,
    plant: str,
    item: str,
    sdate: str,
    edate: str,
    mt: bool,
    stime: str = "",
    stype: str = "",
    change: str = "",
) -> list[dict]:
    """
    對應舊系統 dbVOC.ListVOClog。

    mt=False → 加 msg2 LIKE '%|item|%' 限制（更嚴格，舊系統 MT 未勾選時套用）。
    stime="" → 日期範圍查詢；stime!='' → 精確時間查詢（VOCreason 由列按鈕帶入）。
    stype="" → 含一般 VOC_SPEC 監測項目；stype!='' → 僅雨水溝。
    change="Y" → 僅顯示「改排水」記錄；change!="Y"（預設）→ 含一般監測項目。

    因 Python 不能跨連線共用 @DT 暫存資料表，改用 CTE 實作（同等效果）。
    """
    params: dict = {}

    # 時間條件
    if stime:
        time_main = "REPLACE(CONVERT(nvarchar(16), L.CDATETIME, 120),'-','/') = :stime"
        time_rain = "REPLACE(CONVERT(nvarchar(16), S.CDATETIME, 120),'-','/') = :stime"
        params["stime"] = stime
    else:
        time_main = "CONVERT(nvarchar(10), L.CDATETIME, 111) BETWEEN :sdate AND :edate"
        time_rain = "CONVERT(nvarchar(10), S.CDATETIME, 111) BETWEEN :sdate AND :edate"
        params["sdate"] = sdate
        params["edate"] = edate

    # 廠區 / 項目篩選
    plant_filter = "AND D.plantno = :plant " if plant else ""
    item_filter = "AND D.item = :item " if item else ""
    mt_filter = "AND (L.msg2 LIKE CONCAT('%|',D.item,'|%')) " if not mt else ""
    plant_filter2 = "AND S.plantno = :plant " if plant else ""

    if plant:
        params["plant"] = plant
    if item:
        params["item"] = item

    # DT CTE：監測項目母集合
    if stype == "":
        dt_spec_part = """
            SELECT S2.plantno, REPLACE(REPLACE(I2.item,'COD2','COD'),'pH1','pH') AS item
            FROM [VOC].[dbo].[VOC_SPEC] S2
            JOIN [VOC].[dbo].[VOC_item] I2 ON S2.item = I2.item
            JOIN [VOC].[dbo].[VOC_plant] P2 ON S2.plantno = P2.plantno
            WHERE P2.plantno NOT IN ('環工部','GMO','ALL')
            UNION"""
    else:
        dt_spec_part = ""

    cte = f"""
    WITH DT AS (
        {dt_spec_part}
        SELECT W.plantno, I.item
        FROM [VOC].[dbo].[VOC_SCADA_WEB] W
        JOIN [VOC].[dbo].[VOC_item] I ON W.item = I.item
        JOIN [VOC].[dbo].[VOC_plant] P ON W.plantno = P.plantno
        WHERE W.item LIKE '%雨水溝%'
          AND P.plantno NOT IN ('環工部','GMO','ALL')
    )"""

    inner_parts = []

    if change != "Y":
        inner_parts.append(f"""
        SELECT D.plantno, D.item,
               REPLACE(CONVERT(nvarchar(16), L.cdatetime, 120),'-','/') AS cdatetime,
               L.msg,
               IIF(L.empno='','', ISNULL(E.empname,'') + '/' + ISNULL(E.notesid,'')) AS emp,
               L.reason,
               REPLACE(CONVERT(nvarchar(16), L.rdatetime, 120),'-','/') AS rdatetime,
               L.logid, L.msg1
        FROM DT D
        JOIN [VOC].[dbo].[VOC_MAIL_Log] L
             ON D.plantno = L.plantno AND L.msg1 LIKE CONCAT('%|',D.item,'|%')
        LEFT JOIN [UTIDB].[dbo].[Employee] E ON L.empno = E.empno
        WHERE {time_main}
          {plant_filter}{item_filter}{mt_filter}""")

    # 改排水記錄（永遠包含，plant 篩選直接套在 VOC_MAIL_Log 上）
    inner_parts.append(f"""
    SELECT S.plantno, '' AS item,
           REPLACE(CONVERT(nvarchar(16), S.cdatetime, 120),'-','/') AS cdatetime,
           S.msg,
           IIF(S.empno='','', ISNULL(E.empname,'') + '/' + ISNULL(E.notesid,'')) AS emp,
           S.reason,
           REPLACE(CONVERT(nvarchar(16), S.rdatetime, 120),'-','/') AS rdatetime,
           S.logid, S.msg1
    FROM [VOC].[dbo].[VOC_MAIL_Log] S
    LEFT JOIN [UTIDB].[dbo].[Employee] E ON S.empno = E.empno
    WHERE {time_rain}
      {plant_filter2}AND S.msg LIKE '%改排水%'""")

    inner = " UNION ".join(inner_parts)

    # 外層 SELECT：stime 模式不選 item 也不加 ROW_NUMBER（與舊系統一致）
    if stime:
        outer_cols = "T.plantno, T.cdatetime, T.msg, T.emp, T.reason, T.rdatetime, T.logid, T.msg1"
    else:
        outer_cols = (
            "T.plantno, T.item, "
            "ROW_NUMBER() OVER(ORDER BY T.cdatetime) AS no, "
            "T.cdatetime, T.msg, T.emp, T.reason, T.rdatetime, T.logid, T.msg1"
        )

    sql = text(f"""
    {cte}
    SELECT {outer_cols}
    FROM ({inner}) T
    ORDER BY T.cdatetime
    """)

    rows = db.execute(sql, params).mappings().fetchall()
    return [dict(r) for r in rows]


def update_reason(db: Session, logid: int, reason: str, current_user_empno: str) -> None:
    """
    儲存異常原因回覆，對應舊系統 Update異常原因。
    Mail 通知由外部 JOB 處理（SendMail_廠務法規許可值標準化管控報表 等），
    待取得 JOB 原始碼後補齊 classify_msg 對應的四種 mail 函式。
    """
    db.execute(
        text(
            "UPDATE [VOC].[dbo].[VOC_MAIL_Log] "
            "SET empno = :empno, reason = :reason, rdatetime = :rdatetime "
            "WHERE logid = :logid"
        ),
        {
            "empno": current_user_empno,
            "reason": reason.strip(),
            "rdatetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S.000"),
            "logid": logid,
        },
    )
    db.commit()
