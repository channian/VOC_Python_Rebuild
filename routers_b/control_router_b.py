"""
routers_b/control_router_b.py — B 棧「廠區隔離＋簽核」router 薄層（WP6 補完）

延續 routers_b/ui_router_b.py 的原則：URL 與 A 棧 routers/control_router.py、flow_router.py、
ui_router.py 對齊，templates/partials/control_modal.html、flow_modal.html、control_items.html
與其中的前端 JS 完全不用改；業務一律呼叫 services_b（本檔不寫 SQL，僅有兩處
輕量 ORM 查詢做「模板欄位形狀轉接」）。current_user 沿用兩棧慣例寫死 admin（Phase 3 LDAP 後換）。
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from database_b import get_b_db
from models_b import Isolation, IsolationItem, Item, Plant, Spec
from schemas.control_schema import ControlCreate, ControlModify, ControlTimeUpdate
from schemas.flow_schema import SignAction
from services.control_service import RIGHTSID_CONTROL_TIME  # A/B 兩棧共用常數（roleid=12）
from services_b import acl_service, control_service, flow_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _user() -> tuple[str, str]:
    """目前操作者（MOCK_USER_EMPNO 設定，request 時讀取以支援測試中切換身分；Phase 3 LDAP 後改真身分）。"""
    from config import settings
    return settings.MOCK_USER_EMPNO, settings.MOCK_USER_NAME


# ── 模板形狀轉接 ─────────────────────────────────────────────────────────────

def _iso_dict_for_template(row: dict) -> dict:
    """services_b.get_active_isolations 的 B 形狀（id/plant_no…）→ 模板期待的 A 形狀（ccid/plantno…）。"""
    return {
        "ccid": row["id"], "ccno": row["ccno"],
        "plantno": row["plant_no"], "plantid": row["plant_id"],
        "stime": row["stime"], "etime": row["etime"],
        "mdfdesc": row["mdfdesc"], "remark": row["remark"], "empstr": row["empstr"],
    }


def _todo_dict(db: Session, iso: Isolation) -> dict:
    """flow_service.get_todo_list 的 Isolation ORM → flow_modal.html 期待的欄位。"""
    plant_no = db.execute(
        select(Plant.plant_no).where(Plant.plant_id == iso.plant_id)
    ).scalar_one_or_none() or str(iso.plant_id)
    return {
        "ccid": iso.id, "ccno": iso.ccno, "plantno": plant_no,
        "ttype": iso.ttype, "mdfdesc": iso.mdfdesc,
        "empstr": f"{iso.cemp_no}-{iso.cemp_name or ''}",
        "ctime": iso.created_at, "flowid": iso.flow_id, "fstatus": iso.fstatus,
    }


# ── 隔離頁面 ────────────────────────────────────────────────────────────────

@router.get("/ui/control")
def render_control_modal_b(request: Request, db: Session = Depends(get_b_db)):
    """廠區隔離 Modal：有效隔離清單＋申請表單（模板同 A 棧）。"""
    return templates.TemplateResponse(
        request=request, name="partials/control_modal.html",
        context={
            "active_isolations": [_iso_dict_for_template(r) for r in control_service.get_active_isolations(db)],
            "plant_list": acl_service.get_plant_list(db),
        },
    )


@router.get("/ui/control/items")
def render_control_items_b(request: Request, plantno: str = "", db: Session = Depends(get_b_db)):
    """HTMX：廠區選擇後載入可隔離項目 checkbox（spec ⋈ item 取單位，形狀對齊模板 it.item/it.sourceid/it.unit）。"""
    items: List[dict] = []
    if plantno:
        rows = db.execute(
            select(Spec.item, Spec.source_id, Item.unit)
            .join(Item, Item.item == Spec.item)
            .where(Spec.plant_no == plantno)
            .order_by(Spec.seqno)
        ).all()
        items = [{"item": r.item, "sourceid": r.source_id, "unit": r.unit or ""} for r in rows]
    return templates.TemplateResponse(
        request=request, name="partials/control_items.html",
        context={"items": items, "plantno": plantno},
    )


# ── 隔離 API ────────────────────────────────────────────────────────────────

@router.post("/control/create")
def create_control_b(data: ControlCreate, is_commit: bool = True, db: Session = Depends(get_b_db)):
    try:
        empno, name = _user()
        control_service.create_isolation(db, empno, name, data, is_commit)
        return {"status": "success", "message": "申請已成功送出"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧隔離申請失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


@router.post("/control/submit/{ccid}")
def submit_control_b(ccid: int, db: Session = Depends(get_b_db)):
    try:
        empno, name = _user()
        control_service.submit_isolation(db, ccid, empno, name)
        return {"status": "success", "message": "已送出簽核"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧隔離送簽失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


@router.post("/control/modify")
def modify_control_b(data: ControlModify, is_commit: bool = True, db: Session = Depends(get_b_db)):
    try:
        empno, name = _user()
        iso = control_service.modify_isolation(db, empno, name, data, is_commit)
        return {"status": "success", "message": f"修改單 {iso.ccno} 已建立並送簽"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧隔離修改失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


@router.post("/control/time")
def update_control_time_b(data: ControlTimeUpdate, db: Session = Depends(get_b_db)):
    """隔離時間修改（不走簽核的 roleid=12 通道，權限檢查行為與 A 棧一致、受 ACL_ENFORCE 開關控制）。"""
    if not acl_service.check_permission(db, _user()[0], RIGHTSID_CONTROL_TIME, "modify"):
        raise HTTPException(status_code=403, detail="無隔離時間修改權限")
    try:
        control_service.update_isolation_time(db, _user()[0], data)
        return {"status": "success", "message": "隔離廠區項目結束時間修改成功"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧隔離時間修改失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


@router.get("/control/my_apply")
def my_apply_list_b(plantid: int = -1, statusid: int = -1, ccid: int = -1, db: Session = Depends(get_b_db)):
    return control_service.get_my_applies(db, _user()[0], plant_id=plantid, fstatus=statusid, isolation_id=ccid)


@router.get("/control/tags/{ccid}")
def control_tags_b(ccid: int, db: Session = Depends(get_b_db)):
    """修改表單預先勾選用：該隔離單的明細項目（形狀對齊 A 棧 ControlTagResponse）。"""
    rows = db.execute(select(IsolationItem).where(IsolationItem.isolation_id == ccid)).scalars().all()
    return [
        {"oldtagname": f"{r.plant_no}_{r.item}", "plantno": r.plant_no, "item": r.item, "source": str(r.source_id)}
        for r in rows
    ]


# ── 簽核 ────────────────────────────────────────────────────────────────────

@router.get("/ui/flow")
def render_flow_modal_b(request: Request, db: Session = Depends(get_b_db)):
    todos = [_todo_dict(db, iso) for iso in flow_service.get_todo_list(db, _user()[0])]
    return templates.TemplateResponse(
        request=request, name="partials/flow_modal.html", context={"todos": todos},
    )


@router.get("/flow/todos")
def flow_todos_b(db: Session = Depends(get_b_db)):
    return [_todo_dict(db, iso) for iso in flow_service.get_todo_list(db, _user()[0])]


@router.post("/flow/sign")
def sign_apply_b(action: SignAction, db: Session = Depends(get_b_db)):
    """簽核（actionid：1=核准、9=否決，數值兩棧同源 services/flow_service）。"""
    try:
        flow_service.process_sign(
            db, isolation_id=action.ccid, flow_id=action.flowid, action_id=action.actionid,
            current_user_empno=_user()[0], current_user_name=_user()[1],
            comment=getattr(action, "comment", "") or "",
        )
        return {"status": "success", "message": "簽核已送出"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
