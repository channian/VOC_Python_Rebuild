from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_raingutter():
    response = client.get("/warning/raingutter")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_water_urgent():
    req = {"notify_type": "water_abnormal"}
    response = client.post("/warning/water_urgent", json=req)
    assert response.status_code == 200
    assert "排入背景" in response.json()['message']
