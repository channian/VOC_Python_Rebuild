"""
dept_router.py — 部門權限維護（EditDeptList 移植）

CRUD API + GET /dept/ui 渲染 dept_modal.html。
⚠️ 尚未在 main.py 註冊，待主控整合時加入 app.include_router(dept_router.router)。
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_voc_db
from schemas.dept_schema import DeptAdd, DeptUpdate, DeptDelete
from services.dept_service import (
    list_plants, list_dept_data, get_dept_name,
    add_dept, update_dept, delete_dept, is_all_plant,
)

router = APIRouter(prefix="/dept", tags=["Department Maintenance"])
templates = Jinja2Templates(directory="templates")


@router.get("/ui")
def render_dept_modal(request: Request, plantid: str = "", deptno: str = "",
                       db: Session = Depends(get_voc_db)):
    """渲染部門權限維護 Modal，可選 plantid/deptno 篩選（舊版 btn查詢）。"""
    try:
        rows = list_dept_data(db, plantid, deptno)
        plants = list_plants(db)
        error = ""
    except Exception:
        rows, plants, error = [], [], "查詢失敗，資料庫連線異常"
    return templates.TemplateResponse(
        request=request,
        name="partials/dept_modal.html",
        context={
            "depts": rows,
            "plants": plants,
            "plantid": plantid,
            "deptno": deptno,
            "error": error,
            "is_all_plant": is_all_plant,
        },
    )


@router.get("/name/{deptno}")
def api_get_dept_name(deptno: str, db: Session = Depends(get_voc_db)):
    """依部門代碼帶出部門名稱（舊版 __deptno_TextChanged → Get部門名稱）。"""
    try:
        deptname = get_dept_name(db, deptno)
    except Exception:
        raise HTTPException(status_code=500, detail="查詢失敗，資料庫連線異常")
    if not deptname:
        raise HTTPException(status_code=404, detail="部門代碼錯誤!")
    return {"deptno": deptno, "deptname": deptname}


@router.post("/add")
def api_add_dept(data: DeptAdd, db: Session = Depends(get_voc_db)):
    """新增一筆部門資料 (POST /dept/add)。"""
    try:
        add_dept(db, current_user_empno="admin", plantid=data.plantid,
                  deptno=data.deptno, remark=data.remark or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="新增失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantid}/{data.deptno} 已新增"}


@router.post("/update")
def api_update_dept(data: DeptUpdate, db: Session = Depends(get_voc_db)):
    """修改一筆部門資料 (POST /dept/update)。plantid 不可改，只能改 deptno。"""
    try:
        update_dept(db, current_user_empno="admin", plantid=data.plantid,
                     old_deptno=data.old_deptno, new_deptno=data.deptno,
                     remark=data.remark or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="修改失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantid}/{data.deptno} 已修改"}


@router.post("/delete")
def api_delete_dept(data: DeptDelete, db: Session = Depends(get_voc_db)):
    """刪除一筆部門資料 (POST /dept/delete)。"""
    try:
        delete_dept(db, current_user_empno="admin", plantid=data.plantid, deptno=data.deptno)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="刪除失敗，資料庫連線異常")
    return {"status": "success", "message": f"{data.plantid}/{data.deptno} 已刪除"}
