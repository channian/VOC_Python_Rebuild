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
from models_b import Employee, Isolation, IsolationItem, Item, Plant, Spec
from schemas.control_schema import ControlCreate, ControlModify, ControlTimeUpdate
from schemas.flow_schema import SignAction
from services.control_service import RIGHTSID_CONTROL_TIME  # A/B 兩棧共用常數（roleid=12）
from services.flow_service import FlowStatus
from services.maillist_service import notesid_to_email  # 既有純函式，notesid→email 轉換規則兩棧同源
from services.notify_service import send_email_sync
from services_b import acl_service, control_service, flow_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _user() -> tuple[str, str]:
    """目前操作者：session 登入身分（2026-07-31 AD 串接後）；未登入且 AUTH_MOCK=True 時
    回退 MOCK_USER_EMPNO（沙盒/測試相容），詳見 services_b/session_auth.get_current_user。"""
    from services_b.session_auth import get_current_user
    return get_current_user()


def _notify_sign_result(db: Session, isolation: Isolation, new_status: FlowStatus, action_id: int) -> None:
    """簽核結果通知信（2026-07-08 補接：WP3 留的 notify_callback hook 之前一直是 no-op，
    使用者實測簽核成功後才發現一直沒收到通知信，回頭補上）。

    寄給申請人（isolation.cemp_no），走既有 notify_service.send_email_sync（TEST_MODE 保護、
    走 IT mail server），notesid→email 轉換沿用 services/maillist_service.notesid_to_email
    （兩棧同源，不重寫規則）。查無 email 時只記警告、不讓簽核動作因此失敗（通知信是附加效果，
    不該讓核心的簽核狀態變更失敗）。
    """
    try:
        emp = db.get(Employee, isolation.cemp_no)
        if emp is None or not emp.notes_id:
            logger.warning("簽核通知信：申請人 %s 查無 email，略過寄信", isolation.cemp_no)
            return
        result_text = "核准" if new_status == FlowStatus.核准 else "否決"
        subject = f"【隔離申請{result_text}通知】{isolation.ccno} (Security C)"
        body = (
            f"<p>申請單號：{isolation.ccno}</p>"
            f"<p>結果：{result_text}</p>"
            f"<p>說明：{isolation.mdfdesc or ''}</p>"
        )
        send_email_sync(subject, body, [notesid_to_email(emp.notes_id)])
    except Exception:
        logger.exception("簽核通知信寄送失敗（不影響簽核本身已成功送出）")


def _notify_submit_pending(db: Session, isolation: Isolation, signer_empnos: List[str]) -> None:
    """送簽通知信（2026-07-08 補接：對應舊系統 Proc送簽() 建立 flow 後立刻呼叫
    SendMail通知(isFinished=false)——送簽當下就主動通知簽核人「有單待簽」，不是只靠待辦
    清單被動查看。與 _notify_sign_result 是兩個不同時間點的通知信，之前只補了後者，
    使用者實測才發現送簽當下沒收到信）。

    寄給 signer_empnos（get_signers 回傳的該廠區簽核人清單），查無 email 的人略過，
    全部查無 email 時只記警告、不讓送簽動作失敗。
    """
    try:
        if not signer_empnos:
            return
        to_addrs = []
        for empno in signer_empnos:
            emp = db.execute(select(Employee).where(Employee.emp_no == empno)).scalar_one_or_none()
            if emp is not None and emp.notes_id:
                to_addrs.append(notesid_to_email(emp.notes_id))
        if not to_addrs:
            logger.warning("送簽通知信：廠區簽核人（%s）皆查無 email，略過寄信", signer_empnos)
            return
        subject = f"【隔離申請待簽核】{isolation.ccno} (Security C)"
        body = (
            f"<p>以下文件待您簽核，請儘速處理：</p>"
            f"<p>申請單號：{isolation.ccno}</p>"
            f"<p>說明：{isolation.mdfdesc or ''}</p>"
        )
        send_email_sync(subject, body, to_addrs)
    except Exception:
        logger.exception("送簽通知信寄送失敗（不影響送簽本身已成功送出）")


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
        request=request, name="b/partials/control.html",
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
        control_service.create_isolation(
            db, empno, name, data, is_commit,
            notify_callback=lambda isolation, signer_empnos, flow_id: _notify_submit_pending(
                db, isolation, signer_empnos
            ),
        )
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
        control_service.submit_isolation(
            db, ccid, empno, name,
            notify_callback=lambda isolation, signer_empnos, flow_id: _notify_submit_pending(
                db, isolation, signer_empnos
            ),
        )
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
        iso = control_service.modify_isolation(
            db, empno, name, data, is_commit,
            notify_callback=lambda isolation, signer_empnos, flow_id: _notify_submit_pending(
                db, isolation, signer_empnos
            ),
        )
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
        request=request, name="b/partials/flow.html", context={"todos": todos},
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
            notify_callback=lambda isolation, new_status, action_id: _notify_sign_result(
                db, isolation, new_status, action_id
            ),
            current_user_empno=_user()[0], current_user_name=_user()[1],
            comment=getattr(action, "comment", "") or "",
        )
        return {"status": "success", "message": "簽核已送出"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
