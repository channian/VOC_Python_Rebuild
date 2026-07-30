"""
scripts/seed_test_data.py — Schema B 測試種子資料（WP1 基盤工作包）

依據：docs/PhaseA執行規格書.md 第六節「種子資料規格」。

產生內容：
  1. 測試廠區 TEST1（kind=normal）＋ 3 個項目：pH1（雙邊 6-9）、Cu1（單邊）、VOC1（單邊）＋ SPEC 門檻
  2. 雙測試身分：TEST001（申請人）／TEST999（簽核人，mail_list SignGrp=1、TO），
     notesid 皆填 TEST_PLACEHOLDER（實際使用時使用者需改成自己的 Notes ID）
  3. acl / dept / sign_emp / mail_type 最小集
  4. 模擬 A 端表 kepware_sim(datetime, tagname, value, quality) ＋ 對應 tag_mapping：
     六種案例（正常值／超標值觸發派報／N.D／<0.05／quality=bad／quality=good但value空）
  5. reading_current / reading_history 初始一輪（與 kepware_sim 六案例分開，是獨立的「目前已生效」基準值）
  6. system_config 四個種子鍵

冪等性：採「先清後灌」策略——每個表先刪除本腳本擁有的資料範圍（TEST1 廠區、
TEST001/TEST999 工號、kepware_sim 全表），再重新寫入，因此可重複執行。
全域小型目錄表（source/acl_role/acl_role_rights/mail_type/system_config）採 upsert，
不清空，避免影響其他測試腳本可能已經寫入的目錄資料。

用法：
  python scripts/seed_test_data.py
"""

import sys
import os
from datetime import datetime, timezone
from decimal import Decimal

# 讓腳本可以在 repo 根目錄外執行時仍然找得到 models_b/database_b（專案根目錄加入 sys.path）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_b import BSessionLocal, create_all_b  # noqa: E402
from models_b import (  # noqa: E402
    Plant,
    Item,
    Source,
    Spec,
    ReadingCurrent,
    ReadingHistory,
    Dept,
    AclRole,
    AclUserRole,
    AclRoleRights,
    SignEmp,
    MailList,
    MailTypeModel,
    Employee,
    SystemConfig,
    TagMapping,
    KepwareSim,
)

# ── 種子資料常數 ──────────────────────────────────────────────
TEST_PLANT_NO = "TEST1"
TEST_PLANT_ID = 990  # 刻意用真實廠區不會用到的高位數字，避免與正式資料衝突
TEST_DEPT_NO = "TESTDEPT"
NOTES_PLACEHOLDER = "TEST_PLACEHOLDER"  # 使用者要求：實際使用時改成自己的 Notes ID
APPLICANT_EMPNO = "TEST001"  # 申請人身分
SIGNER_EMPNO = "TEST999"  # 簽核人身分
WATER_RPTTYPE = "水質異常"  # 沿用舊系統既有報表類型名稱（services/warning_service.WATER_RPTTYPE 同值）


def _upsert(session, model, filters: dict, values: dict):
    """通用 upsert：filters 找得到就更新 values，找不到就用 filters+values 新增。"""
    obj = session.query(model).filter_by(**filters).first()
    if obj is None:
        obj = model(**filters, **values)
        session.add(obj)
    else:
        for k, v in values.items():
            setattr(obj, k, v)
    return obj


def _clear_test_scope(session) -> None:
    """先清：整庫依 FK 依賴反序逐表清空。

    2026-07-01 主控修正：原版只清 WP1 自己種的範圍，但 WP2~WP5 的整合測試會
    commit isolation/sign_flow/mail_log 等表的資料，殘留列的 FK 會擋住 plant 刪除
    （曾實際發生 isolation_plant_id_fkey 違反）。voc_b 是專用測試庫，
    每次 seed 前整庫清空最穩，也讓所有 WP 的測試起點一致。
    """
    from models_b import BaseB

    for table in reversed(BaseB.metadata.sorted_tables):
        session.execute(table.delete())
    session.flush()


def _seed_catalog(session) -> None:
    """全域小型目錄表：source / acl_role / acl_role_rights / mail_type（upsert，不清空）。"""
    _upsert(session, Source, {"source_id": 1}, {"name": "SCADA"})
    _upsert(session, Source, {"source_id": 2}, {"name": "CWMS"})
    _upsert(session, Source, {"source_id": 3}, {"name": "QA"})

    # roleid 定義沿用舊系統 services/acl_service.py 註解：
    # 1系統管理員/2規格維護/3隔離維護/4派報簡訊啟用/5停用/6派送名單/7隔離查詢
    role_names = {
        1: "系統管理員",
        2: "規格維護",
        3: "隔離維護",
        4: "派報簡訊啟用",
        5: "停用",
        6: "派送名單",
        7: "隔離查詢",
    }
    for role_id, role_name in role_names.items():
        _upsert(session, AclRole, {"role_id": role_id}, {"role_name": role_name})

    # 最小權限集：隔離維護(3)/隔離查詢(7) 各給自己 rights_id 全開（allow_rights=1）
    _upsert(session, AclRoleRights, {"role_id": 3, "rights_id": 3}, {"allow_rights": 1})
    _upsert(session, AclRoleRights, {"role_id": 7, "rights_id": 7}, {"allow_rights": 1})

    _upsert(session, MailTypeModel, {"type_id": 1}, {"rpttype": WATER_RPTTYPE})
    _upsert(session, MailTypeModel, {"type_id": 2}, {"rpttype": "規格維護"})
    _upsert(session, MailTypeModel, {"type_id": 3}, {"rpttype": "隔離申請"})

    _upsert(
        session,
        SystemConfig,
        {"key": "staleness_minutes"},
        {"value": "30", "updated_at": datetime.now(timezone.utc)},
    )
    _upsert(
        session,
        SystemConfig,
        {"key": "sync_interval_minutes"},
        {"value": "5", "updated_at": datetime.now(timezone.utc)},
    )
    _upsert(
        session,
        SystemConfig,
        {"key": "dispatch_interval_minutes"},
        {"value": "15", "updated_at": datetime.now(timezone.utc)},
    )
    _upsert(
        session,
        SystemConfig,
        {"key": "mail_paused"},
        {"value": "false", "updated_at": datetime.now(timezone.utc)},
    )
    _upsert(
        session,
        SystemConfig,
        # ControlTime（隔離時間修改，roleid=12 環工部例外通道）的隔離總時長上限（小時）。
        # "0" = 無上限（維持現行「不受 1 小時上限限制」的既有行為），語意見
        # services_b/control_service.py._get_control_time_max_hours()。
        {"key": "control_time_max_hours"},
        {"value": "0", "updated_at": datetime.now(timezone.utc)},
    )


def _seed_plant_item_spec(session) -> None:
    """TEST1 廠區 ＋ 3 個項目（pH 雙邊 6-9 / Cu 單邊 / VOC 單邊）＋ SPEC 門檻。"""
    session.add(Plant(plant_id=TEST_PLANT_ID, plant_no=TEST_PLANT_NO, kind="normal", is_show=True, sort=999))

    session.add(Item(item_id=9001, item="pH1", display_name="pH", unit="pH", is_active=True))
    session.add(Item(item_id=9002, item="Cu1", display_name="Cu", unit="mg/L", is_active=True))
    session.add(Item(item_id=9003, item="VOC1", display_name="VOC", unit="ppm", is_active=True))
    session.flush()

    now = datetime.now(timezone.utc)

    # pH1：雙邊規格 6-9（法規 6-9），OOC 6.5-8.5，Alert 6.8-8.2，允收值同 OOC
    session.add(
        Spec(
            plant_no=TEST_PLANT_NO,
            item="pH1",
            law_text="6-9",
            oos_low=Decimal("6.0"), oos_high=Decimal("9.0"), oos_status="valid",
            ooc_low=Decimal("6.5"), ooc_high=Decimal("8.5"), ooc_status="valid",
            alert_low=Decimal("6.8"), alert_high=Decimal("8.2"), alert_status="valid",
            recv_low=Decimal("6.5"), recv_high=Decimal("8.5"), recv_status="valid",
            source_id=1, tagname="TEST.PH1.PV", seqno=1,
            updated_at=now,
        )
    )
    # Cu1：單邊規格，OOS 3.0 / OOC 2.5 / Alert 2.0 / 允收 2.5
    session.add(
        Spec(
            plant_no=TEST_PLANT_NO,
            item="Cu1",
            law_text="3.0",
            oos_high=Decimal("3.0"), oos_status="valid",
            ooc_high=Decimal("2.5"), ooc_status="valid",
            alert_high=Decimal("2.0"), alert_status="valid",
            recv_high=Decimal("2.5"), recv_status="valid",
            source_id=1, tagname="TEST.CU1.PV", seqno=2,
            updated_at=now,
        )
    )
    # VOC1：單邊規格，OOS 50 / OOC 40 / Alert 30 / 允收 40
    session.add(
        Spec(
            plant_no=TEST_PLANT_NO,
            item="VOC1",
            law_text="50",
            oos_high=Decimal("50"), oos_status="valid",
            ooc_high=Decimal("40"), ooc_status="valid",
            alert_high=Decimal("30"), alert_status="valid",
            recv_high=Decimal("40"), recv_status="valid",
            source_id=1, tagname="TEST.VOC1.PV", seqno=3,
            updated_at=now,
        )
    )
    session.flush()


def _seed_reading_baseline(session) -> None:
    """reading_current / reading_history 初始一輪——3 個項目皆為「正常」基準值（含管制值快照）。"""
    now = datetime.now(timezone.utc)

    baseline = [
        # (item, value, scada_low_high_pairs)
        ("pH1", Decimal("7.20"), dict(
            scada_oos_low=Decimal("6.0"), scada_oos_high=Decimal("9.0"),
            scada_ooc_low=Decimal("6.5"), scada_ooc_high=Decimal("8.5"),
            scada_alert_low=Decimal("6.8"), scada_alert_high=Decimal("8.2"),
        ), dict(
            spec_oos_low=Decimal("6.0"), spec_oos_high=Decimal("9.0"),
            spec_ooc_low=Decimal("6.5"), spec_ooc_high=Decimal("8.5"),
            spec_alert_low=Decimal("6.8"), spec_alert_high=Decimal("8.2"),
            spec_recv_low=Decimal("6.5"), spec_recv_high=Decimal("8.5"),
        )),
        ("Cu1", Decimal("1.20"), dict(
            scada_oos_high=Decimal("3.0"), scada_ooc_high=Decimal("2.5"), scada_alert_high=Decimal("2.0"),
        ), dict(
            spec_oos_high=Decimal("3.0"), spec_ooc_high=Decimal("2.5"), spec_alert_high=Decimal("2.0"),
            spec_recv_high=Decimal("2.5"),
        )),
        ("VOC1", Decimal("10.00"), dict(
            scada_oos_high=Decimal("50"), scada_ooc_high=Decimal("40"), scada_alert_high=Decimal("30"),
        ), dict(
            spec_oos_high=Decimal("50"), spec_ooc_high=Decimal("40"), spec_alert_high=Decimal("30"),
            spec_recv_high=Decimal("40"),
        )),
    ]

    for item, value, scada_fields, spec_snapshot in baseline:
        session.add(
            ReadingCurrent(
                plant_no=TEST_PLANT_NO,
                item=item,
                value=value,
                status="normal",
                raw_text=str(value),
                comm_ok=True,
                scada_limit_status="valid",
                cwms_limit_status="na",
                measured_at=now,
                updated_at=now,
                **scada_fields,
            )
        )
        session.add(
            ReadingHistory(
                plant_no=TEST_PLANT_NO,
                item=item,
                value=value,
                status="normal",
                raw_text=str(value),
                measured_at=now,
                **spec_snapshot,
            )
        )
    session.flush()


def _seed_identities(session) -> None:
    """雙測試身分 TEST001（申請人）／TEST999（簽核人）＋ dept/acl_user_role/sign_emp/employee/mail_list。"""
    session.add(Dept(plant_id=TEST_PLANT_ID, dept_no=TEST_DEPT_NO))

    # 兩個身分都給隔離維護角色（3）方便測試申請/查詢流程；簽核動作本身走 sign_flow，不靠 acl_role。
    session.add(AclUserRole(role_id=3, emp_no=APPLICANT_EMPNO, plant_no=TEST_PLANT_NO, dept_no=TEST_DEPT_NO, stype="user"))
    session.add(AclUserRole(role_id=3, emp_no=SIGNER_EMPNO, plant_no=TEST_PLANT_NO, dept_no=TEST_DEPT_NO, stype="user"))

    session.add(SignEmp(emp_no=APPLICANT_EMPNO, emp_name="測試申請人", email=f"{APPLICANT_EMPNO}@example.com", dep_no=TEST_DEPT_NO))
    session.add(SignEmp(emp_no=SIGNER_EMPNO, emp_name="測試簽核人", email=f"{SIGNER_EMPNO}@example.com", dep_no=TEST_DEPT_NO))

    session.add(
        Employee(
            emp_no=APPLICANT_EMPNO, emp_name="測試申請人", notes_id=NOTES_PLACEHOLDER,
            dept_no=TEST_DEPT_NO, is_leave=False, synced_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        Employee(
            emp_no=SIGNER_EMPNO, emp_name="測試簽核人", notes_id=NOTES_PLACEHOLDER,
            dept_no=TEST_DEPT_NO, is_leave=False, synced_at=datetime.now(timezone.utc),
        )
    )

    # TEST999：mail_list SignGrp=1、TO（簽核人身分要收到派報信）
    session.add(
        MailList(
            plant_no=TEST_PLANT_NO, rpttype=WATER_RPTTYPE, emp_no=SIGNER_EMPNO,
            emp_name="測試簽核人", notes_id=NOTES_PLACEHOLDER,
            mail_type="TO", mail_on=True, sign_grp=True,
        )
    )

    # 隔離申請簽核用的名單（services/flow_service.build_rtype_list：含"VOC"項目→空保養中，
    # 其餘→水保養中）。曾漏掉這兩筆，導致瀏覽器實測「送簽」時報「尚未設定簽核人員」
    # （demo_closed_loop.py / tests_integration/test_main_b_routes.py 原本各自補丁一次，
    # 2026-07-06 主控修正：直接種進 seed，兩處補丁可以拿掉但先保留亦不衝突，upsert 語意相容）。
    for isolation_rtype in ("水保養中", "空保養中"):
        session.add(
            MailList(
                plant_no=TEST_PLANT_NO, rpttype=isolation_rtype, emp_no=SIGNER_EMPNO,
                emp_name="測試簽核人", notes_id=NOTES_PLACEHOLDER,
                mail_type="TO", mail_on=True, sign_grp=True,
            )
        )
    session.flush()


def _seed_kepware_sim(session) -> None:
    """模擬 A 端表 kepware_sim ＋ 對應 tag_mapping：六種分類案例（PhaseA執行規格書第三節）。"""
    now = datetime.now(timezone.utc)

    # (tagname, item, value, quality, remark)
    cases = [
        ("TEST.PH1.PV", "pH1", "7.20", "good", "正常值"),
        ("TEST.CU1.PV", "Cu1", "5.00", "good", "超標值（觸發派報，OOS_high=3.0）"),
        ("TEST.VOC1.ND", "VOC1", "N.D", "good", "N.D 案例"),
        ("TEST.VOC1.LOD", "VOC1", "<0.05", "good", "低於偵測極限案例"),
        ("TEST.CU1.BAD", "Cu1", "1.20", "bad", "quality=bad（斷訊）案例"),
        ("TEST.PH1.EMPTY", "pH1", "", "good", "quality=good 但 value 空（已知陷阱）案例"),
    ]

    for tagname, item, value, quality, remark in cases:
        session.add(
            TagMapping(
                source_table="kepware_sim", tagname=tagname,
                plant_no=TEST_PLANT_NO, item=item, target_field="value",
                enabled=True, remark=remark,
            )
        )
        session.add(KepwareSim(datetime_=now, tagname=tagname, value=value, quality=quality))
    session.flush()


def seed() -> None:
    """執行完整種子資料寫入（先清後灌，可重複執行）。"""
    create_all_b()  # 確保表已存在（冪等）
    session = BSessionLocal()
    try:
        _clear_test_scope(session)
        _seed_catalog(session)
        _seed_plant_item_spec(session)
        _seed_reading_baseline(session)
        _seed_identities(session)
        _seed_kepware_sim(session)
        session.commit()
        print("[seed_test_data] 種子資料寫入完成。")
        print(f"  廠區：{TEST_PLANT_NO}（plant_id={TEST_PLANT_ID}），項目：pH1/Cu1/VOC1")
        print(f"  申請人：{APPLICANT_EMPNO}／簽核人：{SIGNER_EMPNO}（notesid={NOTES_PLACEHOLDER}）")
        print("  kepware_sim：6 筆分類案例 ＋ 對應 tag_mapping")
        print("  system_config：staleness_minutes/sync_interval_minutes/dispatch_interval_minutes/mail_paused")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
