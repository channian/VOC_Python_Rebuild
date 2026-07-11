"""
routers_b/spec_router_b.py — B 棧「規格維護/規格簽核＋QA＋異常回覆＋中水通知頁」router 薄層（WP6 補完）

原則同 control_router_b.py：URL 對齊 A 棧、模板零修改、業務走 services_b。
關鍵轉接：A 棧前端送的是字串門檻（'6-9'／'80'），B 棧 spec 表存 numeric low/high＋status——
由本檔的 _bound_fields() 用既有純函式 parse_spec_bound() 轉換，兩棧驗證規則同源。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from database_b import get_b_db
from models_b import Item, SpecApply
from schemas.qa_schema import QAUpdate
from schemas.spec_schema import (
    SpecApplyCreate, SpecCreate, SpecSignAction, SpecUpdate, parse_spec_bound,
)
from services.flow_service import FlowStatus  # 兩棧同源狀態值
from services.spec_service import to_storage_item  # pH1/COD2 別名對應（既有純函式）
from services_b import history_service, qa_service, spec_service, warning_service
from services_b.dashboard_service import _bounds_to_str  # numeric→A 字串形狀（B 棧內共用轉接）

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def _user_no() -> str:
    """目前操作者工號（MOCK_USER_EMPNO，request 時讀取；Phase 3 LDAP 後改真身分）。"""
    from config import settings
    return settings.MOCK_USER_EMPNO


# ── 門檻字串 ⇄ numeric 欄位轉接 ─────────────────────────────────────────────

_INVALID_STATUS = {"": "na", "-": "na", "N/A": "na", "建置中": "building"}


def _bound_fields(prefix: str, raw: str, is_ph: bool, item_name: str) -> dict:
    """A 形狀字串（'6-9'/'80'/'-'/'N/A'/'建置中'）→ B 的 {prefix}_low/_high/_status 三欄。"""
    raw = (raw or "").strip()
    if raw in _INVALID_STATUS:
        return {f"{prefix}_low": None, f"{prefix}_high": None, f"{prefix}_status": _INVALID_STATUS[raw]}
    parsed = parse_spec_bound(raw, prefix.upper(), is_ph, item_name)  # 驗證規則與 A 棧同源
    if parsed is None:
        return {f"{prefix}_low": None, f"{prefix}_high": None, f"{prefix}_status": "na"}
    low, high = (parsed[0], parsed[1]) if len(parsed) == 2 else (None, parsed[0])
    return {f"{prefix}_low": low, f"{prefix}_high": high, f"{prefix}_status": "valid"}


def _fields_from_schema(data) -> tuple[str, dict]:
    """SpecBase（A 形狀）→ (B 儲存用 item 名, B numeric 欄位 dict)。"""
    storage_item = to_storage_item(data.plantno, data.item)
    is_ph = "pH" in data.item
    fields: dict = {"law_text": data.LAW or "", "source_id": data.source_id}
    for prefix, raw in (("oos", data.OOS), ("ooc", data.OOC), ("alert", data.alert)):
        fields.update(_bound_fields(prefix, raw, is_ph, data.item))
    return storage_item, fields


def _spec_row_for_template(r: dict) -> dict:
    """services_b.list_specs 的 B 形狀 → 模板/A API 期待的形狀（LAW/OOS/OOC/alert 字串）。"""
    return {
        "plantno": r["plant_no"], "item": r.get("display_name") or r["item"],
        "LAW": r.get("law_text") or "",
        "OOS": _bounds_to_str(r["oos_low"], r["oos_high"], r["oos_status"]),
        "OOC": _bounds_to_str(r["ooc_low"], r["ooc_high"], r["ooc_status"]),
        "alert": _bounds_to_str(r["alert_low"], r["alert_high"], r["alert_status"]),
        "source": r.get("source_name") or "", "sourceid": r["source_id"], "seqno": r.get("seqno", 0),
    }


_FTYPE_LABEL = {"I": "新增", "M": "修改", "D": "刪除"}


def _apply_row(sa: SpecApply) -> dict:
    """spec_apply → 前端列形狀。2026-07-11 V2 收線補齊 ftype_label/empstr/cdatetime 與
    LAW/OOS/OOC/alert（payload 的 B numeric 欄位轉回 A 字串形狀）——b/spec.html 待簽核卡
    的異動明細靠這些欄位，先前缺漏只會顯示佔位符。"""
    p = sa.payload or {}

    def _b(prefix: str) -> str:
        return _bounds_to_str(p.get(f"{prefix}_low"), p.get(f"{prefix}_high"), p.get(f"{prefix}_status"))

    return {
        "formid": sa.id, "formno": sa.formno, "ftype": sa.ftype,
        "ftype_label": _FTYPE_LABEL.get(sa.ftype, sa.ftype),
        "plantno": sa.plant_no, "item": sa.item, "fstatus": sa.fstatus,
        "empno": sa.emp_no, "empstr": sa.emp_no, "ctime": sa.created_at, "cdatetime": sa.created_at,
        "LAW": p.get("law_text") or "", "OOS": _b("oos"), "OOC": _b("ooc"), "alert": _b("alert"),
    }


# ── 規格維護 ────────────────────────────────────────────────────────────────

@router.get("/ui/spec")
def render_spec_modal_b(request: Request, db: Session = Depends(get_b_db)):
    """規格維護（V2 起為獨立頁 b/spec.html，取代舊 partial 彈窗；context 契約不變）。"""
    specs = [_spec_row_for_template(r) for r in spec_service.list_specs(db)]
    return templates.TemplateResponse(
        request=request, name="b/spec.html",
        context={"specs": specs, "sources": spec_service.get_sources(db)},
    )


@router.get("/spec/list")
def spec_list_b(plantno: str = "", item: str = "", db: Session = Depends(get_b_db)):
    return [_spec_row_for_template(r) for r in spec_service.list_specs(db, plantno, item)]


@router.post("/spec/create")
def spec_create_b(data: SpecCreate, db: Session = Depends(get_b_db)):
    try:
        storage_item, fields = _fields_from_schema(data)
        spec_service.create_spec(db, _user_no(), data.plantno, storage_item, remark=data.remark or "", **fields)
        return {"status": "success", "message": f"{data.plantno}/{data.item} 規格已新增"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧規格新增失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


@router.post("/spec/update")
def spec_update_b(data: SpecUpdate, db: Session = Depends(get_b_db)):
    try:
        storage_item, fields = _fields_from_schema(data)
        spec_service.update_spec(db, _user_no(), data.plantno, storage_item, remark=data.remark or "", **fields)
        return {"status": "success", "message": f"{data.plantno}/{data.item} 規格已更新"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧規格更新失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


@router.delete("/spec/delete")
def spec_delete_b(plantno: str, item: str, remark: str = "", db: Session = Depends(get_b_db)):
    try:
        spec_service.delete_spec(db, _user_no(), plantno, to_storage_item(plantno, item), remark)
        return {"status": "success", "message": f"{plantno}/{item} 規格已刪除"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧規格刪除失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


# ── 規格簽核 ────────────────────────────────────────────────────────────────

@router.post("/spec/apply")
def spec_apply_b(data: SpecApplyCreate, db: Session = Depends(get_b_db)):
    try:
        storage_item, fields = _fields_from_schema(data)
        sa = spec_service.create_spec_apply(
            db, _user_no(), data.plantno, storage_item, data.ftype, payload=fields, remark=data.remark or "",
        )
        return {"status": "success", "message": "規格申請已送出", "formid": sa.id}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧規格送簽失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


@router.get("/spec/applies")
def spec_applies_b(plantno: str = "", item: str = "", db: Session = Depends(get_b_db)):
    return [_apply_row(sa) for sa in spec_service.list_spec_applies(db, plantno, item)]


@router.get("/spec/todos")
def spec_todos_b(db: Session = Depends(get_b_db)):
    """待簽核清單：待簽核(0)＋簽核中(1)。"""
    rows = spec_service.list_spec_applies(db, fstatus=int(FlowStatus.待簽核))
    rows += spec_service.list_spec_applies(db, fstatus=int(FlowStatus.簽核中))
    return [_apply_row(sa) for sa in rows]


@router.post("/spec/sign")
def spec_sign_b(action: SpecSignAction, db: Session = Depends(get_b_db)):
    """規格簽核：核准(1)→套用回 spec；否決(9)→僅改狀態。交易由本層 commit（呼應 apply_spec_from_form 註解）。"""
    sa = db.get(SpecApply, action.formid)
    if sa is None:
        raise HTTPException(status_code=404, detail="查無此規格申請單")
    try:
        if action.actionid == 1:
            spec_service.apply_spec_from_form(db, action.formid, _user_no())
            sa.fstatus = int(FlowStatus.核准)
        else:
            sa.fstatus = int(FlowStatus.否決)
        db.commit()
        return {"status": "success", "message": "簽核已送出"}
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        db.rollback()
        logger.exception("B 棧規格簽核失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


# ── QA 手測值 ──────────────────────────────────────────────────────────────

def _qa_row_for_template(db: Session, r: dict, units: dict) -> dict:
    rvalue = r.get("raw_text") or ("" if r.get("value") is None else str(r["value"]))
    return {
        "plantno": r["plant_no"], "item": r["item"], "unit": units.get(r["item"], ""),
        "rvalue": rvalue, "cdatetime": r.get("measured_at"),
        "OOS": "" if r.get("oos_high") is None else str(r["oos_high"]),
        "OOC": "" if r.get("ooc_high") is None else str(r["ooc_high"]),
        "alert": "" if r.get("alert_high") is None else str(r["alert_high"]),
    }


@router.get("/ui/qa")
def render_qa_modal_b(request: Request, db: Session = Depends(get_b_db)):
    units = {i.item: (i.unit or "") for i in db.execute(select(Item)).scalars().all()}
    qa_items = [_qa_row_for_template(db, r, units) for r in qa_service.list_qa_items(db)]
    return templates.TemplateResponse(
        request=request, name="b/partials/qa.html", context={"qa_items": qa_items},
    )


@router.post("/qa/update")
def qa_update_b(data: QAUpdate, db: Session = Depends(get_b_db)):
    try:
        qa_service.update_qa_value(db, _user_no(), data.plantno, data.item, data.rvalue, data.remark or "")
        return {"status": "success", "message": f"{data.plantno}/{data.item} 手測值已更新"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception:
        logger.exception("B 棧 QA 手測值更新失敗")
        raise HTTPException(status_code=500, detail="伺服器或資料庫錯誤")


# ── 異常原因回覆頁（查詢邏輯與 /ui/history 相同、模板不同）────────────────────

@router.get("/ui/reason")
def render_reason_modal_b(request: Request, plant: str = "", item: str = "", sdate: str = "",
                          edate: str = "", mt: bool = False, db: Session = Depends(get_b_db)):
    if not sdate or not edate:
        sdate, edate = history_service.default_date_range()
    logs, error = [], ""
    try:
        history_service.validate_date_range(sdate, edate)
        logs = history_service.list_voclog(db, plant, item, sdate, edate, mt)
    except ValueError as e:
        error = str(e)
    except Exception as e:
        error = f"查詢失敗：{e}"
    return templates.TemplateResponse(
        request=request, name="b/partials/history.html",
        context={
            "mode": "reason",  # 合併版模板：reason=可行內回覆
            "plants": history_service.list_plants(db), "items": history_service.list_items(db, plant),
            "plant": plant, "item": item, "sdate": sdate, "edate": edate, "mt": mt,
            "logs": logs, "error": error,
        },
    )


# ── 中水緊急通知頁 ──────────────────────────────────────────────────────────

@router.get("/warning/water_urgent/ui")
def render_water_urgent_modal_b(request: Request, db: Session = Depends(get_b_db)):
    try:
        plants = warning_service.get_water_plants(db, exclude_k14b=True)
        reasons = warning_service.list_change_reasons(db)
        error = ""
    except Exception:
        logger.exception("B 棧中水通知頁查詢失敗")
        plants, reasons, error = [], [], "查詢失敗，資料庫連線異常"
    return templates.TemplateResponse(
        request=request, name="b/partials/water_urgent.html",
        context={"plants": plants, "reasons": reasons, "error": error},
    )
