from fastapi.testclient import TestClient
from main import app

# 建立 FastAPI 的測試客戶端
client = TestClient(app)

def test_read_root():
    """
    單位測試：驗證根目錄 (/) API 是否正常運作，並且正確回傳包含系統名稱的 HTML。
    """
    response = client.get("/")
    # 確保 HTTP 狀態碼為 200 OK
    assert response.status_code == 200
    # 確保回傳的 HTML 中包含關鍵字，驗證渲染邏輯沒壞
    assert "VOC 系統 Python 版 - 建置中" in response.text
