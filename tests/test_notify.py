from fastapi.testclient import TestClient
from fastapi import FastAPI, BackgroundTasks
from services.notify_service import add_notification_task
import pytest

app = FastAPI()

@app.post("/notify")
def trigger_notify(background_tasks: BackgroundTasks):
    add_notification_task(background_tasks, "Test Subj", "Test Message", ["test@example.com"])
    return {"status": "ok"}

client = TestClient(app)

def test_trigger_notify():
    # This just ensures we can enqueue the background tasks without crashing
    response = client.post("/notify")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
