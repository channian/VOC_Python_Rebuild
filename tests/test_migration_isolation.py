import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration.context import MigrationContext, PersonnelBinding, Person
from migration.normalize.isolation import normalize_isolation
from models_b import Isolation, IsolationItem


NOW = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)


def _ctx(**overrides):
    """組一個測試用 MigrationContext：2 位申請人、now 固定。"""
    binding = PersonnelBinding(
        applicants=[
            Person(empno="E001", name="王小明", email="wang@aseglobal.com"),
            Person(empno="E002", name="李小華", email="li@aseglobal.com"),
        ],
        signers=[Person(empno="S001", name="陳環工", email="chen@aseglobal.com")],
    )
    base = dict(personnel=binding, now=NOW)
    base.update(overrides)
    return MigrationContext(**base)


def _closectl_row(**overrides):
    """組一個 A VOC_closectl 原始欄位 dict（預設：未刪除、有效未過期）。"""
    base = dict(
        ccid=1,
        ttypeid=1,
        ccno="20260701001",
        plantid=1,
        mdfdesc="設備保養",
        stime=NOW - timedelta(days=1),
        etime=NOW + timedelta(days=1),
        remark="備註文字",
        cempname="舊系統申請人",
        cempno="OLD001",
        ctime=NOW - timedelta(days=1),
        flowid=99,
        fstatusid=7,
        delclerk=None,
        orgccid=None,
    )
    base["del"] = 0
    base.update(overrides)
    return base


def _closectl_list_row(**overrides):
    base = dict(id=1, ccid=1, plantno="K1", item="pH1", sourceid="1")
    base.update(overrides)
    return base


# ── del / etime 篩選 ─────────────────────────────────────────────────────
def test_deleted_row_skipped():
    row = _closectl_row(ccid=1)
    row["del"] = 1
    out, items = normalize_isolation([row], [], _ctx())
    assert out == []


def test_expired_row_skipped():
    row = _closectl_row(ccid=1, etime=NOW - timedelta(hours=1))
    out, items = normalize_isolation([row], [], _ctx())
    assert out == []


def test_active_row_migrated():
    row = _closectl_row(ccid=1)
    out, items = normalize_isolation([row], [], _ctx())
    assert len(out) == 1
    assert isinstance(out[0], Isolation)


# ── id 保留 + 申請人 round-robin 改綁 ────────────────────────────────────
def test_id_preserved_and_applicant_rebound_round_robin():
    rows = [
        _closectl_row(ccid=10, ccno="20260701001"),
        _closectl_row(ccid=20, ccno="20260701002"),
        _closectl_row(ccid=30, ccno="20260701003"),
    ]
    out, items = normalize_isolation(rows, [], _ctx())
    assert [o.id for o in out] == [10, 20, 30]

    # round-robin：第 1 筆 applicants[0]、第 2 筆 applicants[1]、第 3 筆回到 applicants[0]
    assert out[0].cemp_no == "E001"
    assert out[0].cemp_name == "王小明"
    assert out[1].cemp_no == "E002"
    assert out[1].cemp_name == "李小華"
    assert out[2].cemp_no == "E001"
    assert out[2].cemp_name == "王小明"

    # 不搬 A 端真人
    assert out[0].cemp_no != "OLD001"


def test_round_robin_skips_inactive_rows():
    """略過的列不佔 round-robin 序號——只依「有效隔離」的順序分配。"""
    rows = [
        _closectl_row(ccid=1),  # 有效 → applicants[0]
        {**_closectl_row(ccid=2), "del": 1},  # 略過，不佔序號
        _closectl_row(ccid=3),  # 有效 → applicants[1]
    ]
    out, items = normalize_isolation(rows, [], _ctx())
    assert len(out) == 2
    assert out[0].cemp_no == "E001"
    assert out[1].cemp_no == "E002"


# ── flow_id / org_id 皆 None ─────────────────────────────────────────────
def test_flow_id_and_org_id_are_none():
    row = _closectl_row(ccid=1, flowid=123, orgccid=999)
    out, items = normalize_isolation([row], [], _ctx())
    assert out[0].flow_id is None
    assert out[0].org_id is None


# ── IsolationItem 篩選 + source_id 轉型 ──────────────────────────────────
def test_items_only_kept_for_migrated_ccid():
    rows = [
        _closectl_row(ccid=1),
        {**_closectl_row(ccid=2), "del": 1},  # 未搬入
    ]
    list_rows = [
        _closectl_list_row(ccid=1, plantno="K1", item="pH1", sourceid="1"),
        _closectl_list_row(id=2, ccid=2, plantno="K2", item="COD2", sourceid="2"),
    ]
    out, items = normalize_isolation(rows, list_rows, _ctx())
    assert len(items) == 1
    assert isinstance(items[0], IsolationItem)
    assert items[0].isolation_id == 1
    assert items[0].plant_no == "K1"
    assert items[0].item == "pH1"


def test_source_id_str_to_int():
    row = _closectl_row(ccid=1)
    list_rows = [_closectl_list_row(ccid=1, sourceid="1")]
    out, items = normalize_isolation([row], list_rows, _ctx())
    assert items[0].source_id == 1
    assert isinstance(items[0].source_id, int)


# ── 時間欄位：ISO 字串解析 ────────────────────────────────────────────────
def test_iso_string_time_fields_parsed_tz_aware():
    row = _closectl_row(
        ccid=1,
        stime="2026-07-08T00:00:00",
        etime="2026-07-10T00:00:00",
        ctime="2026-07-08T00:00:00Z",
    )
    out, items = normalize_isolation([row], [], _ctx())
    iso = out[0]
    assert iso.stime.tzinfo is not None
    assert iso.etime.tzinfo is not None
    assert iso.created_at.tzinfo is not None
    assert iso.stime == datetime(2026, 7, 8, 0, 0, 0, tzinfo=timezone.utc)
    assert iso.etime == datetime(2026, 7, 10, 0, 0, 0, tzinfo=timezone.utc)


def test_iso_string_etime_expired_still_skipped():
    """字串型 etime 也要能正確判斷過期並略過（不是因為型別不比對而誤判有效）。"""
    row = _closectl_row(ccid=1, etime="2026-07-08T00:00:00")  # 早於 NOW
    out, items = normalize_isolation([row], [], _ctx())
    assert out == []
