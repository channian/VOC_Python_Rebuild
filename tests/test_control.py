import sys
import os
import pytest
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError
from schemas.control_schema import ControlCreate, ControlItemBase
from services.control_service import next_ccno

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
