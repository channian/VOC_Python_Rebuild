from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.acl_schema import AclUserCreate, AclUserBase, AclUserResponse
from services.acl_service import list_acl_users, create_acl_user, delete_acl_user
from typing import List

router = APIRouter(prefix="/acl", tags=["ACL Rights"])

@router.get("/list", response_model=List[AclUserResponse])
def get_acl_list(plantno: str = "", roletype: str = "", empno: str = "", db: Session = Depends(get_voc_db)):
    """
    獲取廠區隔離權限名單 (GET /acl/list)
    """
    return list_acl_users(db, plantno, roletype, empno)

@router.post("/create")
def add_acl(data: AclUserCreate, db: Session = Depends(get_voc_db)):
    """
    新增權限 (POST /acl/create)
    目前操作者預設帶入 admin 測試，未來將由 Depends(get_current_user) 取代。
    """
    success = create_acl_user(db, current_user_empno="admin", data=data)
    if not success:
        raise HTTPException(status_code=400, detail="新增資料失敗，可能是資料重複或資料庫異常")
    return {"status": "success"}

@router.post("/delete")
def remove_acl(data: AclUserBase, db: Session = Depends(get_voc_db)):
    """
    刪除權限 (POST /acl/delete)
    """
    success = delete_acl_user(db, current_user_empno="admin", data=data)
    if not success:
        raise HTTPException(status_code=400, detail="刪除資料失敗，可能找不到對應的權限紀錄")
    return {"status": "success"}
