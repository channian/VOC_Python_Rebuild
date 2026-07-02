import sys
import os
import pytest
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError
from schemas.control_schema import ControlCreate, ControlItemBase, ControlModify, ControlTimeUpdate
from services.control_service import next_ccno, build_modify_record_fields
from services.flow_service import Ttype, FlowStatus

# 注意：本檔純測試 pydantic 驗證邏輯與 next_ccno 純函式，
# 依 CLAUDE.md 慣例只 import services/schemas，不 import routers/main/database
# （環境無 ODBC driver、亦無 httpx2，DB/TestClient 相關測試不適用於此檔）。

def test_control_validation_time_order():
    """ 測試 EditControl 防呆：開始時間不能晚於結束時間 """
    now = datetime.now()
    with pytest.raises(ValidationError) as exc:
        ControlCreate(
            plantid=1, mdfdesc="測試",
            stime=now + timedelta(hours=2),
            etime=now + timedelta(hours=1),
            items=[ControlItemBase(plantno="K1", item="VOC", sourceid="1")]
        )
    assert "開始時間不可大於結束時間" in str(exc.value)

def test_control_validation_time_past():
    """ 測試 EditControl 防呆：開始時間不能在過去 """
    now = datetime.now()
    with pytest.raises(ValidationError) as exc:
        ControlCreate(
            plantid=1, mdfdesc="測試",
            stime=now - timedelta(hours=1),
            etime=now + timedelta(hours=1),
            items=[ControlItemBase(plantno="K1", item="VOC", sourceid="1")]
        )
    assert "開始時間不可小於系統時間" in str(exc.value)

def test_control_validation_max_hours():
    """ 測試 EditControl 防呆：隔離時間上限一律 1 小時（不分項目） """
    now = datetime.now()
    with pytest.raises(ValidationError) as exc:
        ControlCreate(
            plantid=1, mdfdesc="測試",
            stime=now + timedelta(hours=1),
            etime=now + timedelta(hours=3), # 2 小時 > 1 小時上限
            items=[ControlItemBase(plantno="K1", item="VOC", sourceid="1")]
        )
    assert "隔離廠區項目時間不得超過1小時" in str(exc.value)

def test_control_validation_max_hours_applies_to_ph_too():
    """ 舊系統一律 1 小時上限，不分 pH／其他項目；pH 超過 1 小時一樣要擋 """
    now = datetime.now()
    with pytest.raises(ValidationError) as exc:
        ControlCreate(
            plantid=1, mdfdesc="測試",
            stime=now + timedelta(minutes=10),
            etime=now + timedelta(minutes=10, seconds=3601),  # 剛好超過 1 小時 1 秒
            items=[ControlItemBase(plantno="K1", item="pH", sourceid="2")]
        )
    assert "隔離廠區項目時間不得超過1小時" in str(exc.value)

def test_control_validation_exact_one_hour_boundary_ok():
    """ 剛好 1 小時（3600 秒）應該通過，不算超過上限 """
    now = datetime.now()
    control = ControlCreate(
        plantid=1, mdfdesc="剛好一小時",
        stime=now + timedelta(minutes=5),
        etime=now + timedelta(minutes=5, seconds=3600),
        items=[ControlItemBase(plantno="K1", item="COD", sourceid="1")]
    )
    assert control.mdfdesc == "剛好一小時"

def test_control_validation_no_items():
    """ 測試 EditControl 防呆：清單為空 """
    now = datetime.now()
    with pytest.raises(ValidationError) as exc:
        ControlCreate(
            plantid=1, mdfdesc="測試",
            stime=now + timedelta(minutes=10),
            etime=now + timedelta(minutes=40),
            items=[] # 未選擇項目
        )
    assert "尚未選擇要隔離的廠區項目" in str(exc.value)

def test_control_validation_success():
    """ 測試完全正確的格式能通過 Pydantic 驗證 """
    now = datetime.now()
    control = ControlCreate(
        plantid=1, mdfdesc="正確申請",
        stime=now + timedelta(minutes=5),
        etime=now + timedelta(minutes=55),
        items=[ControlItemBase(plantno="K1", item="pH", sourceid="2")]
    )
    assert control.mdfdesc == "正確申請"


# ── ccno 流水號（next_ccno 純函式）──────────────────────────────────────────

def test_next_ccno_no_prior_record():
    """ 當日無資料時，從 000 起算，第一筆為 001 """
    assert next_ccno(None, "20260702") == "20260702001"

def test_next_ccno_no_prior_record_empty_string():
    """ 空字串也應視同無資料（防呆） """
    assert next_ccno("", "20260702") == "20260702001"

def test_next_ccno_increment():
    """ 001 -> 002 """
    assert next_ccno("20260702001", "20260702") == "20260702002"

def test_next_ccno_increment_with_padding():
    """ 099 -> 100（補零格式正確） """
    assert next_ccno("20260702099", "20260702") == "20260702100"

def test_next_ccno_overflow_raises():
    """
    999 溢位：舊系統 GetNextNo 沒有處理這個邊界（續號會變 4 碼破壞 11 碼格式），
    Python 版刻意提前擋下視為錯誤，屬於比舊系統更嚴謹的防呆改良。
    """
    with pytest.raises(ValueError) as exc:
        next_ccno("20260702999", "20260702")
    assert "溢位" in str(exc.value) or "999" in str(exc.value)

def test_next_ccno_format_length():
    """ 產出的 ccno 一律 11 碼（yyyyMMdd + 3 碼流水號） """
    ccno = next_ccno("20260702012", "20260702")
    assert len(ccno) == 11
    assert ccno == "20260702013"


# ── ControlModify（隔離修改 ModifyControl 移植）─────────────────────────────
# 對應 legacy/ModifyControl.aspx.cs Proc新增隔離廠區項目()：與 ControlCreate 共用同一套
# 時間/項目驗證規則（見 schemas/control_schema.py ControlModify 繼承 ControlCreate 的說明）。

def test_control_modify_inherits_time_validation():
    """ ControlModify 繼承 ControlCreate 的驗證：超過 1 小時一樣要擋 """
    now = datetime.now()
    with pytest.raises(ValidationError) as exc:
        ControlModify(
            orgccid=123, plantid=1, mdfdesc="修改測試",
            stime=now + timedelta(minutes=5),
            etime=now + timedelta(hours=3),
            items=[ControlItemBase(plantno="K1", item="pH", sourceid="2")]
        )
    assert "隔離廠區項目時間不得超過1小時" in str(exc.value)


def test_control_modify_success_carries_orgccid():
    """ 合法的修改單資料應通過驗證，且帶有 orgccid 指向原單 """
    now = datetime.now()
    modify = ControlModify(
        orgccid=456, plantid=1, mdfdesc="修改隔離時間",
        stime=now + timedelta(minutes=5),
        etime=now + timedelta(minutes=55),
        items=[ControlItemBase(plantno="K1", item="COD", sourceid="1")]
    )
    assert modify.orgccid == 456


def test_build_modify_record_fields_shape():
    """
    純函式驗證修改單資料形狀（不依賴 DB）：
    ttypeid 必須是 Ttype.修改隔離區間(2)、orgccid 必須帶入原單 ccid、
    fstatusid 初始為待簽核(0) —— 這個形狀要跟 flow_service.process_sign 核准時
    的判斷式（ttypeid==2 and orgccid）相容，見 services/control_service.py 註解。
    """
    now = datetime.now()
    modify = ControlModify(
        orgccid=789, plantid=2, mdfdesc="修改隔離時間",
        stime=now + timedelta(minutes=5),
        etime=now + timedelta(minutes=55),
        items=[ControlItemBase(plantno="K9", item="VOC", sourceid="1")]
    )
    fields = build_modify_record_fields(modify, "20260702003", "A001", "王小明")
    assert fields["ttypeid"] == int(Ttype.修改隔離區間) == 2
    assert fields["orgccid"] == 789
    assert fields["fstatusid"] == int(FlowStatus.待簽核) == 0
    assert fields["ccno"] == "20260702003"
    assert fields["cempno"] == "A001"
    assert fields["cempname"] == "王小明"


# ── ControlTimeUpdate（隔離時間修改 ControlTime 移植）───────────────────────
# 對應 legacy/ControlTime.aspx.cs Proc修改隔離廠區項目() + dbVOC.Update隔離廠區項目()：
# 直接改主表、不走簽核，唯一的合法性規則是「新結束時間不可小於原結束時間」（只能延長/持平）。
# ⚠️ 依 legacy 確認這裡刻意不再套用「隔離上限 1 小時」規則，見 schemas/control_schema.py 註解。

def test_control_time_update_reject_shorten():
    """ 新結束時間小於原結束時間應該被擋（不可縮短） """
    now = datetime.now()
    with pytest.raises(ValidationError) as exc:
        ControlTimeUpdate(
            ccid=1, ccno="20260702001",
            orig_etime=now + timedelta(hours=1),
            etime=now + timedelta(minutes=30),  # 比原本還早，違規
        )
    assert "結束時間需大於" in str(exc.value)


def test_control_time_update_allow_extend():
    """ 新結束時間大於原結束時間，屬於合法的延長操作 """
    now = datetime.now()
    orig = now + timedelta(hours=1)
    update = ControlTimeUpdate(
        ccid=1, ccno="20260702001",
        orig_etime=orig,
        etime=orig + timedelta(minutes=30),
    )
    assert update.etime > update.orig_etime


def test_control_time_update_allow_equal():
    """ 新結束時間等於原結束時間（持平）也應該放行，不強制一定要延長 """
    now = datetime.now()
    orig = now + timedelta(hours=1)
    update = ControlTimeUpdate(
        ccid=1, ccno="20260702001",
        orig_etime=orig,
        etime=orig,
    )
    assert update.etime == update.orig_etime


def test_control_time_update_no_one_hour_cap():
    """
    刻意驗證 ControlTime 不套用「隔離上限 1 小時」規則（與 ControlCreate/ControlModify 不同）：
    新結束時間即使距離現在超過 1 小時也應該通過（legacy Update隔離廠區項目() 沒有這條限制）。
    """
    now = datetime.now()
    orig = now + timedelta(minutes=30)
    update = ControlTimeUpdate(
        ccid=1, ccno="20260702001",
        orig_etime=orig,
        etime=now + timedelta(hours=5),  # 遠超過 1 小時，仍應通過
    )
    assert update.etime == now + timedelta(hours=5)
