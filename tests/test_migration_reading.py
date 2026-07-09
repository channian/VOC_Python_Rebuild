import sys
import os
from datetime import datetime, timezone
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration.normalize.reading import normalize_reading_current
from models_b import ReadingCurrent


def _row(**overrides):
    """組一個 A VOC_SCADA_WEB 原始欄位 dict（預設正常讀值、SCADA/CWMS 六+二欄門檻皆有效）。"""
    base = dict(
        plantno="K1",
        item="COD",
        rvalue="1.23",
        cdatetime="2026-07-09T10:15:00",
        OOS_HH="1.16",
        OOC_H="1.0",
        alert="0.8",
        OOS_LL=None,
        OOC_L=None,
        alert_L=None,
        OOS_HH1="1.5",
        OOC_H1="1.2",
        broken=0,
        TwentyFourHours=None,
    )
    base.update(overrides)
    return base


# ── 正常數字 ─────────────────────────────────────────────────────────────
def test_normal_number():
    out = normalize_reading_current([_row(rvalue="1.23")])
    assert len(out) == 1
    r = out[0]
    assert isinstance(r, ReadingCurrent)
    assert r.value == Decimal("1.23")
    assert r.status == "normal"
    assert r.raw_text == "1.23"
    assert r.comm_ok is True


# ── N.D ──────────────────────────────────────────────────────────────────
def test_nd():
    out = normalize_reading_current([_row(rvalue="N.D")])
    r = out[0]
    assert r.value is None
    assert r.status == "nd"
    assert r.raw_text == "N.D"
    assert r.comm_ok is True


# ── 定量下限 <0.05 ───────────────────────────────────────────────────────
def test_below_lod():
    out = normalize_reading_current([_row(rvalue="<0.05")])
    r = out[0]
    assert r.value == Decimal("0.05")
    assert r.status == "below_lod"
    assert r.raw_text == "<0.05"


# ── broken == 1 斷訊 ─────────────────────────────────────────────────────
def test_broken_1():
    out = normalize_reading_current([_row(rvalue="1.0", broken=1)])
    r = out[0]
    assert r.value is None
    assert r.status == "broken"
    assert r.comm_ok is False


# ── broken == 2 保養中/隔離中 ─────────────────────────────────────────────
def test_broken_2_maintenance():
    out = normalize_reading_current([_row(rvalue="保養中", broken=2)])
    r = out[0]
    assert r.value is None
    assert r.status == "maintenance"
    # comm_ok 只對應通訊斷訊（broken==1），隔離不是通訊問題，仍視為 True。
    assert r.comm_ok is True


# ── rvalue 本身混存「建置中」文字（broken==0）──────────────────────────────
def test_building_in_rvalue_text():
    out = normalize_reading_current([_row(rvalue="建置中", broken=0)])
    r = out[0]
    assert r.value is None
    assert r.status == "building"
    assert r.comm_ok is True


# ── 空字串 rvalue ────────────────────────────────────────────────────────
def test_empty_rvalue():
    out = normalize_reading_current([_row(rvalue="")])
    r = out[0]
    assert r.value is None
    assert r.status == "error"


# ── SCADA OOS_HH/OOS_LL 分別進 high/low ───────────────────────────────────
def test_scada_oos_high_low():
    out = normalize_reading_current([_row(OOS_HH="1.16", OOS_LL="0.1")])
    r = out[0]
    assert r.scada_oos_high == Decimal("1.16")
    assert r.scada_oos_low == Decimal("0.1")
    assert r.scada_limit_status == "valid"


# ── SCADA 六欄全無效 → na ───────────────────────────────────────────────
def test_scada_limit_status_na():
    out = normalize_reading_current([_row(
        OOS_HH=None, OOC_H=None, alert=None, OOS_LL=None, OOC_L=None, alert_L=None,
    )])
    r = out[0]
    assert r.scada_limit_status == "na"
    assert r.scada_oos_high is None
    assert r.scada_oos_low is None


# ── CWMS 只有 high，low 固定 None ─────────────────────────────────────────
def test_cwms_high_only():
    out = normalize_reading_current([_row(OOS_HH1="1.5", OOC_H1="1.2")])
    r = out[0]
    assert r.cwms_oos_high == Decimal("1.5")
    assert r.cwms_ooc_high == Decimal("1.2")
    assert r.cwms_oos_low is None
    assert r.cwms_ooc_low is None
    assert r.cwms_limit_status == "valid"


def test_cwms_limit_status_na():
    out = normalize_reading_current([_row(OOS_HH1=None, OOC_H1=None)])
    r = out[0]
    assert r.cwms_limit_status == "na"


# ── rain_24h 對映 ────────────────────────────────────────────────────────
def test_rain_24h_mapping():
    out = normalize_reading_current([_row(TwentyFourHours=12.5)])
    r = out[0]
    assert r.rain_24h == Decimal("12.5")

    out2 = normalize_reading_current([_row(TwentyFourHours=None)])
    assert out2[0].rain_24h is None


# ── measured_at 由字串正確解析為 tz-aware ─────────────────────────────────
def test_measured_at_parsed_from_string():
    out = normalize_reading_current([_row(cdatetime="2026-07-09T10:15:00")])
    r = out[0]
    assert r.measured_at.tzinfo is not None
    assert r.measured_at == datetime(2026, 7, 9, 10, 15, 0, tzinfo=timezone.utc)


def test_measured_at_from_naive_datetime_object():
    out = normalize_reading_current([_row(cdatetime=datetime(2026, 7, 9, 10, 15, 0))])
    r = out[0]
    assert r.measured_at == datetime(2026, 7, 9, 10, 15, 0, tzinfo=timezone.utc)


def test_measured_at_none_falls_back_to_now():
    out = normalize_reading_current([_row(cdatetime=None)])
    r = out[0]
    assert r.measured_at.tzinfo is not None


# ── plant_no/item 對映 ───────────────────────────────────────────────────
def test_plant_and_item_mapping():
    out = normalize_reading_current([_row(plantno="K3", item="pH")])
    r = out[0]
    assert r.plant_no == "K3"
    assert r.item == "pH"
