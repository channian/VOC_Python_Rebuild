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
    # ControlTime（隔離時間修改，roleid=12 環工部例外通道）的隔離總時長上限（小時）。
    # "0" = 無上限（維持現行「不受 1 小時上限限制」的既有行為），語意見
    # services_b/control_service.py._get_control_time_max_hours()。
    "control_time_max_hours": "0",
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

    def _drop_orphans(objs, keyfn, valid: set, label: str):
        """過濾掉「參照的父表資料沒載入」的孤兒列並記警告。

        A 端有些資料塞不進 B（例如 A 兩個 plantid 共用同一個 plantno，B 的 plant_no 唯一只能留一筆，
        另一個 plantid 就沒有對應的 plant 列）；此時參照它的子表（dept.plant_id 等）會撞 FK。
        搬遷應對這種「A 有、B 塞不下」有韌性：略過孤兒列、記警告，而不是整批失敗。
        """
        kept, dropped = [], 0
        for o in objs:
            if keyfn(o) in valid:
                kept.append(o)
            else:
                dropped += 1
        if dropped:
            logger.warning("搬遷 %s：略過 %d 筆孤兒列（參照的父表資料未載入，多半因 A 端 plantno 重複/為空塞不進 B）",
                           label, dropped)
        return kept

    # ── 1. 父表 ──
    source_objs = config_tables.normalize_source(io.read_table(export_dir, "VOC_source"))
    _load("source", source_objs)
    item_objs = config_tables.normalize_item(io.read_table(export_dir, "VOC_item"))
    _load("item", item_objs)
    # plant 是設定主檔，一律全部載入；不可因 plant_filter 砍掉（廠區過濾的真正場合在 export 階段）。
    plant_objs = config_tables.normalize_plant(io.read_table(export_dir, "VOC_plant"))
    _load("plant", plant_objs)
    _load("mail_type", config_tables.normalize_mail_type(io.read_table(export_dir, "VOC_Mail_Type")))
    _load("acl_role", config_tables.normalize_acl_role(io.read_table(export_dir, "sys_aclrole")))

    # 父表已載入的鍵集合，供下方過濾子表孤兒
    plant_ids = {p.plant_id for p in plant_objs}
    plant_nos_loaded = {p.plant_no for p in plant_objs}
    item_names = {i.item for i in item_objs}
    source_ids = {s.source_id for s in source_objs}

    # ── 2. 依賴父表（過濾掉父表沒載入的孤兒列）──
    dept_objs = _drop_orphans(
        config_tables.normalize_dept(io.read_table(export_dir, "VOC_dept")),
        lambda d: d.plant_id, plant_ids, "dept")
    _load("dept", dept_objs)

    spec_objs = spec_norm.normalize_spec(io.read_table(export_dir, "VOC_SPEC"))
    spec_objs = _drop_orphans(spec_objs, lambda s: s.plant_no, plant_nos_loaded, "spec(plant)")
    spec_objs = _drop_orphans(spec_objs, lambda s: s.item, item_names, "spec(item)")
    spec_objs = _drop_orphans(spec_objs, lambda s: s.source_id, source_ids, "spec(source)")
    _load("spec", spec_objs)

    _load("curve", config_tables.normalize_curve(io.read_table(export_dir, "VOC_Curve")))  # 無 FK
    _load("reading_current", reading_norm.normalize_reading_current(io.read_table(export_dir, "VOC_SCADA_WEB")))  # 無 FK
    _load("acl_role_rights", config_tables.normalize_acl_role_rights(io.read_table(export_dir, "sys_aclrolerights")))

    # ── 3. 人員（改綁 config 同事）──
    # 名單/權限掛在哪些廠：有指定 plant_filter 就取其中「已載入的」廠區，否則全部載入的廠區。
    if plant_filter:
        plant_nos: List[str] = [p.plant_no for p in plant_objs if p.plant_no in plant_filter]
        if not plant_nos:
            logger.warning(
                "plant_filter=%s 在載入的廠區(plant)中都找不到；mail_list/acl_user_role 將為空。"
                "請確認 --plants 給的是 VOC_plant.plantno 的值。", plant_filter,
            )
    else:
        plant_nos = [p.plant_no for p in plant_objs]
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
    iso_objs = _drop_orphans(iso_objs, lambda i: i.plant_id, plant_ids, "isolation")
    iso_ids = {i.id for i in iso_objs}
    iso_item_objs = _drop_orphans(iso_item_objs, lambda it: it.isolation_id, iso_ids, "isolation_item")
    _load("isolation", iso_objs)
    _load("isolation_item", iso_item_objs)

    # ── 系統設定種子（只在不存在時補；用 merge 冪等）──
    _load("system_config", [SystemConfig(key=k, value=v) for k, v in _SYSTEM_CONFIG_DEFAULTS.items()])

    db.commit()
    return report
