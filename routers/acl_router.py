from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.acl_schema import AclUserCreate, AclUserUpdate, AclUserBase, AclUserResponse
from services.acl_service import (
    list_acl_users, create_acl_user, update_acl_user, delete_acl_user,
    get_role_list, get_plant_list, lookup_employee,
)
from typing import List

router = APIRouter(prefix="/acl", tags=["ACL Rights"])


@router.get("/list", response_model=List[AclUserResponse])
def get_acl_list(plantno: str = "", roletype: str = "", empno: str = "", db: Session = Depends(get_voc_db)):
    """
    獲取廠區隔離權限名單 (GET /acl/list)
    真實 DB 查詢，連線失敗回 500（不再有 mock fallback）。
    """
    try:
        return list_acl_users(db, plantno, roletype, empno)
    except Exception:
        raise HTTPException(status_code=500, detail="查詢失敗，資料庫連線異常")


@router.get("/roles")
def get_acl_roles(db: Session = Depends(get_voc_db)):
    """角色下拉選單 (GET /acl/roles) — 對應舊版 List權限()，僅隔離維護(3)/隔離查詢(7)。"""
    try:
        return get_role_list(db)
    except Exception:
        raise HTTPException(status_code=500, detail="查詢角色清單失敗，資料庫連線異常")


@router.get("/plants")
def get_acl_plants(db: Session = Depends(get_voc_db)):
    """廠區下拉選單 (GET /acl/plants) — 對應舊版 List廠區6()。"""
    try:
        return get_plant_list(db)
    except Exception:
        raise HTTPException(status_code=500, detail="查詢廠區清單失敗，資料庫連線異常")


@router.get("/employee/{empno}")
def api_lookup_employee(empno: str, db: Session = Depends(get_voc_db)):
    """依工號帶出姓名與 Notes ID（查不到回空，容許手動輸入）。"""
    return lookup_employee(db, empno)


@router.post("/create")
def add_acl(data: AclUserCreate, db: Session = Depends(get_voc_db)):
    """
    新增權限 (POST /acl/create)
    目前操作者預設帶入 admin 測試，未來將由 Depends(get_current_user) 取代。
    """
    try:
        create_acl_user(db, current_user_empno="admin", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="新增資料失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantno}/{data.role_id}/{data.empno} 已新增"}


@router.post("/update")
def update_acl(data: AclUserUpdate, db: Session = Depends(get_voc_db)):
    """修改權限 (POST /acl/update)。roleid+plantno+舊工號 定位。"""
    try:
        update_acl_user(db, current_user_empno="admin", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="修改資料失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantno}/{data.role_id}/{data.empno} 已修改"}


@router.post("/delete")
def remove_acl(data: AclUserBase, db: Session = Depends(get_voc_db)):
    """
    刪除權限 (POST /acl/delete)
    """
    try:
        delete_acl_user(db, current_user_empno="admin", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="刪除資料失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantno}/{data.role_id}/{data.empno} 已刪除"}
