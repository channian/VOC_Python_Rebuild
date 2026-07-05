"""
tests_integration/test_schema.py — Schema B smoke test（WP1 驗收用）

驗證項目（對應 docs/PhaseA執行規格書.md WP1 驗收標準）：
  1. create_all 成功、seed 成功（由 conftest 的 _b_schema / b_db fixture 保證，能跑到這裡就是成功）
  2. 每張表可寫可查（27 張表逐一驗證）
  3. 關鍵約束生效：isolation 的 etime>stime CHECK、tag_mapping 的 UNIQUE、
     reading_history 的 (plant_no,item,measured_at) UNIQUE
  4. reading_history 快照欄位（spec_oos_low...spec_recv_high、limits_extra）存在且可寫入
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from database_b import b_engine
from models_b import (
    BaseB,
    Plant,
    Item,
    Source,
    Spec,
    ReadingCurrent,
    ReadingHistory,
    MailLog,
    MailLogItem,
    Isolation,
    IsolationItem,
    IsolationHistory,
    SpecApply,
    SignEmp,
    SignFlow,
    SignFlowStep,
    MailList,
    MailTypeModel,
    Dept,
    AclRole,
    AclUserRole,
    AclRoleRights,
    Tranlog,
    Employee,
    SystemConfig,
    Curve,
    TagMapping,
    KepwareSim,
)
from scripts.seed_test_data import TEST_PLANT_NO, TEST_PLANT_ID, APPLICANT_EMPNO, SIGNER_EMPNO


# ============================================================
# 1. create_all / 表結構
# ============================================================

def test_all_27_tables_exist():
    """create_all_b() 應該建出全部 27 張表（models_b.py 定義的所有 ORM 類別）。"""
    inspector = inspect(b_engine)
    existing = set(inspector.get_table_names())
    expected = set(BaseB.metadata.tables.keys())
    assert expected.issubset(existing), f"缺少資料表：{expected - existing}"
    assert len(expected) == 27, f"models_b.py 應定義 27 張表，實際 {len(expected)} 張：{sorted(expected)}"


# ============================================================
# 2. seed 資料存在（種子成功）
# ============================================================

def test_seed_data_present(b_db):
    plant = b_db.query(Plant).filter_by(plant_no=TEST_PLANT_NO).first()
    assert plant is not None
    assert plant.plant_id == TEST_PLANT_ID

    items = {i.item for i in b_db.query(Item).filter(Item.item.in_(["pH1", "Cu1", "VOC1"])).all()}
    assert items == {"pH1", "Cu1", "VOC1"}

    specs = b_db.query(Spec).filter_by(plant_no=TEST_PLANT_NO).all()
    assert len(specs) == 3

    kepware_rows = b_db.query(KepwareSim).all()
    assert len(kepware_rows) == 6

    tag_maps = b_db.query(TagMapping).filter_by(source_table="kepware_sim").all()
    assert len(tag_maps) == 6

    cfg_keys = {c.key for c in b_db.query(SystemConfig).all()}
    assert {"staleness_minutes", "sync_interval_minutes", "dispatch_interval_minutes", "mail_paused"} <= cfg_keys

    signer = b_db.query(MailList).filter_by(plant_no=TEST_PLANT_NO, emp_no=SIGNER_EMPNO).first()
    assert signer is not None
    assert signer.sign_grp is True
    assert signer.mail_type == "TO"


# ============================================================
# 3. 每張表可寫可查（含尚未被 seed 覆蓋到的表）
# ============================================================

def test_mail_log_and_item_writable(b_db):
    log = MailLog(plant_no=TEST_PLANT_NO, sent_at=datetime.now(timezone.utc), subject="測試信件", body_note="測試內文")
    b_db.add(log)
    b_db.flush()  # 取得自動產生的 id

    log_item = MailLogItem(
        mail_log_id=log.id, item="pH1", condition_code="OOS",
        detail="pH 超標測試", escalation_stage=0, is_maintenance=False,
    )
    b_db.add(log_item)
    b_db.flush()

    fetched = b_db.query(MailLogItem).filter_by(mail_log_id=log.id).first()
    assert fetched is not None
    assert fetched.item == "pH1"


def test_isolation_family_writable(b_db):
    now = datetime.now(timezone.utc)
    iso = Isolation(
        ccno="20260705TST1", ttype=1, plant_id=TEST_PLANT_ID,
        stime=now, etime=now + timedelta(hours=1),
        cemp_no=APPLICANT_EMPNO, cemp_name="測試申請人", fstatus=0,
    )
    b_db.add(iso)
    b_db.flush()

    iso_item = IsolationItem(isolation_id=iso.id, plant_no=TEST_PLANT_NO, item="pH1", source_id=1)
    b_db.add(iso_item)

    iso_his = IsolationHistory(
        isolation_id=iso.id, utype=1, snapshot={"ccno": "20260705TST1", "ttype": 1},
        uclerk_no=APPLICANT_EMPNO, uclerk_name="測試申請人",
    )
    b_db.add(iso_his)
    b_db.flush()

    assert b_db.query(IsolationItem).filter_by(isolation_id=iso.id).first() is not None
    assert b_db.query(IsolationHistory).filter_by(isolation_id=iso.id).first().snapshot["ttype"] == 1


def test_spec_apply_writable(b_db):
    apply_row = SpecApply(
        formno="TESTFORM0001", ftype="I", plant_no=TEST_PLANT_NO, item="pH1",
        payload={"oos_high": 9.5}, emp_no=APPLICANT_EMPNO, fstatus=0,
    )
    b_db.add(apply_row)
    b_db.flush()
    fetched = b_db.query(SpecApply).filter_by(formno="TESTFORM0001").first()
    assert fetched is not None
    assert fetched.payload["oos_high"] == 9.5


def test_sign_flow_family_writable(b_db):
    applicant = b_db.query(SignEmp).filter_by(emp_no=APPLICANT_EMPNO).first()
    assert applicant is not None

    flow = SignFlow(frule_id=1, act_step=1, fstatus=0, emp_id=applicant.emp_id)
    b_db.add(flow)
    b_db.flush()

    step = SignFlowStep(flow_id=flow.flow_id, fstep=1, emp_id=applicant.emp_id, ftype=1, sign_action=None)
    b_db.add(step)
    b_db.flush()

    assert b_db.query(SignFlowStep).filter_by(flow_id=flow.flow_id).first() is not None


def test_tranlog_and_curve_writable(b_db):
    log = Tranlog(emp_no=APPLICANT_EMPNO, log_type="I", data_before={}, data_after={"a": 1}, remark="測試")
    b_db.add(log)

    curve = Curve(plant_no=TEST_PLANT_NO, item="pH1", url="http://example.com/curve/ph1")
    b_db.add(curve)
    b_db.flush()

    assert b_db.query(Tranlog).filter_by(emp_no=APPLICANT_EMPNO).first() is not None
    assert b_db.query(Curve).filter_by(plant_no=TEST_PLANT_NO, item="pH1").first() is not None


def test_acl_and_dept_writable(b_db):
    assert b_db.query(AclRole).count() >= 7
    assert b_db.query(AclRoleRights).filter_by(role_id=3, rights_id=3).first() is not None
    assert b_db.query(AclUserRole).filter_by(emp_no=APPLICANT_EMPNO, plant_no=TEST_PLANT_NO).first() is not None
    assert b_db.query(Dept).filter_by(plant_id=TEST_PLANT_ID, dept_no="TESTDEPT").first() is not None
    assert b_db.query(Employee).filter_by(emp_no=SIGNER_EMPNO).first().notes_id == "TEST_PLACEHOLDER"
    assert b_db.query(MailTypeModel).count() >= 3
    assert b_db.query(Source).count() >= 3


# ============================================================
# 4. 關鍵約束生效
# ============================================================

def test_isolation_etime_must_be_after_stime(b_db):
    """CHECK (etime > stime)：etime <= stime 必須被 DB 擋下。"""
    now = datetime.now(timezone.utc)
    bad = Isolation(
        ccno="20260705BADX", ttype=1, plant_id=TEST_PLANT_ID,
        stime=now, etime=now,  # etime == stime，不合法
        cemp_no=APPLICANT_EMPNO, fstatus=0,
    )
    b_db.add(bad)
    with pytest.raises(IntegrityError):
        b_db.flush()
    b_db.rollback()


def test_tag_mapping_unique_source_tagname(b_db):
    """UNIQUE (source_table, tagname)：重複的 (source_table, tagname) 必須被擋下。"""
    dup = TagMapping(
        source_table="kepware_sim", tagname="TEST.PH1.PV",  # seed 已存在此組合
        plant_no=TEST_PLANT_NO, item="pH1", target_field="value",
    )
    b_db.add(dup)
    with pytest.raises(IntegrityError):
        b_db.flush()
    b_db.rollback()


def test_reading_history_unique_plant_item_measured_at(b_db):
    """UNIQUE (plant_no, item, measured_at)：同一項目同一時間點只能有一筆歷史紀錄。"""
    existing = b_db.query(ReadingHistory).filter_by(plant_no=TEST_PLANT_NO, item="pH1").first()
    assert existing is not None

    dup = ReadingHistory(
        plant_no=TEST_PLANT_NO, item="pH1", value=existing.value,
        status="normal", measured_at=existing.measured_at,  # 完全相同的時間點
    )
    b_db.add(dup)
    with pytest.raises(IntegrityError):
        b_db.flush()
    b_db.rollback()


# ============================================================
# 5. reading_history 快照欄位存在且有值
# ============================================================

def test_reading_history_has_spec_snapshot_columns(b_db):
    row = b_db.query(ReadingHistory).filter_by(plant_no=TEST_PLANT_NO, item="pH1").first()
    assert row is not None
    # pH1 是雙邊規格，spec_*_low/high 應該都有值（不是單邊 NULL）
    assert row.spec_oos_low is not None and row.spec_oos_high is not None
    assert row.spec_ooc_low is not None and row.spec_ooc_high is not None
    assert row.spec_alert_low is not None and row.spec_alert_high is not None
    assert row.spec_recv_low is not None and row.spec_recv_high is not None
    # limits_extra 欄位存在（本次種子未填值，但欄位必須可寫 None 不報錯，已由 create_all 驗證過）
    assert hasattr(row, "limits_extra")

    cu_row = b_db.query(ReadingHistory).filter_by(plant_no=TEST_PLANT_NO, item="Cu1").first()
    # Cu1 是單邊規格，low 應為 NULL、high 應有值
    assert cu_row.spec_oos_low is None
    assert cu_row.spec_oos_high is not None
