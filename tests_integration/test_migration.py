"""
tests_integration/test_migration.py — A→B 搬遷端到端整合測試（真 PG）。

用 tests_integration/fixtures/migration_sample/ 的假 A 資料（形狀＝真匯出 SELECT *），跑
migration.runner.run_migration 全鏈路，驗證：
  1. 各表寫入筆數（含 plant_filter 濾掉 ALL、停用 spec 略過、只搬有效隔離）。
  2. 轉換正確（門檻字串拆 low/high、rvalue 分類、申請人改綁、email→notesid）。
  3. 接上 dashboard：COD2 超標紅燈、被隔離的 pH1 顯示保養中。
  4. 冪等：重跑不爆、筆數不變。

不使用 conftest 的 b_db（那會 seed 測試資料）；本檔自建 empty_db fixture 先清空 schema。
"""

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from database_b import BSessionLocal, create_all_b, drop_all_b
from migration.context import Person, PersonnelBinding
from migration.runner import run_migration
from models_b import (
    Employee, Isolation, IsolationItem, MailList, Plant, ReadingCurrent, SignEmp, Spec, SystemConfig,
)
from services_b.control_service import is_item_isolated
from services_b.dashboard_service import get_dashboard_rows

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "migration_sample")
NOW = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)


def _personnel() -> PersonnelBinding:
    return PersonnelBinding(
        applicants=[Person("A001", "申請甲", "Applicant_One@aseglobal.com")],
        signers=[
            Person("S001", "簽核甲", "Signer_One@aseglobal.com"),
            Person("S002", "簽核乙", "Signer_Two@aseglobal.com"),
        ],
    )


@pytest.fixture()
def empty_db():
    """清空並重建 Schema B（本檔要的是空庫再搬遷，不要 conftest 的 seed）。"""
    drop_all_b()
    create_all_b()
    session = BSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_migration_loads_and_transforms(empty_db):
    db = empty_db
    report = run_migration(db, FIXTURE, _personnel(), plant_filter={"K7"}, now=NOW)

    # ── 筆數 ──
    assert report.counts["source"] == 3
    assert report.counts["plant"] == 1              # ALL(plantid=29) 被 plant_filter 濾掉
    assert report.counts["spec"] == 3               # 停用(status=0)的 OLD9 略過
    assert report.counts["reading_current"] == 3
    assert report.counts["isolation"] == 1          # 只有有效核准的 1001（1002 過期、1003 刪除）
    assert report.counts["isolation_item"] == 1
    assert report.counts["employee"] == 3           # 1 申請 + 2 簽核
    assert report.counts["sign_emp"] == 3
    assert report.counts["mail_list"] == 6          # 2 簽核 × 1 廠 ×（水保養中/空保養中/水質異常）
    assert report.counts["acl_user_role"] == 2
    assert report.counts["system_config"] == 4

    # ── 門檻拆解：pH1 雙邊 '6-9' → low/high ──
    ph = db.execute(select(Spec).where(Spec.plant_no == "K7", Spec.item == "pH1")).scalar_one()
    assert float(ph.oos_low) == 6 and float(ph.oos_high) == 9 and ph.oos_status == "valid"

    # ── 申請人改綁 + id 保留 ──
    iso = db.execute(select(Isolation)).scalar_one()
    assert iso.id == 1001 and iso.cemp_no == "A001" and iso.flow_id is None

    # ── email → notes_id 反推 ──
    assert db.get(Employee, "S001").notes_id == "Signer One"

    # ── 隔離推導 + dashboard 燈號 ──
    assert is_item_isolated(db, "K7", "pH1", NOW) is True
    rows = {r.item: r for r in get_dashboard_rows(
        db, isolation_checker=lambda p, i: is_item_isolated(db, p, i, NOW))}
    assert rows["COD2"].light_status == "R"    # 讀值 120 > OOS 100 → 紅燈
    assert rows["pH1"].broken == 2             # 被隔離 → 保養中


def test_migration_idempotent(empty_db):
    db = empty_db
    people = _personnel()
    run_migration(db, FIXTURE, people, plant_filter={"K7"}, now=NOW)
    run_migration(db, FIXTURE, people, plant_filter={"K7"}, now=NOW)  # 重跑不應爆、不應重複

    assert db.execute(select(func.count()).select_from(Spec)).scalar() == 3
    assert db.execute(select(func.count()).select_from(SignEmp)).scalar() == 3
    assert db.execute(select(func.count()).select_from(Isolation)).scalar() == 1
    assert db.execute(select(func.count()).select_from(MailList)).scalar() == 6
    assert db.execute(select(func.count()).select_from(ReadingCurrent)).scalar() == 3
    assert db.execute(select(func.count()).select_from(Plant)).scalar() == 1
