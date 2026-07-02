from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_voc_db
from schemas.control_schema import ApplyListResponse
from schemas.flow_schema import SignAction
from services.flow_service import get_todo_applies, process_sign

router = APIRouter(prefix="/flow", tags=["Sign Workflow"])

@router.get("/todos", response_model=List[ApplyListResponse])
def fetch_todos(sdate: str = "", edate: str = "", ccid: int = -1, db: Session = Depends(get_voc_db)):
    """ 取得待辦簽核事項 (SignControl / SignSPEC) """
    return get_todo_applies(db, cempno="admin", sdate=sdate, edate=edate, ccid=ccid)

@router.post("/sign")
def sign_apply(action: SignAction, db: Session = Depends(get_voc_db)):
    """ 送出簽核結果 (核准/否決)。actionid: 1=核准, 9=否決 (見 schemas/flow_schema.py) """
    try:
        process_sign(db, action, current_user_empno="admin", current_user_name="系統管理員")
        return {"status": "success", "message": "簽核已送出"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
