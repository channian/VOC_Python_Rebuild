from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.control_schema import ControlCreate, ApplyListResponse, ControlTagResponse
from services.control_service import create_control, get_my_applies, get_control_tags
from builtins import ValueError
from typing import List

router = APIRouter(prefix="/control", tags=["Plant Exception Control"])

@router.post("/create")
def apply_plant_exception(data: ControlCreate, is_commit: bool = True, db: Session = Depends(get_voc_db)):
    """ 新增廠區異常隔離申請 (POST /control/create) """
    try:
        success = create_control(db, current_user_empno="admin", current_user_name="系統管理員", data=data, is_commit=is_commit)
        return {"status": "success", "message": "申請已成功送出"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")

@router.get("/my_apply", response_model=List[ApplyListResponse])
def fetch_my_apply_list(sdate: str = "", edate: str = "", plantid: int = -1, statusid: int = -1, ccid: int = -1, db: Session = Depends(get_voc_db)):
    """ 查詢個人申請單清單 (等同 MyApply.aspx) """
    # 預設以 admin 模擬登入者工號
    return get_my_applies(db, cempno="admin", sdate=sdate, edate=edate, plantid=plantid, statusid=statusid, ccid=ccid)

@router.get("/tags/{ccid}", response_model=List[ControlTagResponse])
def fetch_control_tags(ccid: int, db: Session = Depends(get_voc_db)):
    """ 在清單中選擇申請單後，展開查詢的附屬 TAG 明細標籤 """
    return get_control_tags(db, ccid=ccid)
