import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_acl_list_api():
    """ 測試 取得隔離權限名單 API 是否正常運作 """
    response = client.get("/acl/list")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # 根據我們 acl_service 埋放的 Mock 資料，至少會回傳 2 筆
    assert len(data) >= 2
    assert data[0]["plantno"] == "K1"
    assert data[1]["empno"] == "admin"
    
def test_acl_create_fail_without_body():
    """ 測試建立端點的防呆限制機制 """
    response = client.post("/acl/create")
    # 因為沒有傳遞 JSON Body，應該要報 422 錯誤
    assert response.status_code == 422
