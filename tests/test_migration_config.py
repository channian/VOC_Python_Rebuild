"""
tests/test_migration_config.py — migration/normalize/config_tables.py 的純邏輯測試。

不連 DB：直接餵手寫的 A 形狀 dict（key = A 表原始 DB 欄位名），assert 轉出的 B ORM 物件屬性正確。
"""

from migration.normalize.config_tables import (
    normalize_acl_role,
    normalize_acl_role_rights,
    normalize_curve,
    normalize_dept,
    normalize_item,
    normalize_mail_type,
    normalize_plant,
    normalize_source,
)
from models_b import AclRole, AclRoleRights, Curve, Dept, Item, MailTypeModel, Plant, Source


# ---------------------------------------------------------------------------
# normalize_source
# ---------------------------------------------------------------------------

class TestNormalizeSource:
    def test_basic(self):
        rows = [{"sourceid": 1, "source": "SCADA"}, {"sourceid": 2, "source": "CWMS"}]
        out = normalize_source(rows)
        assert len(out) == 2
        assert isinstance(out[0], Source)
        assert out[0].source_id == 1
        assert out[0].name == "SCADA"
        assert out[1].source_id == 2
        assert out[1].name == "CWMS"

    def test_empty(self):
        assert normalize_source([]) == []


# ---------------------------------------------------------------------------
# normalize_item
# ---------------------------------------------------------------------------

class TestNormalizeItem:
    def test_basic(self):
        rows = [{"itemid": 10, "item": "pH1", "unit": None, "stype": "水"}]
        out = normalize_item(rows)
        assert len(out) == 1
        item = out[0]
        assert isinstance(item, Item)
        assert item.item_id == 10
        assert item.item == "pH1"
        assert item.display_name is None
        assert item.unit is None
        assert item.is_active is True

    def test_with_unit(self):
        rows = [{"itemid": 11, "item": "COD2", "unit": "mg/L", "stype": "水"}]
        out = normalize_item(rows)
        assert out[0].unit == "mg/L"
        assert out[0].display_name is None

    def test_empty(self):
        assert normalize_item([]) == []


# ---------------------------------------------------------------------------
# normalize_plant
# ---------------------------------------------------------------------------

class TestNormalizePlant:
    def test_plantid_29_is_all(self):
        rows = [{"plantid": 29, "plantno": "ALL", "sort": 99, "isShow": 1}]
        out = normalize_plant(rows)
        assert len(out) == 1
        plant = out[0]
        assert isinstance(plant, Plant)
        assert plant.plant_id == 29
        assert plant.plant_no == "ALL"
        assert plant.kind == "all"
        assert plant.is_show is True
        assert plant.sort == 99

    def test_normal_plant(self):
        rows = [{"plantid": 7, "plantno": "K7", "sort": 1, "isShow": 1}]
        out = normalize_plant(rows)
        assert out[0].kind == "normal"

    def test_isshow_zero_is_false(self):
        rows = [{"plantid": 5, "plantno": "K5", "sort": 2, "isShow": 0}]
        out = normalize_plant(rows)
        assert out[0].is_show is False

    def test_sort_none_defaults_zero(self):
        rows = [{"plantid": 3, "plantno": "K3", "sort": None, "isShow": 1}]
        out = normalize_plant(rows)
        assert out[0].sort == 0

    def test_empty(self):
        assert normalize_plant([]) == []


# ---------------------------------------------------------------------------
# normalize_dept（容錯 key）
# ---------------------------------------------------------------------------

class TestNormalizeDept:
    def test_plantid_deptno_keys(self):
        rows = [{"plantid": 7, "deptno": "D001"}]
        out = normalize_dept(rows)
        assert len(out) == 1
        dept = out[0]
        assert isinstance(dept, Dept)
        assert dept.plant_id == 7
        assert dept.dept_no == "D001"

    def test_plant_id_dept_no_keys(self):
        rows = [{"plant_id": 8, "dept_no": "D002"}]
        out = normalize_dept(rows)
        assert out[0].plant_id == 8
        assert out[0].dept_no == "D002"

    def test_plantno_id_key(self):
        rows = [{"plantno_id": 9, "deptno": "D003"}]
        out = normalize_dept(rows)
        assert out[0].plant_id == 9
        assert out[0].dept_no == "D003"

    def test_missing_plant_id_skipped(self):
        rows = [{"deptno": "D004"}]
        out = normalize_dept(rows)
        assert out == []

    def test_missing_dept_no_skipped(self):
        rows = [{"plantid": 7}]
        out = normalize_dept(rows)
        assert out == []

    def test_mixed_valid_and_invalid(self):
        rows = [{"plantid": 7, "deptno": "D001"}, {"plantid": 8}]
        out = normalize_dept(rows)
        assert len(out) == 1
        assert out[0].dept_no == "D001"

    def test_empty(self):
        assert normalize_dept([]) == []


# ---------------------------------------------------------------------------
# normalize_mail_type
# ---------------------------------------------------------------------------

class TestNormalizeMailType:
    def test_basic(self):
        rows = [{"typeid": 1, "RptType": "水質異常"}]
        out = normalize_mail_type(rows)
        assert len(out) == 1
        mt = out[0]
        assert isinstance(mt, MailTypeModel)
        assert mt.type_id == 1
        assert mt.rpttype == "水質異常"

    def test_empty(self):
        assert normalize_mail_type([]) == []


# ---------------------------------------------------------------------------
# normalize_curve（容錯 key）
# ---------------------------------------------------------------------------

class TestNormalizeCurve:
    def test_plantno_url_upper(self):
        rows = [{"plantno": "K7", "item": "pH1", "URL": "http://example.com/curve"}]
        out = normalize_curve(rows)
        assert len(out) == 1
        curve = out[0]
        assert isinstance(curve, Curve)
        assert curve.plant_no == "K7"
        assert curve.item == "pH1"
        assert curve.url == "http://example.com/curve"

    def test_plant_no_url_lower(self):
        rows = [{"plant_no": "K9", "item": "COD2", "url": "http://example.com/curve2"}]
        out = normalize_curve(rows)
        assert out[0].plant_no == "K9"
        assert out[0].url == "http://example.com/curve2"

    def test_url_mixed_case(self):
        rows = [{"plantno": "K1", "item": "pH1", "Url": "http://example.com/curve3"}]
        out = normalize_curve(rows)
        assert out[0].url == "http://example.com/curve3"

    def test_empty(self):
        assert normalize_curve([]) == []


# ---------------------------------------------------------------------------
# normalize_acl_role / normalize_acl_role_rights
# ---------------------------------------------------------------------------

class TestNormalizeAclRole:
    def test_basic(self):
        rows = [{"roleid": 3, "rolename": "廠棟工程師"}]
        out = normalize_acl_role(rows)
        assert len(out) == 1
        role = out[0]
        assert isinstance(role, AclRole)
        assert role.role_id == 3
        assert role.role_name == "廠棟工程師"

    def test_empty(self):
        assert normalize_acl_role([]) == []


class TestNormalizeAclRoleRights:
    def test_basic(self):
        rows = [{"roleid": 3, "rightsid": 1, "allowrights": 7}]
        out = normalize_acl_role_rights(rows)
        assert len(out) == 1
        rights = out[0]
        assert isinstance(rights, AclRoleRights)
        assert rights.role_id == 3
        assert rights.rights_id == 1
        assert rights.allow_rights == 7

    def test_empty(self):
        assert normalize_acl_role_rights([]) == []


class TestDedupUniqueKey:
    """B 端 item/plant/mail_type 有 UNIQUE 約束，A 端同鍵可能重複，須去重（保留第一筆）。"""

    def test_item_dedup_by_name(self):
        out = normalize_item([
            {"itemid": 1, "item": "VOC", "unit": "ppm"},
            {"itemid": 77, "item": "VOC", "unit": "ppm"},   # 同名不同 id → 收斂
            {"itemid": 2, "item": "COD", "unit": "mg/L"},
        ])
        assert [i.item for i in out] == ["VOC", "COD"]
        assert out[0].item_id == 1  # 保留第一筆

    def test_item_skip_null_name(self):
        out = normalize_item([{"itemid": 1, "item": None, "unit": "x"}])
        assert out == []

    def test_plant_dedup_by_plantno(self):
        out = normalize_plant([
            {"plantid": 1, "plantno": "K7", "sort": 1, "isShow": 1},
            {"plantid": 99, "plantno": "K7", "sort": 2, "isShow": 1},  # 同 plantno → 收斂
        ])
        assert len(out) == 1 and out[0].plant_id == 1

    def test_mail_type_dedup_by_rpttype(self):
        out = normalize_mail_type([
            {"typeid": 1, "RptType": "水質異常"},
            {"typeid": 9, "RptType": "水質異常"},  # 同 rpttype → 收斂
        ])
        assert len(out) == 1 and out[0].type_id == 1
