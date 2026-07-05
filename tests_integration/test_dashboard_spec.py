"""
tests_integration/test_dashboard_spec.py — WP4（儀表板/規格/QA）B 資料層整合測試

真連 PostgreSQL（b_db fixture，見 tests_integration/conftest.py），驗證：
  services_b/dashboard_service.py — spec JOIN reading_current → 燈號 → DashboardRow
  services_b/spec_service.py      — 規格 CRUD、spec_apply 送簽/核准套用（I/M/D）
  services_b/qa_service.py        — QA 手測值寫入 reading_current + reading_history 快照

★ 燈號一致性表格測試（本檔重點）：燈號計算一律委派既有純函式
  `services.dashboard_service._calculate_light()`（A 棧），B 棧只負責「numeric 門檻/新讀值形狀
  → A 純函式吃的舊字串形狀」這一層轉接（`services_b.dashboard_service._bounds_to_str` /
  `_reading_raw_and_broken`）。這裡逐案驗證：B 轉接層算出的字串形狀，丟進同一顆 `_calculate_light`
  純函式後，跟「手寫等價 A 風格字串」直接丟進去的結果完全一致——確保轉接層沒有語意漂移。
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from models_b import Item, MailList, Spec, ReadingCurrent, ReadingHistory, SpecApply, Tranlog
from services.dashboard_service import _calculate_light
from services.flow_service import FlowStatus
from services_b.control_service import create_isolation, is_item_isolated
from services_b.dashboard_service import get_dashboard_rows, _bounds_to_str, _reading_raw_and_broken
from services_b.flow_service import process_sign
from services_b.qa_service import QA_SOURCE_ID, list_qa_items, update_qa_value
from services_b.spec_service import (
    create_spec,
    create_spec_apply,
    apply_spec_from_form,
    delete_spec,
    display_name_for,
    list_spec_applies,
    list_specs,
    update_spec,
)
from schemas.control_schema import ControlCreate, ControlItemBase
from scripts.seed_test_data import APPLICANT_EMPNO, SIGNER_EMPNO, TEST_PLANT_ID, TEST_PLANT_NO


# ============================================================
# 1. 儀表板資料列：形狀與燈號（種子基準值全部正常 → 應全綠）
# ============================================================

def test_dashboard_rows_shape_and_light(b_db):
    rows = get_dashboard_rows(b_db)

    assert len(rows) == 3
    assert {r.plantno for r in rows} == {TEST_PLANT_NO}
    # display_name 取代硬編映射：pH1->pH、Cu1->Cu、VOC1->VOC
    assert {r.item for r in rows} == {"pH", "Cu", "VOC"}

    for r in rows:
        assert r.light_status == "G", f"{r.item} 基準值應為綠燈，實際 {r.light_status}"
        assert r.is_anomaly is False
        assert r.broken == 0
        assert r.rain_24h == ""  # 種子資料未填 rain_24h，B 棧選填欄位預設空字串

    # rowspan：同廠區只有第一列 show_plant=True，rowspan 涵蓋全部 3 列
    first = rows[0]
    assert first.show_plant is True
    assert first.plant_rowspan == 3
    for r in rows[1:]:
        assert r.show_plant is False
        assert r.plant_rowspan == 0


def test_dashboard_rows_unit_and_law_spec(b_db):
    """單位/法規值等基本欄位應正確帶出（非燈號相關，但驗收基準要求「輸出對齊現有 DashboardRow」）。"""
    rows = get_dashboard_rows(b_db)
    ph_row = next(r for r in rows if r.item == "pH")
    assert ph_row.unit == "pH"
    assert ph_row.law_spec == "6-9"
    assert ph_row.oos == "6.0-9.0"
    assert ph_row.rvalue_raw == "7.20"


# ============================================================
# 2. isolation_checker 注入 → 保養中
# ============================================================

def test_isolation_checker_fake_injection_shows_maintenance(b_db):
    """呼叫端注入的假隔離判斷函式：只要回傳 True，該列必須顯示保養中 + broken=2 + 燈號 '-'。"""
    def checker(plant_no: str, item: str) -> bool:
        return plant_no == TEST_PLANT_NO and item == "pH1"

    rows = get_dashboard_rows(b_db, isolation_checker=checker)
    ph_row = next(r for r in rows if r.item == "pH")
    assert ph_row.rvalue_raw == "保養中"
    assert ph_row.broken == 2
    assert ph_row.light_status == "-"
    assert ph_row.is_anomaly is True

    # 沒被隔離的項目不受影響，仍是正常綠燈
    cu_row = next(r for r in rows if r.item == "Cu")
    assert cu_row.light_status == "G"


def test_isolation_checker_real_integration_via_control_service(b_db):
    """
    真實整合：申請→送簽→核准（services_b.control_service/flow_service，WP3 既有實作），
    再用 is_item_isolated() 當作 isolation_checker 注入 get_dashboard_rows()，驗證推導出的
    保養中狀態能正確反映在儀表板列上（C 決策：隔離不竄改 reading_current，只在顯示層推導）。
    """
    # 種子資料（scripts/seed_test_data.py，WP1 凍結檔）只餵了「水質異常」這個派報用 rpttype，
    # 沒有隔離簽核專用的「水保養中」（見 services.flow_service.build_rtype_list：Cu1 不含
    # 'VOC' 字樣 → 歸類水保養中）。這裡在測試內另外補一筆，不動 seed_test_data.py 本體。
    b_db.add(
        MailList(
            plant_no=TEST_PLANT_NO, rpttype="水保養中", emp_no=SIGNER_EMPNO,
            emp_name="測試簽核人", mail_type="TO", mail_on=True, sign_grp=True,
        )
    )
    b_db.flush()

    now = datetime.now()
    data = ControlCreate(
        plantid=TEST_PLANT_ID, mdfdesc="WP4 儀表板整合測試",
        stime=now + timedelta(minutes=5),
        etime=now + timedelta(minutes=35),
        items=[ControlItemBase(plantno=TEST_PLANT_NO, item="Cu1", sourceid="1")],
    )
    iso = create_isolation(b_db, APPLICANT_EMPNO, "測試申請人", data, is_commit=True)

    ok = process_sign(
        b_db, isolation_id=iso.id, flow_id=iso.flow_id, action_id=1,  # SIGN_ACTION_APPROVE
        current_user_empno=SIGNER_EMPNO, current_user_name="測試簽核人",
    )
    assert ok is True

    mid_time = data.stime + (data.etime - data.stime) / 2

    def checker(plant_no: str, item: str) -> bool:
        return is_item_isolated(b_db, plant_no, item, at_time=mid_time)

    rows = get_dashboard_rows(b_db, isolation_checker=checker)
    cu_row = next(r for r in rows if r.item == "Cu")
    assert cu_row.rvalue_raw == "保養中"
    assert cu_row.broken == 2
    assert cu_row.light_status == "-"

    # reading_current 本體完全沒被竄改（C 決策核心：讀值照實寫入不動）
    rc = b_db.query(ReadingCurrent).filter_by(plant_no=TEST_PLANT_NO, item="Cu1").first()
    assert rc.value == Decimal("1.20")
    assert rc.status == "normal"

    # 其他項目不受影響
    ph_row = next(r for r in rows if r.item == "pH")
    assert ph_row.light_status == "G"


# ============================================================
# 3. 燈號一致性表格測試（≥10 組：紅/橙/黃/綠/灰、pH 雙邊、VOC 例外、管制值不一致橙）
# ============================================================

def _fake_rc(value=None, status="normal", comm_ok=True, raw_text=None):
    """輕量假 ReadingCurrent：_reading_raw_and_broken 只讀 value/status/comm_ok/raw_text 四個屬性。"""
    return SimpleNamespace(value=value, status=status, comm_ok=comm_ok, raw_text=raw_text)


# 每組案例： (case_name, item, b_kwargs, a_kwargs, expected_light, expected_anomaly)
#   b_kwargs：B 風格 numeric 輸入（門檻 low/high/status 三元組 + rc + is_isolated）
#   a_kwargs：手寫等價 A 風格字串輸入（獨立寫死，不經過 B 轉接層）
LIGHT_CASES = [
    (
        "紅燈-單邊超標",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("3.5"), raw_text="3.5"),
        ),
        dict(rvalue_raw="3.5", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="2.0", cwms_oos="-", cwms_ooc="-", broken=0),
        "R", False,
    ),
    (
        "橙燈-範圍介於OOC與OOS之間",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("2.8"), raw_text="2.8"),
        ),
        dict(rvalue_raw="2.8", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="2.0", cwms_oos="-", cwms_ooc="-", broken=0),
        "O", False,
    ),
    (
        "橙燈-SCADA管制值與SPEC不一致",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.5, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("1.0"), raw_text="1.0"),
        ),
        dict(rvalue_raw="1.0", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.5", scada_ooc="2.5", scada_alert="2.0", cwms_oos="-", cwms_ooc="-", broken=0),
        "O", False,
    ),
    (
        "橙燈-CWMS管制值與SPEC不一致",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, 2.9, "valid"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("1.0"), raw_text="1.0"),
        ),
        dict(rvalue_raw="1.0", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="2.0", cwms_oos="2.9", cwms_ooc="-", broken=0),
        "O", False,
    ),
    (
        "黃燈-介於Alert與OOC之間",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("2.2"), raw_text="2.2"),
        ),
        dict(rvalue_raw="2.2", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="2.0", cwms_oos="-", cwms_ooc="-", broken=0),
        "Y", False,
    ),
    (
        "黃燈-超過允收值(無Alert門檻)",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, None, "na"), recv=(None, 1.0, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, None, "na"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("1.2"), raw_text="1.2"),
        ),
        dict(rvalue_raw="1.2", oos="3.0", ooc="2.5", alert_spec="-", recv="1.0",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="-", cwms_oos="-", cwms_ooc="-", broken=0),
        "Y", False,
    ),
    (
        "綠燈-完全正常",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("1.0"), raw_text="1.0"),
        ),
        dict(rvalue_raw="1.0", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="2.0", cwms_oos="-", cwms_ooc="-", broken=0),
        "G", False,
    ),
    (
        "灰燈-斷訊(comm_ok=False)",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("1.0"), comm_ok=False),
        ),
        dict(rvalue_raw="斷訊", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="2.0", cwms_oos="-", cwms_ooc="-", broken=1),
        "-", True,
    ),
    (
        "灰燈-N.D",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=None, status="nd"),
        ),
        dict(rvalue_raw="N.D", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="2.0", cwms_oos="-", cwms_ooc="-", broken=0),
        "-", True,
    ),
    (
        "灰燈-低於偵測極限",
        "VOC",
        dict(
            oos=(None, 50, "valid"), ooc=(None, 40, "valid"), alert=(None, 30, "valid"), recv=(None, 40, "valid"),
            scada_oos=(None, 50, "valid"), scada_ooc=(None, 40, "valid"), scada_alert=(None, 30, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("0.05"), status="below_lod", raw_text="<0.05"),
        ),
        dict(rvalue_raw="<0.05", oos="50", ooc="40", alert_spec="30", recv="40",
             scada_oos="50", scada_ooc="40", scada_alert="30", cwms_oos="-", cwms_ooc="-", broken=0),
        "-", True,
    ),
    (
        "灰燈-保養中(隔離覆蓋)",
        "Cu",
        dict(
            oos=(None, 3.0, "valid"), ooc=(None, 2.5, "valid"), alert=(None, 2.0, "valid"), recv=(None, 2.5, "valid"),
            scada_oos=(None, 3.0, "valid"), scada_ooc=(None, 2.5, "valid"), scada_alert=(None, 2.0, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("1.0")), is_isolated=True,
        ),
        dict(rvalue_raw="保養中", oos="3.0", ooc="2.5", alert_spec="2.0", recv="2.5",
             scada_oos="3.0", scada_ooc="2.5", scada_alert="2.0", cwms_oos="-", cwms_ooc="-", broken=2),
        "-", True,
    ),
    (
        "pH雙邊-上界超標為紅燈",
        "pH",
        dict(
            oos=(6.0, 9.0, "valid"), ooc=(6.5, 8.5, "valid"), alert=(6.8, 8.2, "valid"), recv=(6.5, 8.5, "valid"),
            scada_oos=(6.0, 9.0, "valid"), scada_ooc=(6.5, 8.5, "valid"), scada_alert=(6.8, 8.2, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("9.5"), raw_text="9.5"),
        ),
        dict(rvalue_raw="9.5", oos="6.0-9.0", ooc="6.5-8.5", alert_spec="6.8-8.2", recv="6.5-8.5",
             scada_oos="6.0-9.0", scada_ooc="6.5-8.5", scada_alert="6.8-8.2", cwms_oos="-", cwms_ooc="-", broken=0),
        "R", False,
    ),
    (
        "pH雙邊-舊系統只比上界(過低不示警，維持既有行為)",
        "pH",
        dict(
            oos=(6.0, 9.0, "valid"), ooc=(6.5, 8.5, "valid"), alert=(6.8, 8.2, "valid"), recv=(6.5, 8.5, "valid"),
            scada_oos=(6.0, 9.0, "valid"), scada_ooc=(6.5, 8.5, "valid"), scada_alert=(6.8, 8.2, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("5.0"), raw_text="5.0"),
        ),
        dict(rvalue_raw="5.0", oos="6.0-9.0", ooc="6.5-8.5", alert_spec="6.8-8.2", recv="6.5-8.5",
             scada_oos="6.0-9.0", scada_ooc="6.5-8.5", scada_alert="6.8-8.2", cwms_oos="-", cwms_ooc="-", broken=0),
        "G", False,
    ),
    (
        "VOC例外-SCADA比SPEC嚴不算不一致",
        "VOC1",  # 項目名須含 'VOC' 字樣才會觸發 is_voc 例外分支
        dict(
            oos=(None, 50, "valid"), ooc=(None, 40, "valid"), alert=(None, 30, "valid"), recv=(None, 40, "valid"),
            scada_oos=(None, 45, "valid"), scada_ooc=(None, 40, "valid"), scada_alert=(None, 30, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("10"), raw_text="10"),
        ),
        dict(rvalue_raw="10", oos="50", ooc="40", alert_spec="30", recv="40",
             scada_oos="45", scada_ooc="40", scada_alert="30", cwms_oos="-", cwms_ooc="-", broken=0),
        "G", False,
    ),
    (
        "VOC-SCADA比SPEC寬鬆仍算不一致(橙燈)",
        "VOC1",
        dict(
            oos=(None, 50, "valid"), ooc=(None, 40, "valid"), alert=(None, 30, "valid"), recv=(None, 40, "valid"),
            scada_oos=(None, 55, "valid"), scada_ooc=(None, 40, "valid"), scada_alert=(None, 30, "valid"),
            cwms_oos=(None, None, "na"), cwms_ooc=(None, None, "na"),
            rc=_fake_rc(value=Decimal("10"), raw_text="10"),
        ),
        dict(rvalue_raw="10", oos="50", ooc="40", alert_spec="30", recv="40",
             scada_oos="55", scada_ooc="40", scada_alert="30", cwms_oos="-", cwms_ooc="-", broken=0),
        "O", False,
    ),
]


@pytest.mark.parametrize(
    "case_name,item,b_kwargs,a_kwargs,expected_light,expected_anomaly",
    LIGHT_CASES,
    ids=[c[0] for c in LIGHT_CASES],
)
def test_light_consistency_b_transcode_matches_a_pure_function(
    case_name, item, b_kwargs, a_kwargs, expected_light, expected_anomaly
):
    """
    表格驅動一致性測試：B 轉接層（_bounds_to_str/_reading_raw_and_broken）產生的字串
    丟進 `_calculate_light`，必須與「手寫等價 A 風格字串」丟進同一顆函式的結果完全一致，
    且兩者都要等於預期燈號。不需要連 DB（純函式驗證），但因為是 WP4 驗收要求的一部分，
    與其餘真 DB 測試放在同一個檔案，統一由 `pytest tests_integration/` 一併驗證。
    """
    rvalue_raw, broken = _reading_raw_and_broken(b_kwargs["rc"], b_kwargs.get("is_isolated", False))

    b_row = dict(
        item=item,
        rvalue_raw=rvalue_raw,
        oos=_bounds_to_str(*b_kwargs["oos"]),
        ooc=_bounds_to_str(*b_kwargs["ooc"]),
        alert_spec=_bounds_to_str(*b_kwargs["alert"]),
        recv=_bounds_to_str(*b_kwargs["recv"]),
        scada_oos=_bounds_to_str(*b_kwargs["scada_oos"]),
        scada_ooc=_bounds_to_str(*b_kwargs["scada_ooc"]),
        scada_alert=_bounds_to_str(*b_kwargs["scada_alert"]),
        cwms_oos=_bounds_to_str(*b_kwargs["cwms_oos"]),
        cwms_ooc=_bounds_to_str(*b_kwargs["cwms_ooc"]),
        broken=broken,
    )
    b_light, b_anomaly = _calculate_light(b_row)

    a_row = dict(item=item, **a_kwargs)
    a_light, a_anomaly = _calculate_light(a_row)

    assert b_light == expected_light, f"[{case_name}] B 燈號預期 {expected_light}，實際 {b_light}"
    assert a_light == expected_light, f"[{case_name}] A 燈號預期 {expected_light}，實際 {a_light}"
    assert b_anomaly == expected_anomaly
    assert a_anomaly == expected_anomaly
    assert (b_light, b_anomaly) == (a_light, a_anomaly), f"[{case_name}] A/B 兩棧燈號不一致！"


# ============================================================
# 4. 規格值 CRUD（numeric 門檻）
# ============================================================

def test_spec_crud(b_db):
    b_db.add(Item(item_id=9200, item="Zn1", display_name="Zn", unit="mg/L", is_active=True))
    b_db.commit()

    spec = create_spec(
        b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "Zn1",
        remark="新增測試", oos_high=Decimal("5.0"), oos_status="valid",
        ooc_high=Decimal("4.0"), ooc_status="valid", source_id=1, seqno=10,
    )
    assert spec.plant_no == TEST_PLANT_NO and spec.item == "Zn1"
    assert spec.oos_high == Decimal("5.0")

    # 重覆新增應擋下
    with pytest.raises(ValueError):
        create_spec(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "Zn1", oos_high=Decimal("1.0"))

    updated = update_spec(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "Zn1", remark="修改測試", oos_high=Decimal("6.0"))
    assert updated.oos_high == Decimal("6.0")

    specs = list_specs(b_db, plant_no=TEST_PLANT_NO, item="Zn1")
    assert len(specs) == 1
    assert specs[0]["display_name"] == "Zn"
    assert specs[0]["oos_high"] == Decimal("6.0")

    ok = delete_spec(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "Zn1", remark="刪除測試")
    assert ok is True
    assert list_specs(b_db, plant_no=TEST_PLANT_NO, item="Zn1") == []

    # tranlog 應記錄 I/M/D 三筆
    logs = b_db.query(Tranlog).filter_by(emp_no=APPLICANT_EMPNO).order_by(Tranlog.id).all()
    assert [l.log_type for l in logs] == ["I", "M", "D"]


def test_display_name_for(b_db):
    assert display_name_for(b_db, "pH1") == "pH"
    assert display_name_for(b_db, "Cu1") == "Cu"
    assert display_name_for(b_db, "不存在的項目") == "不存在的項目"


# ============================================================
# 5. spec_apply 送簽單：I(新增)/M(修改)/D(刪除) 核准套用
# ============================================================

def test_spec_apply_insert_flow(b_db):
    b_db.add(Item(item_id=9201, item="Fe1", display_name="Fe", unit="mg/L", is_active=True))
    b_db.commit()

    apply_row = create_spec_apply(
        b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "Fe1", "I",
        payload={"oos_high": 8.0, "oos_status": "valid", "source_id": 1, "seqno": 20},
        remark="新增送簽測試",
    )
    assert apply_row.fstatus == int(FlowStatus.待簽核)
    assert apply_row.formno  # 已配發流水號

    apply_spec_from_form(b_db, apply_row.id, SIGNER_EMPNO)
    b_db.commit()

    spec = b_db.query(Spec).filter_by(plant_no=TEST_PLANT_NO, item="Fe1").first()
    assert spec is not None
    assert spec.oos_high == Decimal("8.0")


def test_spec_apply_modify_flow(b_db):
    apply_row = create_spec_apply(
        b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "pH1", "M",
        payload={"oos_high": 9.5}, remark="修改送簽測試",
    )
    apply_spec_from_form(b_db, apply_row.id, SIGNER_EMPNO)
    b_db.commit()

    spec = b_db.query(Spec).filter_by(plant_no=TEST_PLANT_NO, item="pH1").first()
    assert spec.oos_high == Decimal("9.5")
    assert spec.oos_low == Decimal("6.0")  # 未在 payload 內的欄位維持原值


def test_spec_apply_delete_flow(b_db):
    apply_row = create_spec_apply(
        b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "Cu1", "D", payload={}, remark="刪除送簽測試",
    )
    apply_spec_from_form(b_db, apply_row.id, SIGNER_EMPNO)
    b_db.commit()

    assert b_db.query(Spec).filter_by(plant_no=TEST_PLANT_NO, item="Cu1").first() is None


def test_spec_apply_duplicate_pending_is_blocked(b_db):
    """同廠區/項目已有一筆待簽核/簽核中的申請單時，禁止重覆申請（本檔已修正的防呆邏輯）。"""
    create_spec_apply(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "VOC1", "M", payload={"oos_high": 60})
    with pytest.raises(ValueError):
        create_spec_apply(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "VOC1", "M", payload={"oos_high": 70})


def test_list_spec_applies(b_db):
    create_spec_apply(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "pH1", "M", payload={"oos_high": 9.1})
    applies = list_spec_applies(b_db, plant_no=TEST_PLANT_NO, item="pH1")
    assert len(applies) == 1
    assert applies[0].ftype == "M"
    assert applies[0].payload["oos_high"] == 9.1


# ============================================================
# 6. QA 手測值寫入 → reading_current + reading_history 快照 + tranlog
# ============================================================

def test_qa_update_value_writes_current_history_and_tranlog(b_db):
    # 種子資料 TEST1 三項目皆為 SCADA 來源(source_id=1)，這裡在測試內另建一個 QA 來源測試項目
    b_db.add(Item(item_id=9300, item="CODQA1", display_name="CODQA", unit="mg/L", is_active=True))
    b_db.add(
        Spec(
            plant_no=TEST_PLANT_NO, item="CODQA1", source_id=QA_SOURCE_ID,
            oos_high=Decimal("100"), oos_status="valid", ooc_high=Decimal("80"), ooc_status="valid",
            seqno=30, updated_at=datetime.now(timezone.utc),
        )
    )
    b_db.commit()

    ok = update_qa_value(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "CODQA1", "42.50", remark="QA測試")
    assert ok is True

    rc = b_db.query(ReadingCurrent).filter_by(plant_no=TEST_PLANT_NO, item="CODQA1").first()
    assert rc is not None
    assert rc.value == Decimal("42.50")
    assert rc.status == "normal"
    assert rc.comm_ok is True
    assert rc.raw_text == "42.50"

    hist = (
        b_db.query(ReadingHistory)
        .filter_by(plant_no=TEST_PLANT_NO, item="CODQA1")
        .order_by(ReadingHistory.id.desc())
        .first()
    )
    assert hist is not None
    assert hist.value == Decimal("42.50")
    assert hist.spec_oos_high == Decimal("100")
    assert hist.spec_ooc_high == Decimal("80")

    tlog = b_db.query(Tranlog).filter_by(emp_no=APPLICANT_EMPNO).order_by(Tranlog.id.desc()).first()
    assert tlog is not None
    assert tlog.log_type == "M"
    assert tlog.data_after["value"] == "42.50"

    # N.D 案例：value 應為 NULL、status='nd'
    update_qa_value(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "CODQA1", "N.D")
    rc2 = b_db.query(ReadingCurrent).filter_by(plant_no=TEST_PLANT_NO, item="CODQA1").first()
    assert rc2.value is None
    assert rc2.status == "nd"

    # 非 QA 來源防呆：pH1 是 SCADA 來源，禁止手動輸入
    with pytest.raises(ValueError):
        update_qa_value(b_db, APPLICANT_EMPNO, TEST_PLANT_NO, "pH1", "7.00")


def test_list_qa_items_includes_qa_source_only(b_db):
    b_db.add(Item(item_id=9301, item="CODQA2", display_name="CODQA2", unit="mg/L", is_active=True))
    b_db.add(
        Spec(
            plant_no=TEST_PLANT_NO, item="CODQA2", source_id=QA_SOURCE_ID,
            oos_high=Decimal("50"), oos_status="valid", seqno=31, updated_at=datetime.now(timezone.utc),
        )
    )
    b_db.commit()

    items = list_qa_items(b_db)
    plant_items = {(i["plant_no"], i["item"]) for i in items}
    assert (TEST_PLANT_NO, "CODQA2") in plant_items
    # pH1/Cu1/VOC1 是 SCADA 來源，不應出現在 QA 清單
    assert (TEST_PLANT_NO, "pH1") not in plant_items
