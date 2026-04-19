from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.control_schema import ControlCreate, ControlResponse
from services.control_service import create_control
from builtins import ValueError

router = APIRouter(prefix="/control", tags=["Plant Exception Control"])

@router.post("/create")
def apply_plant_exception(data: ControlCreate, is_commit: bool = True, db: Session = Depends(get_voc_db)):
    """ 
    新增廠區異常隔離申請 (POST /control/create)
    預設直接送簽 (is_commit=True)
    """
    try:
        # Mock user identity
        success = create_control(db, current_user_empno="admin", current_user_name="系統管理員", data=data, is_commit=is_commit)
        return {"status": "success", "message": "申請已成功送出"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")
