"""
services_b/basedata_service.py — 基礎資料維護（廠區 / 項目 / Tag 對應，Schema B 資料層）

背景：`plant`/`item`/`tag_mapping` 三張主檔目前完全沒有網頁維護介面，只能靠 seed 腳本或
直接改 DB。公司蓋新廠棟時，環工部需要能自行在網頁上新增廠區/項目/Tag 對應，不必每次找
工程師動資料庫，本檔即為此提供的資料層（照 dept_service.py 的風格：查詢/新增/修改/刪除
+ 每次寫入都留 Tranlog 稽核；ValueError 給前端顯示中文錯誤訊息，非 ValueError 例外一律
rollback 後往上拋、由呼叫端決定如何處理）。

外鍵/參照完整性説明（models_b.py）：
  - spec.plant_no  FK → plant.plant_no
  - spec.item      FK → item.item
  - tag_mapping.plant_no / tag_mapping.item 「沒有」宣告 DB 層 ForeignKeyConstraint
    （models_b.py 原始設計即是如此——tag_mapping 是同步 JOB 的中央設定表，刻意不綁死
    FK 以便 JOB 可以彈性调整），因此「plant_no/item 必須是已存在的」屬於應用層業務規則，
    必須在這裡（服務層）擋，DB 不會自動保護。

刪除/改鍵防呆策略：
  - 刪除 plant 前：檢查 spec.plant_no / tag_mapping.plant_no 是否還有列參照該 plant_no，
    有則 raise ValueError 告知筆數，不可刪（避免刪除後 spec 表 FK 直接違反、
    也避免 tag_mapping 留下孤兒設定，往後同步 JOB 對到不存在的廠區）。
  - 刪除 item 同理，檢查 spec.item / tag_mapping.item。
  - 修改 plant_no / item 這種業務鍵本身時，套用與刪除相同的參照檢查——因為改字串鍵
    等同「舊鍵已死、新鍵誕生」，若仍有 spec/tag_mapping 掛著舊鍵，直接 UPDATE 會讓
    spec 的 DB 層 FK 直接炸掉（IntegrityError）、或讓 tag_mapping 留下對不到廠區/項目
    的孤兒設定，因此比照刪除規則先擋下，請使用者先清空相依資料再改鍵。
"""

import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models_b import Plant, Item, TagMapping, Spec, Tranlog

logger = logging.getLogger(__name__)

# ── 常數 ──────────────────────────────────────────────────────────────────

PLANT_KIND_CHOICES = ["normal", "virtual_group", "all"]

# tag_mapping.target_field 合法值：'value'（讀值本身）或六種 SCADA 自設管制值欄位之一
# （見 services_b/sync_service.py 開頭註解、models_b.py TagMapping/ReadingCurrent）。
TARGET_FIELD_CHOICES = [
    ("value", "讀值 (value)"),
    ("scada_oos_low", "SCADA OOS 下界"),
    ("scada_oos_high", "SCADA OOS 上界"),
    ("scada_ooc_low", "SCADA OOC 下界"),
    ("scada_ooc_high", "SCADA OOC 上界"),
    ("scada_alert_low", "SCADA Alert 下界"),
    ("scada_alert_high", "SCADA Alert 上界"),
]
TARGET_FIELD_VALUES = [v for v, _ in TARGET_FIELD_CHOICES]


def _tranlog(db: Session, emp_no: str, log_type: str, before: dict, after: dict, remark: str = "") -> None:
    db.add(Tranlog(emp_no=emp_no, log_type=log_type, data_before=before, data_after=after, remark=remark or ""))


# ══════════════════════════════════════════════════════════════════════════
# 廠區 PLANT
# ══════════════════════════════════════════════════════════════════════════

def list_plants(db: Session) -> list[dict]:
    rows = db.execute(select(Plant).order_by(Plant.sort, Plant.plant_id)).scalars().all()
    return [
        {"plant_id": r.plant_id, "plant_no": r.plant_no, "kind": r.kind,
         "is_show": r.is_show, "sort": r.sort}
        for r in rows
    ]


def _plant_reference_counts(db: Session, plant_no: str) -> tuple[int, int]:
    spec_cnt = db.execute(
        select(func.count()).select_from(Spec).where(Spec.plant_no == plant_no)
    ).scalar_one()
    tag_cnt = db.execute(
        select(func.count()).select_from(TagMapping).where(TagMapping.plant_no == plant_no)
    ).scalar_one()
    return spec_cnt, tag_cnt


def add_plant(db: Session, current_user_empno: str, plant_id: int, plant_no: str,
              kind: str, is_show: bool, sort: int, remark: str = "") -> None:
    try:
        plant_no = (plant_no or "").strip()
        if not plant_no:
            raise ValueError("廠區編號不可空白!")
        if kind not in PLANT_KIND_CHOICES:
            raise ValueError(f"廠區種類錯誤，須為 {'/'.join(PLANT_KIND_CHOICES)} 其一!")

        if db.execute(select(Plant).where(Plant.plant_id == plant_id)).scalar_one_or_none():
            raise ValueError(f"廠區代碼 {plant_id} 已存在!")
        if db.execute(select(Plant).where(Plant.plant_no == plant_no)).scalar_one_or_none():
            raise ValueError(f"廠區編號 {plant_no} 已存在!")

        db.add(Plant(plant_id=plant_id, plant_no=plant_no, kind=kind, is_show=is_show, sort=sort))
        _tranlog(db, current_user_empno, "I", {},
                 {"plant_id": plant_id, "plant_no": plant_no, "kind": kind, "is_show": is_show, "sort": sort},
                 remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[add_plant] 新增失敗: {e}")
        raise


def update_plant(db: Session, current_user_empno: str, plant_id: int, plant_no: str,
                  kind: str, is_show: bool, sort: int, remark: str = "") -> None:
    try:
        plant_no = (plant_no or "").strip()
        if not plant_no:
            raise ValueError("廠區編號不可空白!")
        if kind not in PLANT_KIND_CHOICES:
            raise ValueError(f"廠區種類錯誤，須為 {'/'.join(PLANT_KIND_CHOICES)} 其一!")

        entry = db.execute(select(Plant).where(Plant.plant_id == plant_id)).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要修改的廠區資料!")

        before = {"plant_id": entry.plant_id, "plant_no": entry.plant_no, "kind": entry.kind,
                  "is_show": entry.is_show, "sort": entry.sort}

        if plant_no != entry.plant_no:
            # 改業務鍵：先確認新鍵不重複，再確認舊鍵沒有相依資料（見檔頭說明）
            if db.execute(select(Plant).where(Plant.plant_no == plant_no)).scalar_one_or_none():
                raise ValueError(f"廠區編號 {plant_no} 已存在!")
            spec_cnt, tag_cnt = _plant_reference_counts(db, entry.plant_no)
            if spec_cnt or tag_cnt:
                raise ValueError(
                    f"廠區編號 {entry.plant_no} 尚有 {spec_cnt} 筆規格設定、{tag_cnt} 筆 Tag 對應使用中，"
                    "無法變更編號，請先清空相依資料!"
                )
            entry.plant_no = plant_no

        entry.kind = kind
        entry.is_show = is_show
        entry.sort = sort

        _tranlog(db, current_user_empno, "M", before,
                 {"plant_id": entry.plant_id, "plant_no": entry.plant_no, "kind": entry.kind,
                  "is_show": entry.is_show, "sort": entry.sort}, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[update_plant] 修改失敗: {e}")
        raise


def delete_plant(db: Session, current_user_empno: str, plant_id: int, remark: str = "") -> None:
    try:
        entry = db.execute(select(Plant).where(Plant.plant_id == plant_id)).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要刪除的廠區資料!")

        spec_cnt, tag_cnt = _plant_reference_counts(db, entry.plant_no)
        if spec_cnt or tag_cnt:
            raise ValueError(
                f"廠區 {entry.plant_no} 尚有 {spec_cnt} 筆規格設定、{tag_cnt} 筆 Tag 對應使用中，"
                "無法刪除，請先清除相依資料!"
            )

        before = {"plant_id": entry.plant_id, "plant_no": entry.plant_no, "kind": entry.kind,
                  "is_show": entry.is_show, "sort": entry.sort}
        db.delete(entry)
        _tranlog(db, current_user_empno, "D", before, {}, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[delete_plant] 刪除失敗: {e}")
        raise


# ══════════════════════════════════════════════════════════════════════════
# 項目 ITEM
# ══════════════════════════════════════════════════════════════════════════

def list_items(db: Session) -> list[dict]:
    rows = db.execute(select(Item).order_by(Item.item_id)).scalars().all()
    return [
        {"item_id": r.item_id, "item": r.item, "display_name": r.display_name,
         "unit": r.unit, "is_active": r.is_active}
        for r in rows
    ]


def _next_item_id(db: Session) -> int:
    max_id = db.execute(select(func.max(Item.item_id))).scalar_one()
    return (max_id or 0) + 1


def _item_reference_counts(db: Session, item: str) -> tuple[int, int]:
    spec_cnt = db.execute(
        select(func.count()).select_from(Spec).where(Spec.item == item)
    ).scalar_one()
    tag_cnt = db.execute(
        select(func.count()).select_from(TagMapping).where(TagMapping.item == item)
    ).scalar_one()
    return spec_cnt, tag_cnt


def add_item(db: Session, current_user_empno: str, item: str, display_name: Optional[str],
             unit: Optional[str], is_active: bool, remark: str = "") -> None:
    try:
        item = (item or "").strip()
        if not item:
            raise ValueError("項目原名不可空白!")

        if db.execute(select(Item).where(Item.item == item)).scalar_one_or_none():
            raise ValueError(f"項目 {item} 已存在!")

        item_id = _next_item_id(db)
        db.add(Item(item_id=item_id, item=item, display_name=display_name or None,
                     unit=unit or None, is_active=is_active))
        _tranlog(db, current_user_empno, "I", {},
                 {"item_id": item_id, "item": item, "display_name": display_name, "unit": unit,
                  "is_active": is_active}, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[add_item] 新增失敗: {e}")
        raise


def update_item(db: Session, current_user_empno: str, old_item: str, item: str,
                 display_name: Optional[str], unit: Optional[str], is_active: bool,
                 remark: str = "") -> None:
    try:
        item = (item or "").strip()
        if not item:
            raise ValueError("項目原名不可空白!")

        entry = db.execute(select(Item).where(Item.item == old_item)).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要修改的項目資料!")

        before = {"item_id": entry.item_id, "item": entry.item, "display_name": entry.display_name,
                  "unit": entry.unit, "is_active": entry.is_active}

        if item != entry.item:
            if db.execute(select(Item).where(Item.item == item)).scalar_one_or_none():
                raise ValueError(f"項目 {item} 已存在!")
            spec_cnt, tag_cnt = _item_reference_counts(db, entry.item)
            if spec_cnt or tag_cnt:
                raise ValueError(
                    f"項目 {entry.item} 尚有 {spec_cnt} 筆規格設定、{tag_cnt} 筆 Tag 對應使用中，"
                    "無法變更代碼，請先清空相依資料!"
                )
            entry.item = item

        entry.display_name = display_name or None
        entry.unit = unit or None
        entry.is_active = is_active

        _tranlog(db, current_user_empno, "M", before,
                 {"item_id": entry.item_id, "item": entry.item, "display_name": entry.display_name,
                  "unit": entry.unit, "is_active": entry.is_active}, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[update_item] 修改失敗: {e}")
        raise


def delete_item(db: Session, current_user_empno: str, item: str, remark: str = "") -> None:
    try:
        entry = db.execute(select(Item).where(Item.item == item)).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要刪除的項目資料!")

        spec_cnt, tag_cnt = _item_reference_counts(db, entry.item)
        if spec_cnt or tag_cnt:
            raise ValueError(
                f"項目 {entry.item} 尚有 {spec_cnt} 筆規格設定、{tag_cnt} 筆 Tag 對應使用中，"
                "無法刪除，請先清除相依資料!"
            )

        before = {"item_id": entry.item_id, "item": entry.item, "display_name": entry.display_name,
                  "unit": entry.unit, "is_active": entry.is_active}
        db.delete(entry)
        _tranlog(db, current_user_empno, "D", before, {}, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[delete_item] 刪除失敗: {e}")
        raise


# ══════════════════════════════════════════════════════════════════════════
# Tag 對應 TAG MAPPING（同步 JOB 的驅動表）
# ══════════════════════════════════════════════════════════════════════════

def list_tag_mappings(db: Session) -> list[dict]:
    rows = db.execute(select(TagMapping).order_by(TagMapping.id)).scalars().all()
    return [
        {"id": r.id, "source_table": r.source_table, "tagname": r.tagname,
         "plant_no": r.plant_no, "item": r.item, "target_field": r.target_field,
         "enabled": r.enabled, "remark": r.remark}
        for r in rows
    ]


def _validate_plant_and_item(db: Session, plant_no: str, item: str) -> None:
    if not db.execute(select(Plant).where(Plant.plant_no == plant_no)).scalar_one_or_none():
        raise ValueError(f"廠區 {plant_no} 不存在，請先於「廠區」分頁建立!")
    if not db.execute(select(Item).where(Item.item == item)).scalar_one_or_none():
        raise ValueError(f"項目 {item} 不存在，請先於「項目」分頁建立!")


def add_tag_mapping(db: Session, current_user_empno: str, source_table: str, tagname: str,
                     plant_no: str, item: str, target_field: str, enabled: bool,
                     remark: str = "") -> None:
    try:
        source_table = (source_table or "").strip()
        tagname = (tagname or "").strip()
        if not source_table or not tagname:
            raise ValueError("來源資料表與 Tag 名稱不可空白!")
        if target_field not in TARGET_FIELD_VALUES:
            raise ValueError(f"目標欄位錯誤，須為 {'/'.join(TARGET_FIELD_VALUES)} 其一!")

        _validate_plant_and_item(db, plant_no, item)

        existing = db.execute(
            select(TagMapping).where(TagMapping.source_table == source_table,
                                      TagMapping.tagname == tagname)
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"{source_table}/{tagname} 這組來源+Tag 已存在對應設定!")

        row = TagMapping(source_table=source_table, tagname=tagname, plant_no=plant_no,
                          item=item, target_field=target_field, enabled=enabled, remark=remark or None)
        db.add(row)
        db.flush()  # 取回自增 id 供 tranlog 記錄
        _tranlog(db, current_user_empno, "I", {},
                 {"id": row.id, "source_table": source_table, "tagname": tagname, "plant_no": plant_no,
                  "item": item, "target_field": target_field, "enabled": enabled}, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[add_tag_mapping] 新增失敗: {e}")
        raise


def update_tag_mapping(db: Session, current_user_empno: str, id: int, source_table: str,
                        tagname: str, plant_no: str, item: str, target_field: str,
                        enabled: bool, remark: str = "") -> None:
    try:
        source_table = (source_table or "").strip()
        tagname = (tagname or "").strip()
        if not source_table or not tagname:
            raise ValueError("來源資料表與 Tag 名稱不可空白!")
        if target_field not in TARGET_FIELD_VALUES:
            raise ValueError(f"目標欄位錯誤，須為 {'/'.join(TARGET_FIELD_VALUES)} 其一!")

        entry = db.execute(select(TagMapping).where(TagMapping.id == id)).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要修改的 Tag 對應資料!")

        _validate_plant_and_item(db, plant_no, item)

        if source_table != entry.source_table or tagname != entry.tagname:
            dup = db.execute(
                select(TagMapping).where(TagMapping.source_table == source_table,
                                          TagMapping.tagname == tagname,
                                          TagMapping.id != id)
            ).scalar_one_or_none()
            if dup:
                raise ValueError(f"{source_table}/{tagname} 這組來源+Tag 已存在對應設定!")

        before = {"id": entry.id, "source_table": entry.source_table, "tagname": entry.tagname,
                  "plant_no": entry.plant_no, "item": entry.item, "target_field": entry.target_field,
                  "enabled": entry.enabled}

        entry.source_table = source_table
        entry.tagname = tagname
        entry.plant_no = plant_no
        entry.item = item
        entry.target_field = target_field
        entry.enabled = enabled
        entry.remark = remark or None

        _tranlog(db, current_user_empno, "M", before,
                 {"id": entry.id, "source_table": entry.source_table, "tagname": entry.tagname,
                  "plant_no": entry.plant_no, "item": entry.item, "target_field": entry.target_field,
                  "enabled": entry.enabled}, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[update_tag_mapping] 修改失敗: {e}")
        raise


def delete_tag_mapping(db: Session, current_user_empno: str, id: int, remark: str = "") -> None:
    try:
        entry = db.execute(select(TagMapping).where(TagMapping.id == id)).scalar_one_or_none()
        if not entry:
            raise ValueError("找不到要刪除的 Tag 對應資料!")

        before = {"id": entry.id, "source_table": entry.source_table, "tagname": entry.tagname,
                  "plant_no": entry.plant_no, "item": entry.item, "target_field": entry.target_field,
                  "enabled": entry.enabled}
        db.delete(entry)
        _tranlog(db, current_user_empno, "D", before, {}, remark)
        db.commit()
    except ValueError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[delete_tag_mapping] 刪除失敗: {e}")
        raise
