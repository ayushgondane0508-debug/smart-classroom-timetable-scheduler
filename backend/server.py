import asyncio
import logging
import os
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from emailer import email_configured, schedule_html, send_email
from scheduler import generate_schedule, validate_entries
from storage import get_object, init_storage, put_object

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="Smart Classroom Scheduler API")
api = APIRouter(prefix="/api")
JWT_ALGORITHM = "HS256"


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class ContactMessageCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    message: str = Field(min_length=10, max_length=2000)


class EntityInput(BaseModel):
    model_config = ConfigDict(extra="allow")


class CredentialsInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


MAX_PHOTO_BYTES = 3 * 1024 * 1024
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
LOCKOUT_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def now():
    return datetime.now(timezone.utc).isoformat()


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())


def make_token(user_id, email, role):
    return jwt.encode({"sub": user_id, "email": email, "role": role, "exp": datetime.now(timezone.utc) + timedelta(hours=8), "type": "access"}, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def current_user(request: Request):
    token = request.cookies.get("access_token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Session expired")
    return user


async def admin_user(user: dict = Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def teacher_user(user: dict = Depends(current_user)):
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Teacher account required")
    return user


async def check_lockout(identifier):
    record = await db.login_attempts.find_one({"identifier": identifier})
    if record and record.get("count", 0) >= LOCKOUT_ATTEMPTS and record.get("locked_until", "") > now():
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")


async def record_failure(identifier):
    await db.login_attempts.update_one({"identifier": identifier}, {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()}}, upsert=True)


async def seed_admin():
    email = os.environ["ADMIN_EMAIL"].lower()
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "name": "Administrator", "role": "admin", "password_hash": hash_password(os.environ["ADMIN_PASSWORD"]), "created_at": now()})
    elif not verify_password(os.environ["ADMIN_PASSWORD"], existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(os.environ["ADMIN_PASSWORD"])}})


@app.on_event("startup")
async def startup():
    await seed_admin()
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    for collection in ["teachers", "subjects", "divisions", "classrooms", "laboratories", "files", "notifications"]:
        await db[collection].create_index("id", unique=True)
    try:
        await asyncio.to_thread(init_storage)
    except Exception as exc:
        logging.getLogger("storage").error("Storage init failed: %s", exc)


@api.get("/")
async def root():
    return {"message": "Smart Classroom Scheduler API"}


def public_user(user):
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"], "teacher_id": user.get("teacher_id")}


@api.post("/auth/login")
async def login(input: LoginInput, request: Request, response: Response):
    identifier = f"{request.client.host if request.client else 'unknown'}:{input.email.lower()}"
    await check_lockout(identifier)
    user = await db.users.find_one({"email": input.email.lower()})
    if not user or not verify_password(input.password, user["password_hash"]):
        await record_failure(identifier)
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    await db.login_attempts.delete_one({"identifier": identifier})
    response.set_cookie("access_token", make_token(user["id"], user["email"], user["role"]), httponly=True, secure=True, samesite="none", max_age=28800, path="/")
    return public_user(user)


@api.post("/auth/logout")
async def logout(response: Response, _: dict = Depends(current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return public_user(user)


@api.post("/auth/change-password")
async def change_password(input: ChangePasswordInput, user: dict = Depends(current_user)):
    record = await db.users.find_one({"id": user["id"]})
    if not verify_password(input.current_password, record["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(input.new_password), "updated_at": now()}})
    return {"ok": True}


@api.put("/teachers/{teacher_id}/credentials")
async def set_teacher_credentials(teacher_id: str, input: CredentialsInput, _: dict = Depends(admin_user)):
    teacher = await db.teachers.find_one({"id": teacher_id}, {"_id": 0})
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    email = input.email.lower()
    clash = await db.users.find_one({"email": email, "teacher_id": {"$ne": teacher_id}})
    if clash:
        raise HTTPException(status_code=409, detail="That email is already used by another account")
    existing = await db.users.find_one({"teacher_id": teacher_id})
    if existing:
        await db.users.update_one({"teacher_id": teacher_id}, {"$set": {"email": email, "name": teacher["name"], "password_hash": hash_password(input.password), "updated_at": now()}})
    else:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "name": teacher["name"], "role": "teacher", "teacher_id": teacher_id, "password_hash": hash_password(input.password), "created_at": now()})
    await db.teachers.update_one({"id": teacher_id}, {"$set": {"email": email, "has_login": True, "updated_at": now()}})
    return {"ok": True, "email": email, "login_url": f"{os.environ['FRONTEND_URL']}/teacher-login"}


@api.delete("/teachers/{teacher_id}/credentials")
async def revoke_teacher_credentials(teacher_id: str, _: dict = Depends(admin_user)):
    await db.users.delete_many({"teacher_id": teacher_id, "role": "teacher"})
    await db.teachers.update_one({"id": teacher_id}, {"$set": {"has_login": False, "updated_at": now()}})
    return {"ok": True}


@api.post("/teachers/{teacher_id}/photo")
async def upload_teacher_photo(teacher_id: str, file: UploadFile = File(...), _: dict = Depends(admin_user)):
    teacher = await db.teachers.find_one({"id": teacher_id}, {"_id": 0})
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    data = await file.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="Photo must be smaller than 3 MB")
    record = await store_file(data, file.filename, file.content_type, kind="photo", folder=f"photos/{teacher_id}", public=True, title=f"{teacher['name']} photo")
    await db.teachers.update_one({"id": teacher_id}, {"$set": {"photo_file_id": record["id"], "updated_at": now()}})
    return {"ok": True, "photo_file_id": record["id"]}


async def store_file(data, filename, content_type, kind, folder, public=False, title="", category="", meta=None):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    file_id = str(uuid.uuid4())
    result = await put_object(f"{folder}/{file_id}.{ext}", data, content_type or "application/octet-stream")
    record = {"id": file_id, "kind": kind, "public": public, "title": title or filename, "category": category, "original_filename": filename, "content_type": content_type or "application/octet-stream", "size": result.get("size", len(data)), "storage_path": result["path"], "is_deleted": False, "created_at": now(), **(meta or {})}
    await db.files.insert_one(record)
    record.pop("_id", None)
    return record


@api.get("/files/{file_id}")
async def download_file(file_id: str, request: Request):
    record = await db.files.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    if not record.get("public"):
        await current_user(request)
    try:
        data, content_type = await get_object(record["storage_path"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Storage is temporarily unavailable") from exc
    disposition = "inline" if record.get("public") or record["content_type"].startswith("image/") else "attachment"
    return Response(content=data, media_type=record.get("content_type") or content_type, headers={"Content-Disposition": f'{disposition}; filename="{record["original_filename"]}"'})


@api.get("/documents")
async def list_documents(_: dict = Depends(current_user)):
    return await db.files.find({"kind": "document", "is_deleted": False}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/documents")
async def upload_document(file: UploadFile = File(...), title: str = Form(""), category: str = Form("General"), _: dict = Depends(admin_user)):
    data = await file.read()
    if len(data) > MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=400, detail="Documents must be smaller than 15 MB")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    try:
        return await store_file(data, file.filename, file.content_type, kind="document", folder="documents", title=title.strip(), category=category.strip() or "General")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not reach cloud storage. Please retry.") from exc


@api.delete("/documents/{file_id}")
async def delete_document(file_id: str, _: dict = Depends(admin_user)):
    result = await db.files.update_one({"id": file_id, "kind": "document"}, {"$set": {"is_deleted": True, "deleted_at": now()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"ok": True}


@api.get("/exports")
async def list_exports(_: dict = Depends(admin_user)):
    return await db.files.find({"kind": "export", "is_deleted": False}, {"_id": 0}).sort("created_at", -1).to_list(200)


async def archive_export(timetable, data, ext, content_type):
    try:
        await store_file(data, f"{timetable.get('name', 'timetable')}.{ext}", content_type, kind="export", folder=f"exports/{timetable['id']}", title=f"{timetable.get('name', 'Timetable')} ({ext.upper()})", meta={"timetable_id": timetable["id"], "timetable_name": timetable.get("name", ""), "score": timetable.get("score", 0)})
    except Exception as exc:
        logging.getLogger("storage").error("Export archive failed: %s", exc)


async def notify_teachers(timetable_id):
    timetable = await db.timetables.find_one({"id": timetable_id}, {"_id": 0})
    if not timetable:
        return []
    results = []
    for teacher in await list_entities("teachers"):
        entries = [entry for entry in timetable.get("entries", []) if entry.get("teacher_id") == teacher["id"]]
        if not entries or not teacher.get("email"):
            continue
        subject = f"New timetable published: {timetable.get('name', 'Weekly timetable')}"
        outcome = await send_email(teacher["email"], subject, schedule_html(teacher, timetable, entries, f"{os.environ['FRONTEND_URL']}/teacher/{teacher['id']}"))
        record = {"id": str(uuid.uuid4()), "timetable_id": timetable_id, "timetable_name": timetable.get("name", ""), "teacher_id": teacher["id"], "teacher_name": teacher["name"], "email": teacher["email"], "subject": subject, "sessions": len(entries), **outcome, "created_at": now()}
        await db.notifications.insert_one(record)
        record.pop("_id", None)
        results.append(record)
    return results


@api.get("/notifications")
async def list_notifications(_: dict = Depends(admin_user)):
    items = await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"configured": email_configured(), "sender": os.environ.get("SENDER_EMAIL", ""), "items": items}


@api.post("/timetable/{timetable_id}/notify")
async def notify_now(timetable_id: str, _: dict = Depends(admin_user)):
    results = await notify_teachers(timetable_id)
    return {"ok": True, "configured": email_configured(), "count": len(results), "items": results}


@api.post("/contact")
async def contact(input: ContactMessageCreate):
    item = {"id": str(uuid.uuid4()), **input.model_dump(), "created_at": now()}
    await db.contact_messages.insert_one(item)
    item.pop("_id", None)
    return item


async def list_entities(collection):
    return await db[collection].find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)


def entity_router(name):
    @api.get(f"/{name}")
    async def get_all(_: dict = Depends(admin_user)):
        return await list_entities(name)

    @api.post(f"/{name}")
    async def create(input: EntityInput, _: dict = Depends(admin_user)):
        item = {"id": str(uuid.uuid4()), **input.model_dump(), "created_at": now(), "updated_at": now()}
        await db[name].insert_one(item)
        item.pop("_id", None)
        return item

    @api.put(f"/{name}/{{item_id}}")
    async def update(item_id: str, input: EntityInput, _: dict = Depends(admin_user)):
        item = {**input.model_dump(), "updated_at": now()}
        result = await db[name].update_one({"id": item_id}, {"$set": item})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"id": item_id, **item}

    @api.delete(f"/{name}/{{item_id}}")
    async def delete(item_id: str, _: dict = Depends(admin_user)):
        result = await db[name].delete_one({"id": item_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"ok": True}


for entity in ["teachers", "subjects", "divisions", "classrooms", "laboratories"]:
    entity_router(entity)


DEFAULT_CONFIG = {"id": "default", "college_name": "Smart Classroom College", "academic_year": "2026", "department_mode": "single", "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "periods_per_day": 6, "period_duration": 55, "start_time": "09:00", "break_after_period": 3, "lunch_after_period": 5}


@api.get("/config")
async def get_config(_: dict = Depends(admin_user)):
    return await read_config()


async def read_config():
    return await db.settings.find_one({"id": "default"}, {"_id": 0}) or DEFAULT_CONFIG


@api.put("/config")
async def update_config(input: EntityInput, _: dict = Depends(admin_user)):
    item = {"id": "default", **input.model_dump(), "updated_at": now()}
    await db.settings.replace_one({"id": "default"}, item, upsert=True)
    return item


@api.post("/demo/load")
async def load_demo(_: dict = Depends(admin_user)):
    await db.teachers.delete_many({"demo": True}); await db.subjects.delete_many({"demo": True}); await db.divisions.delete_many({"demo": True}); await db.classrooms.delete_many({"demo": True}); await db.laboratories.delete_many({"demo": True})
    teachers = [{"id": f"demo-t-{i}", "name": name, "employee_id": f"FAC-{i:03}", "department": "Computer Engineering", "maximum_lectures_per_day": 4, "maximum_lectures_per_week": 20, "availability": [], "demo": True, "created_at": now()} for i, name in enumerate(["Aarav Shah", "Meera Joshi", "Kabir Patil", "Nisha Rao", "Rohan Kulkarni", "Isha Deshmukh"], 1)]
    subjects = [{"id": f"demo-s-{i}", "name": name, "code": code, "department": "Computer Engineering", "semester": 3, "type": kind, "lectures_per_week": count, "duration": 1, "requires_lab": lab, "teacher_id": f"demo-t-{((i - 1) % 6) + 1}", "demo": True, "created_at": now()} for i, (name, code, kind, count, lab) in enumerate([("Data Structures", "CS201", "Theory", 3, False), ("Operating Systems", "CS202", "Theory", 3, False), ("Database Systems", "CS203", "Theory", 3, False), ("Computer Networks", "CS204", "Theory", 2, False), ("DS Lab", "CS205L", "Practical", 2, True), ("DBMS Lab", "CS206L", "Practical", 2, True)], 1)]
    divisions = [{"id": "demo-d-1", "name": "CSE-A", "department": "Computer Engineering", "semester": 3, "student_count": 42, "subjects": [s["id"] for s in subjects], "demo": True, "created_at": now()}, {"id": "demo-d-2", "name": "CSE-B", "department": "Computer Engineering", "semester": 3, "student_count": 36, "subjects": [s["id"] for s in subjects], "demo": True, "created_at": now()}]
    classrooms = [{"id": f"demo-r-{i}", "room_number": f"20{i}", "building": "A Block", "capacity": 60, "room_type": "Classroom", "available_slots": [], "demo": True, "created_at": now()} for i in range(1, 5)]
    labs = [{"id": "demo-l-1", "lab_name": "Systems Lab", "lab_number": "LAB-1", "lab_type": "Computer", "capacity": 50, "room_type": "Laboratory", "available_slots": [], "demo": True, "created_at": now()}, {"id": "demo-l-2", "lab_name": "Database Lab", "lab_number": "LAB-2", "lab_type": "Computer", "capacity": 50, "room_type": "Laboratory", "available_slots": [], "demo": True, "created_at": now()}]
    for collection, values in [("teachers", teachers), ("subjects", subjects), ("divisions", divisions), ("classrooms", classrooms), ("laboratories", labs)]:
        await db[collection].insert_many(values)
    await db.settings.replace_one({"id": "default"}, DEFAULT_CONFIG, upsert=True)
    return {"ok": True, "counts": {"teachers": len(teachers), "subjects": len(subjects), "divisions": len(divisions), "classrooms": len(classrooms), "laboratories": len(labs)}}


@api.delete("/demo/reset")
async def reset_demo(_: dict = Depends(admin_user)):
    for collection in ["teachers", "subjects", "divisions", "classrooms", "laboratories", "timetables"]:
        await db[collection].delete_many({"demo": True})
    return {"ok": True}


@api.get("/dashboard/stats")
async def dashboard_stats(_: dict = Depends(admin_user)):
    config = await read_config()
    counts = {name: await db[name].count_documents({}) for name in ["teachers", "subjects", "divisions", "classrooms", "laboratories"]}
    timetable_count = await db.timetables.count_documents({})
    current = await db.timetables.find_one({"active": True}, {"_id": 0})
    return {**counts, "weekly_periods": len(config.get("working_days", [])) * int(config.get("periods_per_day", 0)), "generated_timetables": timetable_count, "current_conflicts": len(validate_entries(current.get("entries", []))) if current else 0, "faculty_workload": [], "room_utilization": [], "subject_distribution": []}


@api.post("/timetable/generate")
async def generate(background: BackgroundTasks, _: dict = Depends(admin_user)):
    data = {name: await list_entities(name) for name in ["teachers", "subjects", "divisions", "classrooms", "laboratories"]}
    data["config"] = await read_config()
    result = generate_schedule(teachers=data["teachers"], subjects=data["subjects"], divisions=data["divisions"], rooms=data["classrooms"], labs=data["laboratories"], config=data["config"])
    if result["failures"]:
        return {"ok": False, "message": "Unable to generate a completely conflict-free timetable.", "failures": result["failures"], "score": result["score"], "hard_constraint_violations": result["hard_constraint_violations"]}
    timetable = {"id": str(uuid.uuid4()), "name": f"{data['config'].get('college_name', 'College')} — {data['config'].get('academic_year', 'Current')}", "entries": result["entries"], "slots": result["slots"], "score": result["score"], "hard_constraint_violations": 0, "active": True, "created_at": now(), "updated_at": now()}
    await db.timetables.update_many({}, {"$set": {"active": False}})
    await db.timetables.insert_one(timetable)
    timetable.pop("_id", None)
    background.add_task(notify_teachers, timetable["id"])
    return {"ok": True, "timetable": timetable}


@api.get("/timetable")
async def get_timetable(_: dict = Depends(admin_user)):
    return await db.timetables.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api.put("/timetable/{timetable_id}")
async def update_timetable(timetable_id: str, input: EntityInput, _: dict = Depends(admin_user)):
    payload = input.model_dump(); conflicts = validate_entries(payload.get("entries", []))
    if conflicts:
        raise HTTPException(status_code=409, detail={"message": "Conflict detected", "conflicts": conflicts})
    payload["updated_at"] = now()
    result = await db.timetables.update_one({"id": timetable_id}, {"$set": payload})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return {"id": timetable_id, **payload}


@api.get("/analytics")
async def analytics(_: dict = Depends(admin_user)):
    timetable = await db.timetables.find_one({"active": True}, {"_id": 0})
    entries = timetable.get("entries", []) if timetable else []
    return {"faculty_workload": [{"name": key, "lectures": value} for key, value in Counter(e["teacher_name"] for e in entries).items()], "room_utilization": [{"name": key, "sessions": value} for key, value in Counter(e["room_name"] for e in entries).items()], "subject_distribution": [{"name": key, "sessions": value} for key, value in Counter(e["subject_name"] for e in entries).items()], "daily_density": [{"name": key, "sessions": value} for key, value in Counter(e["day"] for e in entries).items()], "quality_score": timetable.get("score", 0) if timetable else 0}


DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@api.post("/timetable/{timetable_id}/activate")
async def activate_timetable(timetable_id: str, background: BackgroundTasks, _: dict = Depends(admin_user)):
    result = await db.timetables.update_one({"id": timetable_id}, {"$set": {"active": True, "updated_at": now()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Timetable not found")
    await db.timetables.update_many({"id": {"$ne": timetable_id}}, {"$set": {"active": False}})
    background.add_task(notify_teachers, timetable_id)
    return {"ok": True}


async def teacher_schedule(teacher_id):
    teacher = await db.teachers.find_one({"id": teacher_id}, {"_id": 0})
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    timetable = await db.timetables.find_one({"active": True}, {"_id": 0}) or {}
    entries = [entry for entry in timetable.get("entries", []) if entry.get("teacher_id") == teacher_id]
    config = await read_config()
    return {"teacher": {"id": teacher["id"], "name": teacher["name"], "department": teacher.get("department", ""), "departments": teacher.get("departments", []), "employee_id": teacher.get("employee_id", ""), "photo_file_id": teacher.get("photo_file_id")}, "timetable_name": timetable.get("name", ""), "entries": entries, "working_days": config.get("working_days", []), "periods_per_day": int(config.get("periods_per_day", 6))}


@api.get("/public/teacher/{teacher_id}")
async def public_teacher_schedule(teacher_id: str):
    return await teacher_schedule(teacher_id)


@api.get("/me/schedule")
async def my_schedule(user: dict = Depends(teacher_user)):
    return await teacher_schedule(user["teacher_id"])


def timetable_grid(timetable):
    entries = timetable.get("entries", [])
    days = sorted({entry["day"] for entry in entries}, key=lambda day: DAY_ORDER.index(day) if day in DAY_ORDER else 99)
    periods = sorted({entry["period"] for entry in entries})
    divisions = sorted({entry["division_name"] for entry in entries})
    def cell(division, day, period):
        return next((entry for entry in entries if entry["division_name"] == division and entry["day"] == day and entry["period"] == period), None)
    return days, periods, divisions, cell


@api.get("/timetable/{timetable_id}/export/excel")
async def export_timetable_excel(timetable_id: str, background: BackgroundTasks, _: dict = Depends(admin_user)):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    timetable = await db.timetables.find_one({"id": timetable_id}, {"_id": 0})
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    days, periods, divisions, cell = timetable_grid(timetable)
    workbook = Workbook()
    workbook.remove(workbook.active)
    header_fill = PatternFill("solid", fgColor="2563EB")
    header_font = Font(color="FFFFFF", bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")
    for division in divisions:
        sheet = workbook.create_sheet((division or "Timetable")[:31])
        sheet.append([f"{timetable.get('name', 'Weekly Timetable')} — Division {division}"])
        sheet.append(["Period", *days])
        for period in periods:
            row = [f"P{period}"]
            for day in days:
                entry = cell(division, day, period)
                row.append(f"{entry.get('subject_code') or entry['subject_name']}\n{entry['teacher_name']}\n{entry['room_name']}" if entry else "Free")
            sheet.append(row)
        for item in sheet[2]:
            item.fill = header_fill
            item.font = header_font
        for row in sheet.iter_rows(min_row=3):
            for item in row:
                item.alignment = wrap
        sheet.column_dimensions["A"].width = 10
        for index in range(len(days)):
            sheet.column_dimensions[chr(66 + index)].width = 24
    buffer = BytesIO()
    workbook.save(buffer)
    background.add_task(archive_export, timetable, buffer.getvalue(), "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="timetable-{timetable_id}.xlsx"'})


@api.get("/timetable/{timetable_id}/export/pdf")
async def export_timetable_pdf(timetable_id: str, background: BackgroundTasks, _: dict = Depends(admin_user)):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    timetable = await db.timetables.find_one({"id": timetable_id}, {"_id": 0})
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    days, periods, divisions, cell = timetable_grid(timetable)
    styles = getSampleStyleSheet()
    cell_style = styles["Normal"]
    cell_style.fontSize = 7
    cell_style.leading = 9
    story = [Paragraph(timetable.get("name", "Weekly Timetable"), styles["Title"]), Paragraph(f"Quality score {timetable.get('score', 0)}/100 · Generated {str(timetable.get('created_at', ''))[:10]}", styles["Normal"]), Spacer(1, 14)]
    for division in divisions:
        story.append(Paragraph(f"Division {division}", styles["Heading2"]))
        data = [["Period", *days]]
        for period in periods:
            row = [f"P{period}"]
            for day in days:
                entry = cell(division, day, period)
                row.append(Paragraph(f"<b>{entry.get('subject_code') or entry['subject_name']}</b><br/>{entry['teacher_name']}<br/>{entry['room_name']}", cell_style) if entry else "—")
            data.append(row)
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")])]))
        story.extend([table, Spacer(1, 18)])
    buffer = BytesIO()
    SimpleDocTemplate(buffer, pagesize=landscape(A4), title=timetable.get("name", "Timetable")).build(story)
    background.add_task(archive_export, timetable, buffer.getvalue(), "pdf", "application/pdf")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="timetable-{timetable_id}.pdf"'})


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[os.environ["FRONTEND_URL"]], allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown():
    client.close()