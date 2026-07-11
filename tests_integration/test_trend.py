"""
tests_integration/test_trend.py — 歷史曲線頁（trend_service / trend_router_b）整合測試

真連 PostgreSQL（b_db fixture，見 tests_integration/conftest.py）。

⚠️ main_b.py 尚未 include trend_router_b（主控統一接線待後續處理），本檔自建一個最小
FastAPI app 掛 trend_router_b 測試，不透過 `from main_b import app`。
"""

from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from routers_b import trend_router_b  # noqa: E402
from scripts.seed_test_data import TEST_PLANT_NO  # noqa: E402


@pytest.fixture()
def client(b_db):
    """自建最小 app（只掛本頁 router），b_db fixture 先確保 schema + seed 就緒。"""
    app = FastAPI()
    app.include_router(trend_router_b.router)
    with TestClient(app) as c:
        yield c


# ── /trend/ui ───────────────────────────────────────────────────────────

def test_trend_ui_200(client):
    r = client.get("/trend/ui")
    assert r.status_code == 200
    assert "歷史曲線" in r.text


def test_trend_ui_with_explicit_plant(client):
    r = client.get(f"/trend/ui?plant={TEST_PLANT_NO}")
    assert r.status_code == 200
    assert TEST_PLANT_NO in r.text


# ── /trend/plants ───────────────────────────────────────────────────────

def test_trend_plants_includes_seed_plant(client):
    r = client.get("/trend/plants")
    assert r.status_code == 200
    plantnos = [p["plantno"] for p in r.json()]
    assert TEST_PLANT_NO in plantnos


# ── /trend/metrics ──────────────────────────────────────────────────────

def test_trend_metrics_returns_seed_three_items(client):
    r = client.get(f"/trend/metrics?plant={TEST_PLANT_NO}")
    assert r.status_code == 200
    body = r.json()
    items = {m["item"] for m in body}
    assert items == {"pH1", "Cu1", "VOC1"}

    units = {m["item"]: m["unit"] for m in body}
    assert units["pH1"] == "pH"
    assert units["Cu1"] == "mg/L"
    assert units["VOC1"] == "ppm"


def test_trend_metrics_unknown_plant_returns_empty(client):
    r = client.get("/trend/metrics?plant=NOSUCHPLANT")
    assert r.status_code == 200
    assert r.json() == []


# ── /trend/series ───────────────────────────────────────────────────────

def test_trend_series_returns_seed_point_and_oos_snapshot(client):
    r = client.get(f"/trend/series?plant={TEST_PLANT_NO}&items=pH1&range=7D")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1

    series = data[0]
    assert series["item"] == "pH1"
    assert series["unit"] == "pH"
    assert len(series["points"]) >= 1
    # seed baseline：pH1 = 7.20
    assert series["points"][-1]["v"] == pytest.approx(7.20)
    assert series["points"][-1]["status"] == "normal"
    # spec_oos_high / spec_ooc_high 快照（seed：oos_high=9.0 / ooc_high=8.5）
    assert series["oos"] == pytest.approx(9.0)
    assert series["ooc"] == pytest.approx(8.5)
    assert series["stats"]["latest"] == pytest.approx(7.20)
    assert series["stats"]["exceed_count"] == 0


def test_trend_series_multi_item(client):
    r = client.get(f"/trend/series?plant={TEST_PLANT_NO}&items=pH1,Cu1,VOC1&range=7D")
    assert r.status_code == 200
    data = r.json()
    assert {s["item"] for s in data} == {"pH1", "Cu1", "VOC1"}
    cu = next(s for s in data if s["item"] == "Cu1")
    assert cu["oos"] == pytest.approx(3.0)
    assert cu["stats"]["latest"] == pytest.approx(1.20)


def test_trend_series_missing_items_400(client):
    r = client.get(f"/trend/series?plant={TEST_PLANT_NO}&items=&range=7D")
    assert r.status_code == 400


def test_trend_series_invalid_range_400(client):
    r = client.get(f"/trend/series?plant={TEST_PLANT_NO}&items=pH1&range=bogus")
    assert r.status_code == 400


def test_trend_series_custom_range(client):
    today = datetime.now(timezone.utc).date()
    frm = (today - timedelta(days=1)).isoformat()
    to = (today + timedelta(days=1)).isoformat()
    r = client.get(
        f"/trend/series?plant={TEST_PLANT_NO}&items=pH1&range=custom&from={frm}&to={to}"
    )
    assert r.status_code == 200
    assert len(r.json()[0]["points"]) >= 1


def test_trend_series_custom_range_missing_dates_400(client):
    r = client.get(f"/trend/series?plant={TEST_PLANT_NO}&items=pH1&range=custom")
    assert r.status_code == 400


def test_trend_series_no_data_for_out_of_range_window(client):
    """時間窗完全落在資料之外：回傳 200，points 為空陣列（非錯誤）。"""
    far_past_from = "2000-01-01"
    far_past_to = "2000-01-02"
    r = client.get(
        f"/trend/series?plant={TEST_PLANT_NO}&items=pH1&range=custom&from={far_past_from}&to={far_past_to}"
    )
    assert r.status_code == 200
    series = r.json()[0]
    assert series["points"] == []
    assert series["stats"]["latest"] is None


# ── /trend/series.csv ───────────────────────────────────────────────────

def test_trend_series_csv_bom_and_header(client):
    r = client.get(f"/trend/series.csv?plant={TEST_PLANT_NO}&items=pH1&range=7D")
    assert r.status_code == 200
    assert r.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM

    text = r.content.decode("utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == "time,plant,metric,value,status"
    assert any(TEST_PLANT_NO in line and "pH1" in line for line in lines[1:])

    assert "attachment" in r.headers.get("content-disposition", "")
