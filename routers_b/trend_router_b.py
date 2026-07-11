"""
routers_b/trend_router_b.py — 歷史曲線頁 router 薄層（Schema B / PostgreSQL）

⚠️ 刻意用 /trend 前綴，不是 /history/*——/history/* 已被「異常回覆」功能佔用
（services_b/history_service.py + routers_b/spec_router_b.py 的 /ui/reason 系列），
不可撞路徑。

業務邏輯全部在 services_b/trend_service.py（可測、不依賴 FastAPI），本檔只負責：
  1. 參數解析（items 逗號字串→list、range/from/to → 時間區間）。
  2. 呼叫 service，把結果轉成 JSON 或 CSV response。
  3. /trend/ui 渲染 templates/b/history.html，注入初始下拉選單資料。

⚠️ 尚未掛進 main_b.py（main_b 尚未 include 本 router，統一接線由主控後續處理，
見任務分工——本檔案與其他三個新檔案互相獨立，main_b.py 不在本次異動範圍內）。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database_b import get_b_db
from services_b import trend_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trend")
templates = Jinja2Templates(directory="templates")


def _split_items(items: str) -> list[str]:
    return [x.strip() for x in items.split(",") if x.strip()]


def _resolve_range_or_400(range_: str, from_: str | None, to_: str | None):
    try:
        return trend_service.resolve_range(range_, from_, to_)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# ── 頁面 ──────────────────────────────────────────────────────────────────

@router.get("/ui")
def trend_ui(request: Request, plant: str = "", db: Session = Depends(get_b_db)):
    """歷史曲線頁。plant 選填，預設第一個有資料（有 SPEC）的廠。"""
    plants = trend_service.list_plants(db)
    if not plant:
        plant = plants[0]["plantno"] if plants else ""
    metrics = trend_service.list_metrics(db, plant) if plant else []
    return templates.TemplateResponse(
        request=request, name="b/history.html",
        context={"plants": plants, "plant": plant, "metrics": metrics},
    )


# ── 下拉選單 ──────────────────────────────────────────────────────────────

@router.get("/plants")
def trend_plants(db: Session = Depends(get_b_db)):
    return trend_service.list_plants(db)


@router.get("/metrics")
def trend_metrics(plant: str, db: Session = Depends(get_b_db)):
    return trend_service.list_metrics(db, plant)


# ── 趨勢資料 ──────────────────────────────────────────────────────────────

@router.get("/series")
def trend_series(
    plant: str, items: str, range: str = "7D",
    from_: str | None = Query(None, alias="from"), to: str | None = None,
    db: Session = Depends(get_b_db),
):
    item_list = _split_items(items)
    if not item_list:
        raise HTTPException(status_code=400, detail="items 不可為空")
    start, end = _resolve_range_or_400(range, from_, to)
    return trend_service.get_series(db, plant, item_list, start, end)


@router.get("/series.csv")
def trend_series_csv(
    plant: str, items: str, range: str = "7D",
    from_: str | None = Query(None, alias="from"), to: str | None = None,
    db: Session = Depends(get_b_db),
):
    item_list = _split_items(items)
    if not item_list:
        raise HTTPException(status_code=400, detail="items 不可為空")
    start, end = _resolve_range_or_400(range, from_, to)
    series = trend_service.get_series(db, plant, item_list, start, end)
    csv_text = trend_service.build_csv(plant, series)
    filename = f"voc_history_{plant}_{range}.csv"
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
