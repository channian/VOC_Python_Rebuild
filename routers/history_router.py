from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.history_schema import ReasonUpdate
from services.history_service import (
    list_plants, list_items, list_voclog,
    update_reason, default_date_range, validate_date_range,
)

router = APIRouter(prefix="/history", tags=["異常記錄查詢"])


@router.get("/plants")
def api_history_plants(db: Session = Depends(get_voc_db)):
    """廠區清單（用於篩選下拉）"""
    return list_plants(db)


@router.get("/items")
def api_history_items(plant: str = "", db: Session = Depends(get_voc_db)):
    """項目清單（依廠區篩選，plant 空字串 → 全部項目）"""
    return list_items(db, plant)


@router.get("/logs")
def api_history_logs(
    plant: str = "",
    item: str = "",
    sdate: str = "",
    edate: str = "",
    mt: bool = False,
    db: Session = Depends(get_voc_db),
):
    """查詢 VOC_MAIL_Log 異常記錄（GET /history/logs）"""
    if not sdate or not edate:
        sdate, edate = default_date_range()
    try:
        validate_date_range(sdate, edate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return list_voclog(db, plant, item, sdate, edate, mt)


@router.post("/reply")
def api_reason_reply(data: ReasonUpdate, db: Session = Depends(get_voc_db)):
    """儲存異常原因回覆（POST /history/reply）。Phase 3 後換用 current_user.empno。"""
    try:
        update_reason(db, data.logid, data.reason, current_user_empno="admin")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存失敗：{e}")
    return {"status": "success", "message": f"logid={data.logid} 原因已儲存"}
