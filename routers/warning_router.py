from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List

from database import get_voc_db
from schemas.warning_schema import RainGutterItem, WaterUrgentRequest
from services.warning_service import (
    get_raingutter_list, get_current_anomalies, trigger_water_notify,
    get_water_plants, list_change_reasons,
)

router = APIRouter(prefix="/warning", tags=["Warnings & Notifications"])
templates = Jinja2Templates(directory="templates")


@router.get("/raingutter", response_model=List[RainGutterItem])
def fetch_raingutter(db: Session = Depends(get_voc_db)):
    """ 取得雨水溝預警狀態清單 """
    try:
        return get_raingutter_list(db)
    except Exception:
        raise HTTPException(status_code=500, detail="雨水溝資料查詢失敗，資料庫連線異常")


@router.get("/anomalies")
def fetch_anomalies(db: Session = Depends(get_voc_db)):
    """ 取得目前紅/橙燈異常清單 """
    try:
        return get_current_anomalies(db)
    except Exception:
        raise HTTPException(status_code=500, detail="異常清單查詢失敗，資料庫連線異常")


@router.get("/water_urgent/ui")
def render_water_urgent_modal(request: Request, db: Session = Depends(get_voc_db)):
    """渲染中水緊急通知 Modal（對應舊版 WaterUrgent.aspx）。"""
    try:
        plants = get_water_plants(db, exclude_k14b=True)
        reasons = list_change_reasons(db)
        error = ""
    except Exception:
        plants, reasons, error = [], [], "查詢失敗，資料庫連線異常"
    return templates.TemplateResponse(
        request=request,
        name="partials/water_urgent_modal.html",
        context={"plants": plants, "reasons": reasons, "error": error},
    )


@router.post("/water_urgent")
def post_water_urgent(req: WaterUrgentRequest, bg_tasks: BackgroundTasks,
                       db: Session = Depends(get_voc_db)):
    """ 觸發水質異常或改排水通知（依 legacy SendMail_水質異常通知/SendMail_改排水通知 邏輯移植）"""
    try:
        sent = trigger_water_notify(db, req, bg_tasks)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="通知觸發失敗，資料庫連線異常")

    if not sent:
        return {"status": "empty", "message": "沒有符合條件的收件人或資料，未寄出通知"}
    return {"status": "success", "message": "通知已排入背景發送程序"}
