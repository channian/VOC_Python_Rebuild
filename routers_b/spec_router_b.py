"""
routers_b/spec_router_b.py — B 棧「規格維護/規格簽核＋QA＋異常回覆＋中水通知頁」router 薄層（WP6 補完）

原則同 control_router_b.py：URL 對齊 A 棧、模板零修改、業務走 services_b。
關鍵轉接：A 棧前端送的是字串門檻（'6-9'／'80'），B 棧 spec 表存 numeric low/high＋status——
由本檔的 _bound_fields() 用既有純函式 parse_spec_bound() 轉換，兩棧驗證規則同源。

★ 2026-07-31「雙邊規格判定改資料驅動」（見 models_b.Item.is_dual_bound）：
  問題：`SpecCreate`/`SpecUpdate`/`SpecApplyCreate` 是 Pydantic model，**FastAPI 在解析 body
  的當下就跑完 model_validator**，也就是「名稱不像 pH 的雙邊項目（如 K21 溫度填 20-35）」
  會在 request 還沒進到 router 函式之前就被打成 422，根本來不及查 DB 問 item.is_dual_bound。
  解法：B 棧三個寫入端點改收**寬鬆**輸入模型 `SpecInputB`/`SpecApplyInputB`（同樣欄位、
  但**沒有** model_validator，所以純解析不驗證），進到 router 後先查 `Item.is_dual_bound`，
  再把查到的值當 `is_dual_bound` 注入、建構原本那個嚴格 model 完成驗證（`_validate_b()`）。
  驗證規則因此仍與 A 棧同源（同一個 SpecBase.validate_limits），只是判「單邊/雙邊」的依據
  由「猜名稱」換成「查資料」；item 查無或該欄為 NULL 時自動退回名稱推測，現況不受影響。
  A 棧（routers/spec_router.py）完全不動，仍直接以 SpecCreate 解析 → 一律走名稱推測。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from database_b import get_b_db
from models_b import Item, SpecApply
from schemas.qa_schema import QAUpdate
from schemas.spec_schema import (
    SpecApplyCreate, SpecBase, SpecCreate, SpecSignAction, SpecUpdate, parse_spec_bound,
)
from services.flow_service import FlowStatus  # 兩棧同源狀態值
from services.spec_service import to_storage_item  # pH1/COD2 別名對應（既有純函式）
from services_b import history_service, qa_service, spec_service, warning_service
from services_b.dashboard_service import _bounds_to_str  # numeric→A 字串形狀（B 棧內共用轉接）

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def _user_no() -> str:
    """目前操作者工號：session 登入身分（2026-07-31 AD 串接後；未登入且 AUTH_MOCK=True 回退
    MOCK 身分，見 services_b/session_auth.get_current_user）。"""
    from services_b.session_auth import get_current_user
    return get_current_user()[0]


# ── 門檻字串 ⇄ numeric 欄位轉接 ─────────────────────────────────────────────

_INVALID_STATUS = {"": "na", "-": "na", "N/A": "na", "建置中": "building"}


def _bound_fields(prefix: str, raw: str, is_dual: bool, item_name: str) -> dict:
    """A 形狀字串（'6-9'/'80'/'-'/'N/A'/'建置中'）→ B 的 {prefix}_low/_high/_status 三欄。"""
    raw = (raw or "").strip()
    if raw in _INVALID_STATUS:
        return {f"{prefix}_low": None, f"{prefix}_high": None, f"{prefix}_status": _INVALID_STATUS[raw]}
    parsed = parse_spec_bound(raw, prefix.upper(), is_dual, item_name)  # 驗證規則與 A 棧同源
    if parsed is None:
        return {f"{prefix}_low": None, f"{prefix}_high": None, f"{prefix}_status": "na"}
    low, high = (parsed[0], parsed[1]) if len(parsed) == 2 else (None, parsed[0])
    return {f"{prefix}_low": low, f"{prefix}_high": high, f"{prefix}_status": "valid"}


def _fields_from_schema(data: SpecBase) -> tuple[str, dict]:
    """SpecBase（A 形狀）→ (B 儲存用 item 名, B numeric 欄位 dict)。

    ★ 雙邊判定改用 `data.effective_dual_bound()`（＝router 先查 item.is_dual_bound 注入的值，
      未指定時才退回名稱推測），取代原本這裡自己寫的第三套字串比對 `"pH" in data.item`——
      那套連 schemas 與載入器的兩套都對不齊，溫度更是永遠猜不到。
    """
    storage_item = to_storage_item(data.plantno, data.item)
    is_dual = data.effective_dual_bound()
    fields: dict = {"law_text": data.LAW or "", "source_id": data.source_id}
    for prefix, raw in (("oos", data.OOS), ("ooc", data.OOC), ("alert", data.alert)):
        fields.update(_bound_fields(prefix, raw, is_dual, data.item))
    return storage_item, fields


# ── 寬鬆輸入模型 + 資料驅動的雙邊判定（見檔頭 ★ 說明）──────────────────────────

class SpecInputB(BaseModel):
    """B 棧規格寫入端點的輸入模型：欄位與 `SpecBase` 相同，但**刻意不帶 model_validator**。

    目的是把「門檻格式驗證」延後到 router 內部（查得到 item.is_dual_bound 之後）再做，
    而不是在 FastAPI 解析 body 的當下就用名稱推測驗完（那會讓溫度這種雙邊項目永遠 422）。
    """
    plantno: str
    item: str
    LAW: str
    OOS: str
    OOC: str
    alert: str
    source_id: int
    remark: Optional[str] = ""


class SpecApplyInputB(SpecInputB):
    """送簽版寬鬆輸入模型（多一個 ftype；ftype 合法值由嚴格 model SpecApplyCreate 驗）。"""
    ftype: str


def _resolve_dual_bound(db: Session, storage_item: str) -> Optional[bool]:
    """查 `item.is_dual_bound`（B 棧資料驅動的規格型態）。

    回傳 None 有兩種情況，語意相同——「沒有明確指定」，交回 `SpecBase` 用名稱推測：
      1. item 主檔查無此項目（例如送簽新增一個尚未建立的項目）；
      2. 查到了但該欄位是 NULL（基礎資料還沒填「規格型態」）。
    """
    return db.execute(
        select(Item.is_dual_bound).where(Item.item == storage_item)
    ).scalar_one_or_none()


def _validate_b(model_cls, raw: SpecInputB, db: Session) -> SpecBase:
    """寬鬆輸入 → 查 item.is_dual_bound → 建構嚴格 model 完成驗證。

    驗證失敗時轉成 422，且 detail 形狀比照 FastAPI 自己產生的 RequestValidationError
    （`[{"loc": [...], "msg": ..., "type": ...}]`），前端 `extractErrors()` 不必改就能顯示
    原因（例：「Value error, OOS 值錯誤, 溫度 必須為雙邊規格 (如: 6-9)!」）。
    """
    is_dual = _resolve_dual_bound(db, to_storage_item(raw.plantno, raw.item))
    try:
        return model_cls(**raw.model_dump(), is_dual_bound=is_dual)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=[
            {
                "loc": ["body"] + [str(x) for x in err.get("loc", ())],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in e.errors()
        ])


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
def spec_create_b(raw: SpecInputB, db: Session = Depends(get_b_db)):
    # 驗證刻意放在 try 之外：_validate_b 失敗會丟 HTTPException(422)，
    # 若放進 try 會被下面的 `except Exception` 吃掉、變成語焉不詳的 500。
    data = _validate_b(SpecCreate, raw, db)
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
def spec_update_b(raw: SpecInputB, db: Session = Depends(get_b_db)):
    data = _validate_b(SpecUpdate, raw, db)  # 同 spec_create_b：驗證放 try 之外
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
def spec_apply_b(raw: SpecApplyInputB, db: Session = Depends(get_b_db)):
    data = _validate_b(SpecApplyCreate, raw, db)  # 同 spec_create_b：驗證放 try 之外
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
    """2026-07-31 C8：logs 每一列改帶 item_id（逐項目複合鍵字串，見
    history_service._make_item_id），模板行內回覆改用 item_id 呼叫 /history/reply。"""
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
