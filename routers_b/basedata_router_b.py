"""
routers_b/basedata_router_b.py — 基礎資料維護（廠區 / 項目 / Tag 對應）router 薄層

第 12 個工具頁：讓環工部能自行在網頁上新增/維護廠區、監測項目、Kepware Tag 對應，
不必每次找工程師動資料庫（公司蓋新廠棟時尤其需要）。

照抄 routers_b/ui_router_b.py 的 dept CRUD 端點風格：router 只做「收 request → call
services_b.basedata_service → 組回應」的薄層，ValueError 一律轉 HTTP 400
`{"detail": "..."}`，成功一律 `{"status": "success", "message": "..."}`。

URL 前綴刻意用 /basedata，避免與既有端點衝突（見任務規格）：
  GET  /ui/basedata                 — 渲染 modal（三分頁：廠區/項目/Tag對應）
  GET  /basedata/plants|items|tags  — 三個列表 JSON（modal 內 JS 亦可用來重新整理局部畫面）
  POST /basedata/plant/create|update|delete
  POST /basedata/item/create|update|delete
  POST /basedata/tag/create|update|delete

★ 本檔案「尚未」掛到 main_b.py（主控統一接線範圍，任務要求本次只新增檔案，不改
  main_b.py），因此整合測試（tests_integration/test_basedata.py）自建最小 FastAPI app
  + include_router 驗證，正式掛載留待主控後續統一處理。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database_b import get_b_db
from services_b import basedata_service

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _user_no() -> str:
    """目前操作者工號（比照 routers_b/ui_router_b.py 的作法：session 登入身分，
    AUTH_MOCK=True 未登入時回退 MOCK 身分）。"""
    from services_b.session_auth import get_current_user
    return get_current_user()[0]


# ══════════════════════════════════════════════════════════════════════════
# 請求 body 模型
# ══════════════════════════════════════════════════════════════════════════

class PlantCreateReq(BaseModel):
    plant_id: int
    plant_no: str
    kind: str = "normal"
    is_show: bool = True
    sort: int = 0
    remark: str = ""


class PlantUpdateReq(PlantCreateReq):
    pass


class PlantDeleteReq(BaseModel):
    plant_id: int
    remark: str = ""


class ItemCreateReq(BaseModel):
    item: str
    display_name: str | None = None
    unit: str | None = None
    is_active: bool = True
    remark: str = ""
    # 規格型態（models_b.Item.is_dual_bound）：true=雙邊（pH/溫度，門檻填「低-高」）、
    # false=單邊、null=未指定（退回舊的名稱推測）。B 棧規格維護頁靠這欄決定驗證方式。
    is_dual_bound: bool | None = None


class ItemUpdateReq(ItemCreateReq):
    old_item: str


class ItemDeleteReq(BaseModel):
    item: str
    remark: str = ""


class TagCreateReq(BaseModel):
    source_table: str
    tagname: str
    plant_no: str
    item: str
    target_field: str = "value"
    enabled: bool = True
    remark: str = ""


class TagUpdateReq(TagCreateReq):
    id: int


class TagDeleteReq(BaseModel):
    id: int
    remark: str = ""


# ══════════════════════════════════════════════════════════════════════════
# 頁面：GET /ui/basedata
# ══════════════════════════════════════════════════════════════════════════

@router.get("/ui/basedata")
def render_basedata_modal_b(request: Request, db: Session = Depends(get_b_db)):
    try:
        plants = basedata_service.list_plants(db)
        items = basedata_service.list_items(db)
        tags = basedata_service.list_tag_mappings(db)
        error = ""
    except Exception:
        plants, items, tags, error = [], [], [], "查詢失敗，資料庫連線異常"
    return templates.TemplateResponse(
        request=request, name="b/partials/basedata.html",
        context={
            "plants": plants, "items": items, "tags": tags, "error": error,
            "plant_kind_choices": basedata_service.PLANT_KIND_CHOICES,
            "target_field_choices": basedata_service.TARGET_FIELD_CHOICES,
        },
    )


# ══════════════════════════════════════════════════════════════════════════
# 列表 JSON
# ══════════════════════════════════════════════════════════════════════════

@router.get("/basedata/plants")
def api_list_plants_b(db: Session = Depends(get_b_db)):
    return {"rows": basedata_service.list_plants(db)}


@router.get("/basedata/items")
def api_list_items_b(db: Session = Depends(get_b_db)):
    return {"rows": basedata_service.list_items(db)}


@router.get("/basedata/tags")
def api_list_tags_b(db: Session = Depends(get_b_db)):
    return {"rows": basedata_service.list_tag_mappings(db)}


# ══════════════════════════════════════════════════════════════════════════
# 廠區 PLANT CRUD
# ══════════════════════════════════════════════════════════════════════════

@router.post("/basedata/plant/create")
def api_create_plant_b(data: PlantCreateReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.add_plant(
            db, current_user_empno=_user_no(), plant_id=data.plant_id, plant_no=data.plant_no,
            kind=data.kind, is_show=data.is_show, sort=data.sort, remark=data.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"廠區 {data.plant_no} 已新增"}


@router.post("/basedata/plant/update")
def api_update_plant_b(data: PlantUpdateReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.update_plant(
            db, current_user_empno=_user_no(), plant_id=data.plant_id, plant_no=data.plant_no,
            kind=data.kind, is_show=data.is_show, sort=data.sort, remark=data.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"廠區 {data.plant_no} 已修改"}


@router.post("/basedata/plant/delete")
def api_delete_plant_b(data: PlantDeleteReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.delete_plant(db, current_user_empno=_user_no(), plant_id=data.plant_id,
                                       remark=data.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"廠區(plant_id={data.plant_id}) 已刪除"}


# ══════════════════════════════════════════════════════════════════════════
# 項目 ITEM CRUD
# ══════════════════════════════════════════════════════════════════════════

@router.post("/basedata/item/create")
def api_create_item_b(data: ItemCreateReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.add_item(
            db, current_user_empno=_user_no(), item=data.item, display_name=data.display_name,
            unit=data.unit, is_active=data.is_active, remark=data.remark,
            is_dual_bound=data.is_dual_bound,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"項目 {data.item} 已新增"}


@router.post("/basedata/item/update")
def api_update_item_b(data: ItemUpdateReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.update_item(
            db, current_user_empno=_user_no(), old_item=data.old_item, item=data.item,
            display_name=data.display_name, unit=data.unit, is_active=data.is_active,
            remark=data.remark, is_dual_bound=data.is_dual_bound,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"項目 {data.item} 已修改"}


@router.post("/basedata/item/delete")
def api_delete_item_b(data: ItemDeleteReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.delete_item(db, current_user_empno=_user_no(), item=data.item, remark=data.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"項目 {data.item} 已刪除"}


# ══════════════════════════════════════════════════════════════════════════
# Tag 對應 TAG MAPPING CRUD
# ══════════════════════════════════════════════════════════════════════════

@router.post("/basedata/tag/create")
def api_create_tag_b(data: TagCreateReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.add_tag_mapping(
            db, current_user_empno=_user_no(), source_table=data.source_table, tagname=data.tagname,
            plant_no=data.plant_no, item=data.item, target_field=data.target_field,
            enabled=data.enabled, remark=data.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"Tag 對應 {data.source_table}/{data.tagname} 已新增"}


@router.post("/basedata/tag/update")
def api_update_tag_b(data: TagUpdateReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.update_tag_mapping(
            db, current_user_empno=_user_no(), id=data.id, source_table=data.source_table,
            tagname=data.tagname, plant_no=data.plant_no, item=data.item,
            target_field=data.target_field, enabled=data.enabled, remark=data.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"Tag 對應 {data.source_table}/{data.tagname} 已修改"}


@router.post("/basedata/tag/delete")
def api_delete_tag_b(data: TagDeleteReq, db: Session = Depends(get_b_db)):
    try:
        basedata_service.delete_tag_mapping(db, current_user_empno=_user_no(), id=data.id, remark=data.remark)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", "message": f"Tag 對應(id={data.id}) 已刪除"}
