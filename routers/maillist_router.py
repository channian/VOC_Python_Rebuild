from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.maillist_schema import MailListAdd, MailListUpdate, MailListDelete
from services.maillist_service import (
    add_maillist, update_maillist, delete_maillist, lookup_employee,
    disable_all_mail, enable_all_mail, is_mail_disabled,
)

router = APIRouter(prefix="/maillist", tags=["Mail List"])


@router.get("/employee/{empno}")
def api_lookup_employee(empno: str, db: Session = Depends(get_voc_db)):
    """依工號帶出姓名與 Notes ID（群組/值班回空，由人工輸入）。"""
    return lookup_employee(db, empno)


@router.post("/add")
def api_add_maillist(data: MailListAdd, db: Session = Depends(get_voc_db)):
    """新增一筆派送名單 (POST /maillist/add)。Phase 3 後改用 current_user.empno。"""
    try:
        add_maillist(db, current_user_empno="admin", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="新增失敗，資料庫連線異常")
    return {"status": "success",
            "message": f"{data.plantno}/{data.rpttype}/{data.empno} 已新增"}


@router.post("/update")
def api_update_maillist(data: MailListUpdate, db: Session = Depends(get_voc_db)):
    """修改一筆派送名單 (POST /maillist/update)。"""
    try:
        update_maillist(db, current_user_empno="admin", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="修改失敗，資料庫連線異常")
    return {"status": "success",
            "message": f"{data.plantno}/{data.rpttype}/{data.empno} 已修改"}


@router.post("/delete")
def api_delete_maillist(data: MailListDelete, db: Session = Depends(get_voc_db)):
    """刪除一筆派送名單 (POST /maillist/delete)。"""
    try:
        delete_maillist(db, current_user_empno="admin",
                        plantno=data.plantno, rpttype=data.rpttype, empno=data.empno)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="刪除失敗，資料庫連線異常")
    return {"status": "success",
            "message": f"{data.plantno}/{data.rpttype}/{data.empno} 已刪除"}


@router.post("/toggle")
def api_toggle_mail(enable: bool, db: Session = Depends(get_voc_db)):
    """全域暫停/恢復寄信切換 (POST /maillist/toggle?enable=true|false)。"""
    try:
        if enable:
            enable_all_mail(db)
        else:
            disable_all_mail(db)
    except Exception:
        raise HTTPException(status_code=500, detail="切換失敗，資料庫連線異常")
    return {"status": "success", "disabled": is_mail_disabled(db)}
