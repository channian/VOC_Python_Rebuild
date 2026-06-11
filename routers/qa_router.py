from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.qa_schema import QAUpdate
from services.qa_service import update_qa_value

router = APIRouter(prefix="/qa", tags=["QA Manual Value"])


@router.post("/update")
def modify_qa_value(data: QAUpdate, db: Session = Depends(get_voc_db)):
    """ 更新 QA 手測值 (POST /qa/update) — Phase 3 後改為 current_user.empno """
    try:
        update_qa_value(db, current_user_empno="admin",
                        plantno=data.plantno, item=data.item,
                        rvalue=data.rvalue, remark=data.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="更新失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantno}/{data.item} 手測值已更新"}
