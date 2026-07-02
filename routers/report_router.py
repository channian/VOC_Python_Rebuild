"""
異常報表 VOCreport 移植路由。

對應舊系統 legacy/VOCreport.aspx（線上統計報表：長條圖 + PIVOT 交叉表 + 排行，非檔案匯出）。

⚠️ 本檔為新建檔案，router 註冊（main.py include_router）由主控整合，這裡不動 main.py。
"""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_voc_db
from services.history_service import list_plants, list_items
from services.report_service import (
    query_report_data,
    build_summary,
    build_pivot,
    build_ranking,
    default_date_range,
    validate_date_range,
)

router = APIRouter(prefix="/report", tags=["異常報表"])
templates = Jinja2Templates(directory="templates")


@router.get("/logs")
def api_report_logs(
    plant: str = "",
    item: str = "",
    sdate: str = "",
    edate: str = "",
    mt: bool = False,
    db: Session = Depends(get_voc_db),
):
    """
    異常報表 JSON API（GET /report/logs）。
    回傳原始明細列 + 三種彙整結果（summary/pivot/ranking），供前端或其他系統整合使用。
    """
    if not sdate or not edate:
        sdate, edate = default_date_range()
    validate_date_range(sdate, edate)

    rows = query_report_data(db, plant, item, sdate, edate, mt)
    return {
        "sdate": sdate,
        "edate": edate,
        "rows": rows,
        "summary": build_summary(rows),
        "pivot": build_pivot(rows),
        "ranking": build_ranking(rows),
    }


@router.get("/ui")
def render_report_modal(
    request: Request,
    plant: str = "", item: str = "",
    sdate: str = "", edate: str = "",
    mt: bool = False,
    db: Session = Depends(get_voc_db),
):
    """渲染異常報表 Modal（對應舊系統 VOCreport.aspx）。"""
    if not sdate or not edate:
        sdate, edate = default_date_range()

    rows, summary, pivot, ranking, error = [], [], {"columns": [], "rows": []}, {"rows": [], "max_rank": 0}, ""
    try:
        validate_date_range(sdate, edate)
        rows = query_report_data(db, plant, item, sdate, edate, mt)
        summary = build_summary(rows)
        pivot = build_pivot(rows)
        ranking = build_ranking(rows)
    except ValueError as e:
        error = str(e)
    except Exception as e:
        error = f"查詢失敗：{e}"

    return templates.TemplateResponse(
        request=request,
        name="partials/report_modal.html",
        context={
            "plants": list_plants(db),
            "items": list_items(db, plant),
            "plant": plant, "item": item,
            "sdate": sdate, "edate": edate, "mt": mt,
            "summary": summary, "pivot": pivot, "ranking": ranking,
            "total_count": sum(s["count"] for s in summary),
            "error": error,
        },
    )
