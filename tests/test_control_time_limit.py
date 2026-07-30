"""
test_control_time_limit.py — services_b/control_service.py C5「隔離時間修改」可設定上限測試

背景：ControlTime（roleid=12「隔離時間修改」環工部例外通道）不走簽核，且舊系統刻意不套用
一般申請（ControlCreate/ControlModify）的「隔離總時長 1 小時上限」。C5 把這個上限改成可由
system_config['control_time_max_hours'] 設定，預設（不設定/設 0/空字串/亂碼）= 無上限，
維持現行行為不變。

原則：不連真的 DB。用 sqlite in-memory + models_b 的 SystemConfig/Isolation 兩張表
（SQLAlchemy 泛型型別，sqlite 也能建表），驗證 update_isolation_time() 的上限檢查。

「不可縮短」的既有驗證（新 etime 不可小於選取當下的原始 etime）由
schemas.control_schema.ControlTimeUpdate.validate_etime() 這個 pydantic validator 負責，
本檔不重複測（見 CLAUDE.md「不可違反的技術決策」與該 schema 檔頭註解）。
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import itertools

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from models_b import BaseB, Isolation, SystemConfig, Tranlog
from schemas.control_schema import ControlTimeUpdate
from services.flow_service import FlowStatus, Ttype
from services_b.control_service import _get_control_time_max_hours, update_isolation_time

# tranlog.id 用 BigInteger + Identity()（PG/MSSQL 皆懂），sqlite 方言不認得 Identity()，
# 只在測試這裡補一個自增序號（照抄 tests/test_auth_ldap.py 的 sign_emp 作法），
# 正式環境（PG/MSSQL）不受影響，這段只掛在測試檔案本身、不改 models_b.py。
_tranlog_id_seq = itertools.count(1)


@event.listens_for(Tranlog, "before_insert")
def _assign_tranlog_id_for_sqlite(mapper, connection, target):
    if target.id is None:
        target.id = next(_tranlog_id_seq)


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    BaseB.metadata.create_all(
        engine, tables=[SystemConfig.__table__, Isolation.__table__, Tranlog.__table__]
    )
    return Session(engine)


def _seed_isolation(db: Session, stime: datetime, etime: datetime, ccno: str = "20260730001") -> Isolation:
    iso = Isolation(
        id=1,
        ccno=ccno,
        ttype=int(Ttype.新增),
        plant_id=1,
        mdfdesc="測試隔離",
        remark="",
        stime=stime,
        etime=etime,
        cemp_no="E001",
        cemp_name="王小明",
        fstatus=int(FlowStatus.核准),
    )
    db.add(iso)
    db.commit()
    return iso


def _set_config(db: Session, value: str) -> None:
    db.add(SystemConfig(key="control_time_max_hours", value=value))
    db.commit()


NOW = datetime(2026, 7, 30, 8, 0, 0, tzinfo=timezone.utc)


# ── _get_control_time_max_hours() ────────────────────────────────────────────

def test_get_max_hours_returns_none_when_not_configured():
    db = _make_db()
    assert _get_control_time_max_hours(db) is None


@pytest.mark.parametrize("bad_value", ["0", "", "-1", "abc", "0.0"])
def test_get_max_hours_returns_none_for_no_limit_values(bad_value):
    db = _make_db()
    _set_config(db, bad_value)
    assert _get_control_time_max_hours(db) is None


def test_get_max_hours_returns_configured_value():
    db = _make_db()
    _set_config(db, "8")
    assert _get_control_time_max_hours(db) == 8.0


# ── update_isolation_time()：無上限（預設行為不變）───────────────────────────

def test_no_config_allows_long_duration():
    """未設定 control_time_max_hours → 無上限，維持現行行為（可任意延長）。"""
    db = _make_db()
    stime = NOW
    _seed_isolation(db, stime=stime, etime=stime + timedelta(hours=1))

    data = ControlTimeUpdate(
        ccid=1,
        ccno="20260730001",
        orig_etime=stime + timedelta(hours=1),
        etime=stime + timedelta(hours=10),  # 總時長 10 小時，遠超一般 1 小時上限
        remark="",
    )
    assert update_isolation_time(db, "E999", data) is True

    updated = db.execute(select(Isolation).where(Isolation.id == 1)).scalar_one()
    assert updated.etime.replace(tzinfo=None) == (stime + timedelta(hours=10)).replace(tzinfo=None)


@pytest.mark.parametrize("no_limit_value", ["0", "", "亂碼"])
def test_zero_or_blank_or_garbage_config_means_no_limit(no_limit_value):
    db = _make_db()
    stime = NOW
    _seed_isolation(db, stime=stime, etime=stime + timedelta(hours=1))
    _set_config(db, no_limit_value)

    data = ControlTimeUpdate(
        ccid=1,
        ccno="20260730001",
        orig_etime=stime + timedelta(hours=1),
        etime=stime + timedelta(hours=10),
        remark="",
    )
    assert update_isolation_time(db, "E999", data) is True


# ── update_isolation_time()：設定上限後生效 ──────────────────────────────────

def test_within_configured_limit_passes():
    """設定 8 小時上限，總時長 6 小時 → 通過。"""
    db = _make_db()
    stime = NOW
    _seed_isolation(db, stime=stime, etime=stime + timedelta(hours=1))
    _set_config(db, "8")

    data = ControlTimeUpdate(
        ccid=1,
        ccno="20260730001",
        orig_etime=stime + timedelta(hours=1),
        etime=stime + timedelta(hours=6),
        remark="",
    )
    assert update_isolation_time(db, "E999", data) is True


def test_exceeds_configured_limit_raises_with_numbers_in_message():
    """設定 8 小時上限，總時長 10 小時 → raise，訊息含上限與本次時長數字。"""
    db = _make_db()
    stime = NOW
    _seed_isolation(db, stime=stime, etime=stime + timedelta(hours=1))
    _set_config(db, "8")

    data = ControlTimeUpdate(
        ccid=1,
        ccno="20260730001",
        orig_etime=stime + timedelta(hours=1),
        etime=stime + timedelta(hours=10),
        remark="",
    )
    with pytest.raises(ValueError) as exc_info:
        update_isolation_time(db, "E999", data)

    msg = str(exc_info.value)
    assert "8" in msg
    assert "10" in msg

    # 驗證失敗時已 rollback，etime 未被異動
    reloaded = db.execute(select(Isolation).where(Isolation.id == 1)).scalar_one()
    assert reloaded.etime.replace(tzinfo=None) == (stime + timedelta(hours=1)).replace(tzinfo=None)


def test_exactly_at_limit_passes():
    """剛好等於上限（非超過）→ 通過，邊界不誤擋。"""
    db = _make_db()
    stime = NOW
    _seed_isolation(db, stime=stime, etime=stime + timedelta(hours=1))
    _set_config(db, "8")

    data = ControlTimeUpdate(
        ccid=1,
        ccno="20260730001",
        orig_etime=stime + timedelta(hours=1),
        etime=stime + timedelta(hours=8),
        remark="",
    )
    assert update_isolation_time(db, "E999", data) is True


# ── 「不可縮短」驗證仍由 pydantic 層負責，本檔不重複實作 ─────────────────────

def test_pydantic_layer_still_rejects_shortened_etime():
    """驗證 ControlTimeUpdate 建構當下就擋，不需要 service 層重複這條規則。"""
    stime = NOW
    with pytest.raises(Exception):
        ControlTimeUpdate(
            ccid=1,
            ccno="20260730001",
            orig_etime=stime + timedelta(hours=2),
            etime=stime + timedelta(hours=1),  # 比 orig_etime 早 → pydantic 應該擋
            remark="",
        )
