from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_voc_db
from services.flow_service import get_todo_applies
from services.spec_service import list_specs

router = APIRouter(prefix="/ui", tags=["Frontend UI HTML Responses"])
templates = Jinja2Templates(directory="templates")

@router.get("/flow")
def render_flow_modal(request: Request, db: Session = Depends(get_voc_db)):
    """ 渲染簽核管理 Modal """
    todos = get_todo_applies(db, cempno="admin")
    return templates.TemplateResponse(
        request=request,
        name="partials/flow_modal.html",
        context={"todos": todos}
    )

@router.get("/control")
def render_control_modal(request: Request, db: Session = Depends(get_voc_db)):
    """ 渲染廠區隔離 Modal """
    # 這裡未來可整合 control_service 獲取真正的資料
    return templates.TemplateResponse(
        request=request,
        name="partials/control_modal.html",
        context={}
    )

@router.get("/spec")
def render_spec_modal(request: Request, db: Session = Depends(get_voc_db)):
    """ 渲染規格維護 Modal """
    specs = list_specs(db)
    return templates.TemplateResponse(
        request=request,
        name="partials/spec_modal.html",
        context={"specs": specs}
    )

@router.get("/warning")
def render_warning_modal(request: Request, db: Session = Depends(get_voc_db)):
    """ 渲染預警紀錄 Modal """
    return templates.TemplateResponse(
        request=request,
        name="partials/warning_modal.html",
        context={}
    )

@router.get("/acl")
def render_acl_modal(request: Request, db: Session = Depends(get_voc_db)):
    """ 渲染權限設定 Modal """
    return templates.TemplateResponse(
        request=request,
        name="partials/acl_modal.html",
        context={}
    )
