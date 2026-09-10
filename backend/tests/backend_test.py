import os
import uuid

import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def test_api_root_returns_message():
    response = requests.get(f"{BASE_URL}/api/", timeout=15)
    assert response.status_code == 200
    assert response.json().get("message") == "Hello World"


def test_contact_validation_rejects_short_message():
    response = requests.post(
        f"{BASE_URL}/api/contact",
        json={"name": "QA", "email": "qa@example.com", "message": "short"},
        timeout=15,
    )
    assert response.status_code == 422


def test_contact_create_returns_serializable_payload():
    payload = {
        "name": "TEST_" + uuid.uuid4().hex[:8],
        "email": "qa@example.com",
        "message": "A persistence verification message.",
    }
    response = requests.post(f"{BASE_URL}/api/contact", json=payload, timeout=15)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["email"] == payload["email"]
    assert data["message"] == payload["message"]
    assert isinstance(data["id"], str)
    assert isinstance(data["created_at"], str)
    assert "_id" not in data