"""
migration/runner.py — 搬遷編排：來源 → normalize → upsert，依 FK 安全順序。

呼叫端（scripts/migrate_a_to_b.py）給一個 B 棧 Session + export 資料夾 + 人員 config。
本檔讀各 A 表 JSON、呼叫對應 normalize 純函式、用 migration.io.upsert 冪等寫入 B。

FK 安全順序（父表先）：
  1. source / item / plant / mail_type / acl_role
  2. dept（依 plant）/ spec（依 plant,item,source）/ curve / reading_current / acl_role_rights
  3. 人員：employee / sign_emp / mail_list / acl_user_role（改綁 config 同事）
  4. isolation（依 plant）/ isolation_item（依 isolation）
系統設定 system_config 種子（staleness/sync/dispatch 間隔、mail_paused）最後補齊。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from migration import io
from migration.context import MigrationContext, PersonnelBinding
from migration.normalize import (
    config_tables,
    isolation as isolation_norm,
    personnel as personnel_norm,
    reading as reading_norm,
    spec as spec_norm,
)
from models_b import SystemConfig

logger = logging.getLogger(__name__)

# 種子系統設定（與 seed_test_data / worker 預設一致；dispatch_interval_minutes 供未來派報 worker）
_SYSTEM_CONFIG_DEFAULTS = {
    "staleness_minutes": "30",
    "sync_interval_minutes": "5",
    "dispatch_interval_minutes": "15",
    "mail_paused": "false",
}


@dataclass
class LoadReport:
    """搬遷結果統計：每張 B 表寫入筆數。"""
    counts: Dict[str, int] = field(default_factory=dict)

    def add(self, table: str, n: int) -> None:
        self.counts[table] = self.counts.get(table, 0) + n

    def total(self) -> int:
        return sum(self.counts.values())


def run_migration(
    db: Session,
    export_dir: str,
    personnel: PersonnelBinding,
    plant_filter: Optional[Set[str]] = None,
    now: Optional[datetime] = None,
) -> LoadReport:
    """執行一次完整搬遷（冪等，可重跑）。回傳每張表寫入筆數。"""
    now = now or datetime.now(timezone.utc)
    ctx = MigrationContext(personnel=personnel, now=now, plant_filter=plant_filter)
    report = LoadReport()

    def _load(table_b: str, objs) -> None:
        report.add(table_b, io.upsert(db, objs))

    # ── 1. 父表 ──
    _load("source", config_tables.normalize_source(io.read_table(export_dir, "VOC_source")))
    _load("item", config_tables.normalize_item(io.read_table(export_dir, "VOC_item")))
    plant_objs = config_tables.normalize_plant(io.read_table(export_dir, "VOC_plant"))
    if plant_filter:
        plant_objs = [p for p in plant_objs if p.plant_no in plant_filter]
    _load("plant", plant_objs)
    _load("mail_type", config_tables.normalize_mail_type(io.read_table(export_dir, "VOC_Mail_Type")))
    _load("acl_role", config_tables.normalize_acl_role(io.read_table(export_dir, "sys_aclrole")))

    # ── 2. 依賴父表 ──
    _load("dept", config_tables.normalize_dept(io.read_table(export_dir, "VOC_dept")))
    _load("spec", spec_norm.normalize_spec(io.read_table(export_dir, "VOC_SPEC")))
    _load("curve", config_tables.normalize_curve(io.read_table(export_dir, "VOC_Curve")))
    _load("reading_current", reading_norm.normalize_reading_current(io.read_table(export_dir, "VOC_SCADA_WEB")))
    _load("acl_role_rights", config_tables.normalize_acl_role_rights(io.read_table(export_dir, "sys_aclrolerights")))

    # ── 3. 人員（改綁 config 同事）──
    plant_nos: List[str] = [p.plant_no for p in plant_objs]
    people = personnel_norm.build_personnel(ctx, plant_nos)
    _load("employee", people["employee"])
    _load("sign_emp", people["sign_emp"])
    _load("mail_list", people["mail_list"])
    _load("acl_user_role", people["acl_user_role"])

    # ── 4. 隔離 ──
    iso_objs, iso_item_objs = isolation_norm.normalize_isolation(
        io.read_table(export_dir, "VOC_closectl"),
        io.read_table(export_dir, "VOC_closectl_list"),
        ctx,
    )
    _load("isolation", iso_objs)
    _load("isolation_item", iso_item_objs)

    # ── 系統設定種子（只在不存在時補；用 merge 冪等）──
    _load("system_config", [SystemConfig(key=k, value=v) for k, v in _SYSTEM_CONFIG_DEFAULTS.items()])

    db.commit()
    return report
