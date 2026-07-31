"""
tests_integration/test_basedata.py — 真 PG 整合測試：基礎資料維護（廠區/項目/Tag 對應）

涵蓋 services_b/basedata_service.py + routers_b/basedata_router_b.py。
main_b.py 尚未掛載 basedata_router_b（主控統一接線範圍，本次任務刻意不改 main_b.py），
因此本檔案自建最小 FastAPI app + include_router，並用 dependency_overrides 把
get_b_db 換成 tests_integration/conftest.py 的 b_db fixture 提供的 session
（比照 database_b.get_b_db 的 yield/close 慣例）。

使用 conftest.py 的 `b_db` fixture（每個測試前先 seed_test_data.seed() 重灌基準資料，
沒有可連線的 PostgreSQL 時整個目錄會被自動 skip）。
種子資料提供：廠區 TEST1（plant_id=990）、項目 pH1/Cu1/VOC1、tag_mapping 六筆
（source_table='kepware_sim'，皆 target_field='value'），spec 三筆皆 FK 到 TEST1。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database_b import get_b_db
from routers_b.basedata_router_b import router as basedata_router
from scripts.seed_test_data import TEST_PLANT_NO, TEST_PLANT_ID


def _make_client(b_db) -> TestClient:
    app = FastAPI()
    app.include_router(basedata_router)
    app.dependency_overrides[get_b_db] = lambda: b_db
    return TestClient(app)


# ══════════════════════════════════════════════════════════════════════════
# 列表端點
# ══════════════════════════════════════════════════════════════════════════

def test_list_endpoints_return_seed_data(b_db):
    client = _make_client(b_db)

    res = client.get("/basedata/plants")
    assert res.status_code == 200
    plant_nos = [r["plant_no"] for r in res.json()["rows"]]
    assert TEST_PLANT_NO in plant_nos

    res = client.get("/basedata/items")
    assert res.status_code == 200
    item_names = [r["item"] for r in res.json()["rows"]]
    assert "pH1" in item_names and "Cu1" in item_names and "VOC1" in item_names

    res = client.get("/basedata/tags")
    assert res.status_code == 200
    tags = res.json()["rows"]
    assert len(tags) >= 6
    assert all(t["source_table"] == "kepware_sim" for t in tags)


def test_ui_page_renders(b_db):
    client = _make_client(b_db)
    res = client.get("/ui/basedata")
    assert res.status_code == 200
    assert "基礎資料維護" in res.text
    assert TEST_PLANT_NO in res.text


# ══════════════════════════════════════════════════════════════════════════
# 廠區 PLANT
# ══════════════════════════════════════════════════════════════════════════

def test_create_plant_success(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/plant/create", json={
        "plant_id": 1345, "plant_no": "NEWPLANT", "kind": "normal", "is_show": True, "sort": 5,
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    rows = client.get("/basedata/plants").json()["rows"]
    assert any(r["plant_no"] == "NEWPLANT" and r["plant_id"] == 1345 for r in rows)


def test_create_plant_duplicate_plant_no_rejected(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/plant/create", json={
        "plant_id": 1346, "plant_no": TEST_PLANT_NO, "kind": "normal", "is_show": True, "sort": 0,
    })
    assert res.status_code == 400
    assert "已存在" in res.json()["detail"]


def test_create_plant_duplicate_plant_id_rejected(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/plant/create", json={
        "plant_id": TEST_PLANT_ID, "plant_no": "ANOTHER", "kind": "normal", "is_show": True, "sort": 0,
    })
    assert res.status_code == 400
    assert "已存在" in res.json()["detail"]


def test_delete_plant_with_dependents_rejected(b_db):
    client = _make_client(b_db)
    # TEST1 有 3 筆 spec + 6 筆 tag_mapping 參照
    res = client.post("/basedata/plant/delete", json={"plant_id": TEST_PLANT_ID})
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "筆" in detail
    assert "無法刪除" in detail


def test_delete_plant_without_dependents_succeeds(b_db):
    client = _make_client(b_db)
    client.post("/basedata/plant/create", json={
        "plant_id": 2222, "plant_no": "TOBEDEL", "kind": "normal", "is_show": True, "sort": 0,
    })
    res = client.post("/basedata/plant/delete", json={"plant_id": 2222})
    assert res.status_code == 200
    rows = client.get("/basedata/plants").json()["rows"]
    assert not any(r["plant_id"] == 2222 for r in rows)


def test_update_plant(b_db):
    client = _make_client(b_db)
    client.post("/basedata/plant/create", json={
        "plant_id": 3333, "plant_no": "UPD1", "kind": "normal", "is_show": True, "sort": 1,
    })
    res = client.post("/basedata/plant/update", json={
        "plant_id": 3333, "plant_no": "UPD1", "kind": "virtual_group", "is_show": False, "sort": 9,
    })
    assert res.status_code == 200
    rows = client.get("/basedata/plants").json()["rows"]
    row = next(r for r in rows if r["plant_id"] == 3333)
    assert row["kind"] == "virtual_group"
    assert row["is_show"] is False
    assert row["sort"] == 9


# ══════════════════════════════════════════════════════════════════════════
# 項目 ITEM
# ══════════════════════════════════════════════════════════════════════════

def test_create_item_success(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/item/create", json={
        "item": "NH3-1", "display_name": "氨氮", "unit": "mg/L", "is_active": True,
    })
    assert res.status_code == 200
    rows = client.get("/basedata/items").json()["rows"]
    assert any(r["item"] == "NH3-1" and r["display_name"] == "氨氮" for r in rows)


def test_create_item_duplicate_rejected(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/item/create", json={"item": "pH1", "is_active": True})
    assert res.status_code == 400
    assert "已存在" in res.json()["detail"]


def test_delete_item_with_dependents_rejected(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/item/delete", json={"item": "pH1"})
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "筆" in detail
    assert "無法刪除" in detail


def test_delete_item_without_dependents_succeeds(b_db):
    client = _make_client(b_db)
    client.post("/basedata/item/create", json={"item": "TOBEDEL_ITEM", "is_active": True})
    res = client.post("/basedata/item/delete", json={"item": "TOBEDEL_ITEM"})
    assert res.status_code == 200
    rows = client.get("/basedata/items").json()["rows"]
    assert not any(r["item"] == "TOBEDEL_ITEM" for r in rows)


def test_update_item(b_db):
    client = _make_client(b_db)
    client.post("/basedata/item/create", json={"item": "UPDIT1", "unit": "mg/L", "is_active": True})
    res = client.post("/basedata/item/update", json={
        "old_item": "UPDIT1", "item": "UPDIT1", "display_name": "更新別名", "unit": "ppm", "is_active": False,
    })
    assert res.status_code == 200
    rows = client.get("/basedata/items").json()["rows"]
    row = next(r for r in rows if r["item"] == "UPDIT1")
    assert row["display_name"] == "更新別名"
    assert row["unit"] == "ppm"
    assert row["is_active"] is False


# ── 規格型態 is_dual_bound（2026-07-31）：新廠上線的常態維護路徑，一定要能改 ──────

def test_item_is_dual_bound_defaults_to_null(b_db):
    """不帶 is_dual_bound 建項目 → NULL（未指定，規格頁退回名稱推測）。"""
    client = _make_client(b_db)
    res = client.post("/basedata/item/create", json={"item": "DUALDEF", "is_active": True})
    assert res.status_code == 200, res.text
    row = next(r for r in client.get("/basedata/items").json()["rows"] if r["item"] == "DUALDEF")
    assert row["is_dual_bound"] is None


def test_item_create_with_is_dual_bound_true(b_db):
    """★ 新增項目時可直接設定雙邊（例如新廠的 K21 溫度）。"""
    client = _make_client(b_db)
    res = client.post("/basedata/item/create", json={
        "item": "溫度BD", "unit": "°C", "is_active": True, "is_dual_bound": True,
    })
    assert res.status_code == 200, res.text
    row = next(r for r in client.get("/basedata/items").json()["rows"] if r["item"] == "溫度BD")
    assert row["is_dual_bound"] is True


def test_item_update_can_switch_is_dual_bound(b_db):
    """既有項目可改規格型態：未指定 → 雙邊 → 單邊 → 回未指定（整份覆寫語意）。"""
    client = _make_client(b_db)
    client.post("/basedata/item/create", json={"item": "DUALUPD", "is_active": True})

    def _set(value):
        res = client.post("/basedata/item/update", json={
            "old_item": "DUALUPD", "item": "DUALUPD", "is_active": True, "is_dual_bound": value,
        })
        assert res.status_code == 200, res.text
        rows = client.get("/basedata/items").json()["rows"]
        return next(r for r in rows if r["item"] == "DUALUPD")["is_dual_bound"]

    assert _set(True) is True
    assert _set(False) is False
    assert _set(None) is None


def test_basedata_page_renders_spec_kind_column(b_db):
    """項目分頁要看得到「規格型態」欄與表單控制項（新廠維護走這條路）。"""
    client = _make_client(b_db)
    html = client.get("/ui/basedata").text
    assert "規格型態" in html
    assert 'id="bdv2-i-dual"' in html


# ══════════════════════════════════════════════════════════════════════════
# Tag 對應 TAG MAPPING
# ══════════════════════════════════════════════════════════════════════════

def test_create_tag_mapping_success(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/tag/create", json={
        "source_table": "kepware_sim", "tagname": "TEST.NEWTAG.PV",
        "plant_no": TEST_PLANT_NO, "item": "pH1", "target_field": "value", "enabled": True,
    })
    assert res.status_code == 200
    rows = client.get("/basedata/tags").json()["rows"]
    assert any(r["tagname"] == "TEST.NEWTAG.PV" for r in rows)


def test_create_tag_mapping_duplicate_source_tagname_rejected(b_db):
    client = _make_client(b_db)
    # 種子資料已有 kepware_sim/TEST.PH1.PV
    res = client.post("/basedata/tag/create", json={
        "source_table": "kepware_sim", "tagname": "TEST.PH1.PV",
        "plant_no": TEST_PLANT_NO, "item": "pH1", "target_field": "value", "enabled": True,
    })
    assert res.status_code == 400
    assert "已存在" in res.json()["detail"]


def test_create_tag_mapping_invalid_plant_rejected(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/tag/create", json={
        "source_table": "kepware_sim", "tagname": "TEST.NOPLANT.PV",
        "plant_no": "NOSUCHPLANT", "item": "pH1", "target_field": "value", "enabled": True,
    })
    assert res.status_code == 400
    assert "不存在" in res.json()["detail"]


def test_create_tag_mapping_invalid_item_rejected(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/tag/create", json={
        "source_table": "kepware_sim", "tagname": "TEST.NOITEM.PV",
        "plant_no": TEST_PLANT_NO, "item": "NOSUCHITEM", "target_field": "value", "enabled": True,
    })
    assert res.status_code == 400
    assert "不存在" in res.json()["detail"]


def test_create_tag_mapping_invalid_target_field_rejected(b_db):
    client = _make_client(b_db)
    res = client.post("/basedata/tag/create", json={
        "source_table": "kepware_sim", "tagname": "TEST.BADFIELD.PV",
        "plant_no": TEST_PLANT_NO, "item": "pH1", "target_field": "not_a_real_field", "enabled": True,
    })
    assert res.status_code == 400


def test_delete_tag_mapping_succeeds(b_db):
    client = _make_client(b_db)
    client.post("/basedata/tag/create", json={
        "source_table": "kepware_sim", "tagname": "TEST.TOBEDEL.PV",
        "plant_no": TEST_PLANT_NO, "item": "Cu1", "target_field": "value", "enabled": True,
    })
    rows = client.get("/basedata/tags").json()["rows"]
    new_id = next(r["id"] for r in rows if r["tagname"] == "TEST.TOBEDEL.PV")
    res = client.post("/basedata/tag/delete", json={"id": new_id})
    assert res.status_code == 200
    rows = client.get("/basedata/tags").json()["rows"]
    assert not any(r["id"] == new_id for r in rows)


def test_update_tag_mapping(b_db):
    client = _make_client(b_db)
    client.post("/basedata/tag/create", json={
        "source_table": "kepware_sim", "tagname": "TEST.UPDTAG.PV",
        "plant_no": TEST_PLANT_NO, "item": "Cu1", "target_field": "value", "enabled": True,
    })
    rows = client.get("/basedata/tags").json()["rows"]
    row_id = next(r["id"] for r in rows if r["tagname"] == "TEST.UPDTAG.PV")

    res = client.post("/basedata/tag/update", json={
        "id": row_id, "source_table": "kepware_sim", "tagname": "TEST.UPDTAG.PV",
        "plant_no": TEST_PLANT_NO, "item": "VOC1", "target_field": "scada_oos_high", "enabled": False,
    })
    assert res.status_code == 200
    rows = client.get("/basedata/tags").json()["rows"]
    row = next(r for r in rows if r["id"] == row_id)
    assert row["item"] == "VOC1"
    assert row["target_field"] == "scada_oos_high"
    assert row["enabled"] is False
