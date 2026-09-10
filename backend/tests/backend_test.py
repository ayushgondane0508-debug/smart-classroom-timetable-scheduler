"""Backend tests for Smart Classroom & Timetable Scheduler (iteration 2)."""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@smartclassroom.com"
ADMIN_PASSWORD = "SmartClassroom2026!"
TEACHER_EMAIL = "isha.teacher@smartclassroom.com"
TEACHER_PASSWORD = "Teacher2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def teacher_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": TEACHER_EMAIL, "password": TEACHER_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def active_timetable_id(admin_session):
    r = admin_session.get(f"{API}/timetable", timeout=15)
    assert r.status_code == 200
    items = r.json()
    active = next((t for t in items if t.get("active")), None)
    assert active, "No active timetable found in demo data"
    return active["id"]


# ---------- auth ----------
def test_admin_me(admin_session):
    r = admin_session.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "admin"
    assert data.get("teacher_id") is None


def test_teacher_me_and_schedule(teacher_session):
    r = teacher_session.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "teacher"
    assert data["teacher_id"] == "demo-t-6"

    r = teacher_session.get(f"{API}/me/schedule", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert "teacher" in body and "entries" in body


def test_teacher_forbidden_from_admin_endpoints(teacher_session):
    r = teacher_session.get(f"{API}/teachers", timeout=15)
    assert r.status_code == 403


def test_change_password_flow():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": TEACHER_EMAIL, "password": TEACHER_PASSWORD}, timeout=15)
    assert r.status_code == 200

    r = s.post(f"{API}/auth/change-password",
               json={"current_password": "WrongPass!", "new_password": "TempPass2026!"}, timeout=15)
    assert r.status_code == 400

    r = s.post(f"{API}/auth/change-password",
               json={"current_password": TEACHER_PASSWORD, "new_password": "TempPass2026!"}, timeout=15)
    assert r.status_code == 200

    s2 = requests.Session()
    r = s2.post(f"{API}/auth/login", json={"email": TEACHER_EMAIL, "password": "TempPass2026!"}, timeout=15)
    assert r.status_code == 200

    r = s2.post(f"{API}/auth/change-password",
                json={"current_password": "TempPass2026!", "new_password": TEACHER_PASSWORD}, timeout=15)
    assert r.status_code == 200

    s3 = requests.Session()
    r = s3.post(f"{API}/auth/login", json={"email": TEACHER_EMAIL, "password": TEACHER_PASSWORD}, timeout=15)
    assert r.status_code == 200, "Failed to restore original teacher password!"


# ---------- teacher credentials ----------
def test_teacher_credentials_create_and_revoke(admin_session):
    payload = {"email": "demo.t5@smartclassroom.com", "password": "Demo5Pass!"}
    r = admin_session.put(f"{API}/teachers/demo-t-5/credentials", json=payload, timeout=15)
    assert r.status_code == 200, r.text

    r = admin_session.get(f"{API}/teachers", timeout=15)
    teacher = next(t for t in r.json() if t["id"] == "demo-t-5")
    assert teacher.get("has_login") is True
    assert teacher.get("email") == payload["email"]

    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": payload["email"], "password": payload["password"]}, timeout=15)
    assert r.status_code == 200

    r = admin_session.delete(f"{API}/teachers/demo-t-5/credentials", timeout=15)
    assert r.status_code == 200

    r = admin_session.get(f"{API}/teachers", timeout=15)
    teacher = next(t for t in r.json() if t["id"] == "demo-t-5")
    assert teacher.get("has_login") is False

    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": payload["email"], "password": payload["password"]}, timeout=15)
    assert r.status_code == 401


# ---------- photo upload ----------
PNG_BYTES = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "890000000A49444154789C63000100000500010D0A2DB40000000049454E44AE426082"
)


def test_photo_upload_public_access(admin_session):
    files = {"file": ("pixel.png", PNG_BYTES, "image/png")}
    r = admin_session.post(f"{API}/teachers/demo-t-6/photo", files=files, timeout=20)
    assert r.status_code == 200, r.text
    photo_id = r.json().get("photo_file_id")
    assert photo_id

    r = requests.get(f"{API}/files/{photo_id}", timeout=15)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")

    files = {"file": ("bad.txt", b"not an image", "text/plain")}
    r = admin_session.post(f"{API}/teachers/demo-t-6/photo", files=files, timeout=15)
    assert r.status_code == 400


# ---------- documents ----------
def test_documents_crud_and_access(admin_session):
    files = {"file": ("doc.txt", b"hello world", "text/plain")}
    data = {"title": f"TEST_{uuid.uuid4().hex[:6]}", "category": "policy"}
    r = admin_session.post(f"{API}/documents", files=files, data=data, timeout=20)
    assert r.status_code == 200, r.text
    file_id = r.json()["id"]

    r = admin_session.get(f"{API}/documents", timeout=15)
    assert any(d["id"] == file_id for d in r.json())

    r = requests.get(f"{API}/files/{file_id}", timeout=15)
    assert r.status_code == 401

    r = admin_session.get(f"{API}/files/{file_id}", timeout=15)
    assert r.status_code == 200
    assert r.content == b"hello world"

    r = admin_session.delete(f"{API}/documents/{file_id}", timeout=15)
    assert r.status_code == 200

    r = admin_session.get(f"{API}/documents", timeout=15)
    assert not any(d["id"] == file_id for d in r.json())


# ---------- exports ----------
def test_exports_pdf_excel_archived(admin_session, active_timetable_id):
    r = admin_session.get(f"{API}/timetable/{active_timetable_id}/export/pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")

    r = admin_session.get(f"{API}/timetable/{active_timetable_id}/export/excel", timeout=30)
    assert r.status_code == 200

    time.sleep(3.5)
    r = admin_session.get(f"{API}/exports", timeout=15)
    assert r.status_code == 200
    assert any(it.get("kind") == "export" for it in r.json())


# ---------- notify ----------
def test_notify_teachers_skipped(admin_session, active_timetable_id):
    r = admin_session.post(f"{API}/timetable/{active_timetable_id}/notify", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("configured") is False
    assert body.get("count", 0) >= 1
    for item in body.get("items", []):
        assert item.get("status") == "skipped"

    r = admin_session.get(f"{API}/notifications", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("configured") is False
    assert isinstance(body.get("items"), list)


# ---------- department mode ----------
def test_department_mode_persistence_and_generate(admin_session):
    r = admin_session.get(f"{API}/config", timeout=15)
    assert r.status_code == 200
    original = r.json()

    r = admin_session.put(f"{API}/config", json={**original, "department_mode": "multi"}, timeout=15)
    assert r.status_code == 200
    r = admin_session.get(f"{API}/config", timeout=15)
    assert r.json().get("department_mode") == "multi"

    r = admin_session.post(f"{API}/timetable/generate", timeout=60)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    r = admin_session.put(f"{API}/config", json={**original, "department_mode": "single"}, timeout=15)
    assert r.status_code == 200


# ---------- brute force lockout ----------
def test_brute_force_lockout():
    email = f"lock.{uuid.uuid4().hex[:6]}@x.com"
    s = requests.Session()
    codes = []
    for _ in range(6):
        r = s.post(f"{API}/auth/login", json={"email": email, "password": "wrongpass"}, timeout=15)
        codes.append(r.status_code)
    assert codes[-1] == 429, f"Expected final 429, got {codes}"
