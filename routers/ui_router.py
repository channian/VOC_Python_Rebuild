from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_voc_db
from services.flow_service import get_todo_applies
from services.spec_service import list_specs
from services.control_service import get_active_isolations, get_plant_list
from services.warning_service import get_current_anomalies

router = APIRouter(prefix="/ui", tags=["Frontend UI HTML Responses"])
templates = Jinja2Templates(directory="templates")


@router.get("/flow")
def render_flow_modal(request: Request, db: Session = Depends(get_voc_db)):
    """渲染簽核管理 Modal — 顯示目前待簽核的申請單"""
    todos = get_todo_applies(db, cempno="admin")  # Phase 3 換成 current_user.empno
    return templates.TemplateResponse(
        request=request,
        name="partials/flow_modal.html",
        context={"todos": todos}
    )


@router.get("/control")
def render_control_modal(request: Request, db: Session = Depends(get_voc_db)):
    """渲染廠區隔離 Modal — 目前有效隔離清單 + 申請表單"""
    return templates.TemplateResponse(
        request=request,
        name="partials/control_modal.html",
        context={
            "active_isolations": get_active_isolations(db),
            "plant_list":        get_plant_list(db),
        }
    )


@router.get("/spec")
def render_spec_modal(request: Request, db: Session = Depends(get_voc_db)):
    """渲染規格維護 Modal"""
    return templates.TemplateResponse(
        request=request,
        name="partials/spec_modal.html",
        context={"specs": list_specs(db)}
    )


@router.get("/warning")
def render_warning_modal(request: Request, db: Session = Depends(get_voc_db)):
    """渲染預警紀錄 Modal — 目前紅/橙燈項目"""
    return templates.TemplateResponse(
        request=request,
        name="partials/warning_modal.html",
        context={"anomalies": get_current_anomalies(db)}
    )


@router.get("/acl")
def render_acl_modal(request: Request, db: Session = Depends(get_voc_db)):
    """渲染系統管理 Modal — Phase 3 完成 LDAP 後才有完整功能"""
    return templates.TemplateResponse(
        request=request,
        name="partials/acl_modal.html",
        context={}
    )
