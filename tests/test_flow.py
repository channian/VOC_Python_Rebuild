from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_fetch_todos():
    response = client.get("/flow/todos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
