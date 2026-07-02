from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.control_schema import ControlCreate, ControlModify, ControlTimeUpdate, ApplyListResponse, ControlTagResponse
from services.control_service import (
    create_control, submit_control, get_my_applies, get_control_tags,
    modify_control, update_control_time, RIGHTSID_CONTROL_TIME,
)
from services.acl_service import check_permission
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

@router.post("/submit/{ccid}")
def submit_plant_exception(ccid: int, db: Session = Depends(get_voc_db)):
    """ 把先前暫存的隔離申請單正式送出簽核 (對應舊版 Proc送簽) """
    try:
        submit_control(db, ccid=ccid, current_user_empno="admin", current_user_name="系統管理員")
        return {"status": "success", "message": "已送出簽核"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")

@router.post("/modify")
def modify_plant_exception(data: ControlModify, is_commit: bool = True, db: Session = Depends(get_voc_db)):
    """
    針對已核准且仍有效的隔離單建立修改單 (POST /control/modify，對應舊版 ModifyControl.aspx)。
    建立完成後仍需走簽核（見 services/control_service.modify_control）；
    核准後回寫原單 stime/etime 的邏輯在 services/flow_service.process_sign。
    """
    try:
        modify_control(db, current_user_empno="admin", current_user_name="系統管理員", data=data, is_commit=is_commit)
        msg = "隔離廠區項目區間" + ("送簽" if is_commit else "暫存") + "成功"
        return {"status": "success", "message": msg}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


@router.post("/time")
def update_plant_exception_time(data: ControlTimeUpdate, db: Session = Depends(get_voc_db)):
    """
    隔離時間修改 (POST /control/time，對應舊版 ControlTime.aspx)。
    僅限具備 rightsid=12（隔離時間修改）權限者使用；依 legacy/dbVOC.cs Update隔離廠區項目() 確認，
    這支功能直接改主表、不走簽核流程，見 services/control_service.update_control_time 註解。
    """
    current_user_empno = "admin"  # Phase 3 換成 current_user.empno（見 HANDOVER.md AD/LDAP 整合）
    if not check_permission(db, empno=current_user_empno, rightsid=RIGHTSID_CONTROL_TIME, action="modify"):
        raise HTTPException(status_code=403, detail="無隔離時間修改權限")
    try:
        update_control_time(db, current_user_empno=current_user_empno, data=data)
        return {"status": "success", "message": "隔離廠區項目結束時間修改成功"}
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
