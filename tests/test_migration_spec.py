import sys
import os
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration.normalize.spec import normalize_spec
from models_b import Spec


def _row(**overrides):
    """組一個 A VOC_SPEC 原始欄位 dict（預設全部啟用、四組門檻皆為單邊有效值）。"""
    base = dict(
        plantno="K1", item="COD", LAW="法規文字", OOS="1.16", OOC="1.16",
        alert="1.16", recv="1.16", source=1, status=1, tagname="TAG.K1.COD", seqno=1,
    )
    base.update(overrides)
    return base


# ── 單邊規格 ─────────────────────────────────────────────────────────────
def test_single_side_oos():
    out = normalize_spec([_row(OOS="1.16")])
    assert len(out) == 1
    spec = out[0]
    assert isinstance(spec, Spec)
    assert spec.oos_low == Decimal("1.16")
    assert spec.oos_high == Decimal("1.16")
    assert spec.oos_status == "valid"


# ── 雙邊規格（pH）─────────────────────────────────────────────────────────
def test_two_side_ph():
    out = normalize_spec([_row(item="pH", OOS="6-9")])
    spec = out[0]
    assert spec.oos_low == Decimal("6")
    assert spec.oos_high == Decimal("9")
    assert spec.oos_status == "valid"


# ── 建置中 ───────────────────────────────────────────────────────────────
def test_building():
    out = normalize_spec([_row(OOS="建置中")])
    spec = out[0]
    assert spec.oos_status == "building"
    assert spec.oos_low is None
    assert spec.oos_high is None


# ── 無效值（'-'／'N/A'／空字串）────────────────────────────────────────────
def test_invalid_values():
    for raw in ("-", "N/A", ""):
        out = normalize_spec([_row(OOS=raw)])
        spec = out[0]
        assert spec.oos_status == "na", f"raw={raw!r}"
        assert spec.oos_low is None
        assert spec.oos_high is None


# ── status==0（停用）被略過 ─────────────────────────────────────────────
def test_disabled_rows_skipped():
    out = normalize_spec([_row(status=0), _row(status=1, item="pH")])
    assert len(out) == 1
    assert out[0].item == "pH"

    # status 非 1 的其他情況（None/其他數字）一併略過
    out2 = normalize_spec([_row(status=None), _row(status=2)])
    assert out2 == []


# ── 一列四組門檻同時拆解、其餘欄位對映 ───────────────────────────────────
def test_full_row_all_four_thresholds():
    out = normalize_spec([_row(
        plantno="K3", item="pH", LAW="放流水標準", source=2, tagname="TAG.K3.PH", seqno=5,
        OOS="6-9", OOC="6.5-8.5", alert="7-8", recv="-",
    )])
    assert len(out) == 1
    spec = out[0]

    assert spec.plant_no == "K3"
    assert spec.item == "pH"
    assert spec.law_text == "放流水標準"
    assert spec.source_id == 2
    assert spec.tagname == "TAG.K3.PH"
    assert spec.seqno == 5

    assert (spec.oos_low, spec.oos_high, spec.oos_status) == (Decimal("6"), Decimal("9"), "valid")
    assert (spec.ooc_low, spec.ooc_high, spec.ooc_status) == (Decimal("6.5"), Decimal("8.5"), "valid")
    assert (spec.alert_low, spec.alert_high, spec.alert_status) == (Decimal("7"), Decimal("8"), "valid")
    assert (spec.recv_low, spec.recv_high, spec.recv_status) == (None, None, "na")


# ── seqno 缺省時補 0 ─────────────────────────────────────────────────────
def test_seqno_defaults_to_zero():
    out = normalize_spec([_row(seqno=None)])
    assert out[0].seqno == 0
