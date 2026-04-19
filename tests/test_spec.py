import sys
import os
import pytest
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from pydantic import ValidationError
from main import app
from schemas.spec_schema import SpecCreate

client = TestClient(app)

def test_spec_list_api():
    """ 測試 取得規格清單 API 是否正常運作 """
    response = client.get("/spec/list")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2 # From mock data fallback
    assert "tagname" in data[0]

def test_spec_validation_logic_ph_double_sided():
    """ 測試 Pydantic 是否完美攔截單雙邊防呆問題 """
    # 1. 成功案例：pH 為雙邊且邏輯正確
    spec = SpecCreate(
        plantno="K1", item="pH", 
        LAW="6-9", OOS="6.5-8.5", OOC="7-8", alert="7.2-7.8", 
        source_id=1
    )
    assert spec.item == "pH"
    
    # 2. 失敗案例：pH 輸入單邊範圍
    with pytest.raises(ValidationError) as exc_info:
        SpecCreate(
             plantno="K1", item="pH", 
             LAW="6", OOS="6.5", OOC="7", alert="7.2", 
             source_id=1
        )
    assert "pH 必須為雙邊規格" in str(exc_info.value)

def test_spec_validation_logic_voc_single_sided():
    """ 測試一般項目 (VOC) 是否攔下被輸入成雙邊 """
    with pytest.raises(ValidationError) as exc_info:
        SpecCreate(
            plantno="K1", item="VOC", 
            LAW="10-100", OOS="80", OOC="60", alert="50", 
            source_id=1
        )
    assert "VOC 必須為單邊規格" in str(exc_info.value)

def test_spec_validation_logic_hierarchical_limits():
    """ 測試 OOC 是否有防呆「不能寫反或超過 Alert」 """
    with pytest.raises(ValidationError) as exc_info:
        SpecCreate(
            plantno="K1", item="VOC", 
            LAW="100", OOS="80", OOC="40", alert="50",  # OOC(40) 反而比 Alert(50) 小
            source_id=1
        )
    assert "單邊規格中，OOC 上限值必須大於" in str(exc_info.value)
