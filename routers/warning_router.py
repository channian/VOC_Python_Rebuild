from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from database import get_voc_db
from schemas.warning_schema import RainGutterItem, WaterUrgentRequest
from services.warning_service import get_raingutter_list, trigger_water_notify

router = APIRouter(prefix="/warning", tags=["Warnings & Notifications"])

@router.get("/raingutter", response_model=List[RainGutterItem])
def fetch_raingutter(db: Session = Depends(get_voc_db)):
    """ 取得雨水溝預警狀態清單 """
    return get_raingutter_list(db)

@router.post("/water_urgent")
def post_water_urgent(req: WaterUrgentRequest, bg_tasks: BackgroundTasks):
    """ 觸發水質異常或改排水通知 """
    try:
        trigger_water_notify(req, bg_tasks)
        return {"status": "success", "message": "通知已排入背景發送程序"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
