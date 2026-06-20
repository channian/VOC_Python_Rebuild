from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.maillist_schema import MailListAdd, MailListDelete
from services.maillist_service import add_maillist, delete_maillist

router = APIRouter(prefix="/maillist", tags=["Mail List"])


@router.post("/add")
def api_add_maillist(data: MailListAdd, db: Session = Depends(get_voc_db)):
    """新增一筆派送名單 (POST /maillist/add)"""
    try:
        seqno = add_maillist(db, current_user_empno="admin",
                             plantno=data.plantno, empno=data.empno,
                             email=data.email, mailtype=data.mailtype)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="新增失敗，資料庫連線異常")
    return {"status": "success", "seqno": seqno,
            "message": f"{data.plantno} / {data.email} ({data.mailtype}) 已新增"}


@router.post("/delete")
def api_delete_maillist(data: MailListDelete, db: Session = Depends(get_voc_db)):
    """刪除一筆派送名單 (POST /maillist/delete)"""
    try:
        delete_maillist(db, current_user_empno="admin", seqno=data.seqno)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="刪除失敗，資料庫連線異常")
    return {"status": "success", "message": f"seqno={data.seqno} 已刪除"}
