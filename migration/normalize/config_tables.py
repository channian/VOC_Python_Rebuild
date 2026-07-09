"""
migration/normalize/config_tables.py — A→B「設定類小表」純轉換函式。

契約（見 migration/normalize/__init__.py）：每個函式輸入 = list[dict]（key 為 A 表原始 DB 欄位名，
匯出腳本用 SELECT * 所得），輸出 = list[<models_b 的 ORM 物件>]（未 save，呼叫端負責用
migration/io.py 的 upsert() 落地）。全部是純函式，不連 DB，可直接對回傳物件屬性單元測試。

A 端來源欄位對照（依實際 A 端 ORM model 或欄位假設）：
  VOC_source          models/spec_model.py 系列未提供 ORM，依規格書欄位：sourceid, source
  VOC_item            同上，依規格書欄位：itemid, item, unit, stype（stype 本模組不搬，
                       display_name 的別名對照非 A 資料來源，一律先填 None）
  VOC_plant           依規格書欄位：plantid, plantno, sort, isShow
  VOC_dept            ★無 A 端 ORM 檔可查，欄位為假設，實際欄位以公司匯出為準★
                       本函式對 plant_id/dept_no 兩個關鍵欄位都用多個候選 key 容錯讀取。
  VOC_Mail_Type       models/maillist_model.py 的 VocMailType：typeid, RptType
  VOC_Curve           ★無 A 端 ORM 檔可查，欄位為假設，實際欄位以公司匯出為準★
                       容錯 key：plantno/plant_no、item、URL/url/Url。
  sys_aclrole         models/acl_model.py 的 SysAclRole：roleid, rolename
  sys_aclrolerights   models/acl_model.py 的 SysAclRoleRights：roleid, rightsid, allowrights
"""

from typing import Any, Dict, List

from models_b import AclRole, AclRoleRights, Curve, Dept, Item, MailTypeModel, Plant, Source


def normalize_source(rows: List[Dict[str, Any]]) -> List[Source]:
    """A VOC_source{sourceid, source} → Source(source_id, name)。"""
    out: List[Source] = []
    for row in rows:
        out.append(Source(source_id=row.get("sourceid"), name=row.get("source")))
    return out


def normalize_item(rows: List[Dict[str, Any]]) -> List[Item]:
    """A VOC_item{itemid, item, unit, stype} → Item(item_id, item, display_name=None, unit, is_active=True)。

    display_name（舊程式硬編的 pH1→pH、COD2→COD 別名對照）非 A 端資料，一律先填 None，日後另補。
    """
    out: List[Item] = []
    for row in rows:
        out.append(
            Item(
                item_id=row.get("itemid"),
                item=row.get("item"),
                display_name=None,
                unit=row.get("unit"),
                is_active=True,
            )
        )
    return out


def normalize_plant(rows: List[Dict[str, Any]]) -> List[Plant]:
    """A VOC_plant{plantid, plantno, sort, isShow} → Plant(...)。

    plantid==29（舊 ALL 虛擬列）→ kind='all'；其餘 → kind='normal'。
    """
    out: List[Plant] = []
    for row in rows:
        plantid = row.get("plantid")
        sort = row.get("sort")
        out.append(
            Plant(
                plant_id=plantid,
                plant_no=row.get("plantno"),
                kind="all" if plantid == 29 else "normal",
                is_show=bool(row.get("isShow")),
                sort=sort if sort is not None else 0,
            )
        )
    return out


def normalize_dept(rows: List[Dict[str, Any]]) -> List[Dept]:
    """A VOC_dept（★無 A 端 ORM 檔，欄位為假設，實際欄位以公司匯出為準★）→ Dept(plant_id, dept_no)。

    容錯：dict key 可能是 'plantid'/'plantno_id'/'plant_id' 或 'deptno'/'dept_no'，
    依序嘗試 row.get(...)；取不到 plant_id 或 dept_no 的列略過（不中斷整批）。
    """
    out: List[Dept] = []
    for row in rows:
        plant_id = None
        for key in ("plantid", "plantno_id", "plant_id"):
            if row.get(key) is not None:
                plant_id = row.get(key)
                break

        dept_no = None
        for key in ("deptno", "dept_no"):
            if row.get(key) is not None:
                dept_no = row.get(key)
                break

        if plant_id is None or dept_no is None:
            continue

        out.append(Dept(plant_id=plant_id, dept_no=dept_no))
    return out


def normalize_mail_type(rows: List[Dict[str, Any]]) -> List[MailTypeModel]:
    """A VOC_Mail_Type{typeid, RptType}（models/maillist_model.py 的 VocMailType）
    → MailTypeModel(type_id=typeid, rpttype=RptType)。"""
    out: List[MailTypeModel] = []
    for row in rows:
        out.append(MailTypeModel(type_id=row.get("typeid"), rpttype=row.get("RptType")))
    return out


def normalize_curve(rows: List[Dict[str, Any]]) -> List[Curve]:
    """A VOC_Curve（★無 A 端 ORM 檔，欄位為假設，實際欄位以公司匯出為準★）
    → Curve(plant_no, item, url)。容錯 key：plantno/plant_no、item、URL/url/Url。"""
    out: List[Curve] = []
    for row in rows:
        plant_no = row.get("plantno")
        if plant_no is None:
            plant_no = row.get("plant_no")

        item = row.get("item")

        url = None
        for key in ("URL", "url", "Url"):
            if row.get(key) is not None:
                url = row.get(key)
                break

        out.append(Curve(plant_no=plant_no, item=item, url=url))
    return out


def normalize_acl_role(rows: List[Dict[str, Any]]) -> List[AclRole]:
    """A sys_aclrole{roleid, rolename}（models/acl_model.py 的 SysAclRole）
    → AclRole(role_id=roleid, role_name=rolename)。"""
    out: List[AclRole] = []
    for row in rows:
        out.append(AclRole(role_id=row.get("roleid"), role_name=row.get("rolename")))
    return out


def normalize_acl_role_rights(rows: List[Dict[str, Any]]) -> List[AclRoleRights]:
    """A sys_aclrolerights{roleid, rightsid, allowrights}（models/acl_model.py 的 SysAclRoleRights）
    → AclRoleRights(role_id=roleid, rights_id=rightsid, allow_rights=allowrights)。"""
    out: List[AclRoleRights] = []
    for row in rows:
        out.append(
            AclRoleRights(
                role_id=row.get("roleid"),
                rights_id=row.get("rightsid"),
                allow_rights=row.get("allowrights"),
            )
        )
    return out
