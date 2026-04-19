import sys
import os
import pytest
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from pydantic import ValidationError
from main import app
from schemas.control_schema import ControlCreate, ControlItemBase

client = TestClient(app)

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
    """ 測試 EditControl 防呆：預設隔離最長只允許申請一小時 """
    now = datetime.now()
    with pytest.raises(ValidationError) as exc:
        ControlCreate(
            plantid=1, mdfdesc="測試",
            stime=now + timedelta(hours=1),
            etime=now + timedelta(hours=3), # 2 小時 > 1 小時 (3600 秒)
            items=[ControlItemBase(plantno="K1", item="VOC", sourceid="1")]
        )
    assert "隔離廠區項目時間不得超過1小時" in str(exc.value)

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
