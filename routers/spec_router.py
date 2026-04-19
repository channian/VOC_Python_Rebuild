from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.spec_schema import SpecCreate, SpecUpdate, SpecResponse
from services.spec_service import list_specs, create_spec, update_spec, delete_spec
from typing import List

router = APIRouter(prefix="/spec", tags=["Spec Config"])

@router.get("/list", response_model=List[SpecResponse])
def get_spec_list(plantno: str = "", item: str = "", db: Session = Depends(get_voc_db)):
    """ 獲取廠區儀表板規格值 (GET /spec/list) """
    return list_specs(db, plantno, item)

@router.post("/create")
def add_spec(data: SpecCreate, db: Session = Depends(get_voc_db)):
    """ 新增法規參數 (POST /spec/create) """
    success = create_spec(db, current_user_empno="admin", data=data)
    if not success:
        raise HTTPException(status_code=400, detail="新增資料失敗，可能是資料重複或與資料庫連線異常")
    return {"status": "success"}

@router.post("/update")
def modify_spec(data: SpecUpdate, db: Session = Depends(get_voc_db)):
    """ 修改法規參數 (POST /spec/update) """
    success = update_spec(db, current_user_empno="admin", data=data)
    if not success:
        raise HTTPException(status_code=400, detail="修改資料失敗，可能找不到對應的規格紀錄")
    return {"status": "success"}

@router.delete("/delete")
def remove_spec(plantno: str, item: str, remark: str = "", db: Session = Depends(get_voc_db)):
    """ 刪除法規參數 (DELETE /spec/delete?plantno=xxx&item=xxx) """
    success = delete_spec(db, current_user_empno="admin", plantno=plantno, item=item, remark=remark)
    if not success:
        raise HTTPException(status_code=400, detail="刪除資料失敗，可能找不到對應的規格紀錄")
    return {"status": "success"}
