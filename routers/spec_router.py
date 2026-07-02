from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_voc_db
from schemas.spec_schema import (
    SpecCreate, SpecUpdate, SpecResponse,
    SpecApplyCreate, SpecApplyListResponse, SpecSignAction,
)
from services.spec_service import (
    list_specs, create_spec, update_spec, delete_spec,
    create_spec_apply, list_spec_applies, list_spec_todos, process_spec_sign,
)
from typing import List

router = APIRouter(prefix="/spec", tags=["Spec Config"])

# 注意：目前系統尚未串接登入驗證（ACL 全開，見 CLAUDE.md 已知待辦 #1），
# 這裡沿用 control_router.py / flow_router.py 既有作法，先寫死 "admin" 模擬登入者。

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


# ── 規格簽核申請（VOC_SPEC_apply，落差清單 #5）───────────────────────────────

@router.post("/apply")
def apply_spec(data: SpecApplyCreate, db: Session = Depends(get_voc_db)):
    """ 送出規格新增/修改/刪除申請單 (POST /spec/apply，對應 legacy SPEC送簽) """
    try:
        formid = create_spec_apply(db, current_user_empno="admin", current_user_name="系統管理員", data=data)
        return {"status": "success", "message": "規格申請已送出", "formid": formid}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")

@router.get("/applies", response_model=List[SpecApplyListResponse])
def fetch_spec_applies(
    sdate: str = "", edate: str = "", plantno: str = "", statusid: int = -1, formid: int = -1,
    db: Session = Depends(get_voc_db),
):
    """ 查詢我的規格申請單 (等同 ApplySPEC.aspx) """
    return list_spec_applies(db, cempno="admin", sdate=sdate, edate=edate, plantno=plantno, statusid=statusid, formid=formid)

@router.get("/todos", response_model=List[SpecApplyListResponse])
def fetch_spec_todos(sdate: str = "", edate: str = "", formid: int = -1, db: Session = Depends(get_voc_db)):
    """ 查詢待我簽核的規格申請單 (等同 SignSPEC.aspx) """
    return list_spec_todos(db, empno="admin", sdate=sdate, edate=edate, formid=formid)

@router.post("/sign")
def sign_spec_apply(action: SpecSignAction, db: Session = Depends(get_voc_db)):
    """ 送出規格申請單簽核結果 (核准/否決)。actionid: 1=核准, 9=否決 """
    try:
        process_spec_sign(db, action, current_user_empno="admin", current_user_name="系統管理員")
        return {"status": "success", "message": "簽核已送出"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")
