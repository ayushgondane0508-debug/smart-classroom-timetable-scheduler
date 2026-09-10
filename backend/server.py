import os
import secrets
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from scheduler import generate_schedule, validate_entries

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


def now():
    return datetime.now(timezone.utc).isoformat()


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())


def make_token(user_id, email):
    return jwt.encode({"sub": user_id, "email": email, "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=8), "type": "access"}, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def current_user(request: Request):
    token = request.cookies.get("access_token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        raise HTTPException(status_code=401, detail="Admin login required")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload.get("sub"), "role": "admin"}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Session expired")
        return user
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc


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
    for collection in ["teachers", "subjects", "divisions", "classrooms", "laboratories"]:
        await db[collection].create_index("id", unique=True)


@api.get("/")
async def root():
    return {"message": "Smart Classroom Scheduler API"}


@api.post("/auth/login")
async def login(input: LoginInput, response: Response):
    user = await db.users.find_one({"email": input.email.lower()})
    if not user or not verify_password(input.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    response.set_cookie("access_token", make_token(user["id"], user["email"]), httponly=True, secure=True, samesite="none", max_age=28800, path="/")
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}


@api.post("/auth/logout")
async def logout(response: Response, _: dict = Depends(current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return user


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
    async def get_all(_: dict = Depends(current_user)):
        return await list_entities(name)

    @api.post(f"/{name}")
    async def create(input: EntityInput, _: dict = Depends(current_user)):
        item = {"id": str(uuid.uuid4()), **input.model_dump(), "created_at": now(), "updated_at": now()}
        await db[name].insert_one(item)
        item.pop("_id", None)
        return item

    @api.put(f"/{name}/{{item_id}}")
    async def update(item_id: str, input: EntityInput, _: dict = Depends(current_user)):
        item = {**input.model_dump(), "updated_at": now()}
        result = await db[name].update_one({"id": item_id}, {"$set": item})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"id": item_id, **item}

    @api.delete(f"/{name}/{{item_id}}")
    async def delete(item_id: str, _: dict = Depends(current_user)):
        result = await db[name].delete_one({"id": item_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"ok": True}


for entity in ["teachers", "subjects", "divisions", "classrooms", "laboratories"]:
    entity_router(entity)


DEFAULT_CONFIG = {"id": "default", "college_name": "Smart Classroom College", "academic_year": "2026", "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "periods_per_day": 6, "period_duration": 55, "start_time": "09:00", "break_after_period": 3, "lunch_after_period": 5}


@api.get("/config")
async def get_config(_: dict = Depends(current_user)):
    return await read_config()


async def read_config():
    return await db.settings.find_one({"id": "default"}, {"_id": 0}) or DEFAULT_CONFIG


@api.put("/config")
async def update_config(input: EntityInput, _: dict = Depends(current_user)):
    item = {"id": "default", **input.model_dump(), "updated_at": now()}
    await db.settings.replace_one({"id": "default"}, item, upsert=True)
    return item


@api.post("/demo/load")
async def load_demo(_: dict = Depends(current_user)):
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
async def reset_demo(_: dict = Depends(current_user)):
    for collection in ["teachers", "subjects", "divisions", "classrooms", "laboratories", "timetables"]:
        await db[collection].delete_many({"demo": True})
    return {"ok": True}


@api.get("/dashboard/stats")
async def dashboard_stats(_: dict = Depends(current_user)):
    config = await read_config()
    counts = {name: await db[name].count_documents({}) for name in ["teachers", "subjects", "divisions", "classrooms", "laboratories"]}
    timetable_count = await db.timetables.count_documents({})
    current = await db.timetables.find_one({"active": True}, {"_id": 0})
    return {**counts, "weekly_periods": len(config.get("working_days", [])) * int(config.get("periods_per_day", 0)), "generated_timetables": timetable_count, "current_conflicts": len(validate_entries(current.get("entries", []))) if current else 0, "faculty_workload": [], "room_utilization": [], "subject_distribution": []}


@api.post("/timetable/generate")
async def generate(_: dict = Depends(current_user)):
    data = {name: await list_entities(name) for name in ["teachers", "subjects", "divisions", "classrooms", "laboratories"]}
    data["config"] = await read_config()
    result = generate_schedule(teachers=data["teachers"], subjects=data["subjects"], divisions=data["divisions"], rooms=data["classrooms"], labs=data["laboratories"], config=data["config"])
    if result["failures"]:
        return {"ok": False, "message": "Unable to generate a completely conflict-free timetable.", "failures": result["failures"], "score": result["score"], "hard_constraint_violations": result["hard_constraint_violations"]}
    timetable = {"id": str(uuid.uuid4()), "name": f"{data['config'].get('college_name', 'College')} — {data['config'].get('academic_year', 'Current')}", "entries": result["entries"], "slots": result["slots"], "score": result["score"], "hard_constraint_violations": 0, "active": True, "created_at": now(), "updated_at": now()}
    await db.timetables.update_many({}, {"$set": {"active": False}})
    await db.timetables.insert_one(timetable)
    timetable.pop("_id", None)
    return {"ok": True, "timetable": timetable}


@api.get("/timetable")
async def get_timetable(_: dict = Depends(current_user)):
    return await db.timetables.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api.put("/timetable/{timetable_id}")
async def update_timetable(timetable_id: str, input: EntityInput, _: dict = Depends(current_user)):
    payload = input.model_dump(); conflicts = validate_entries(payload.get("entries", []))
    if conflicts:
        raise HTTPException(status_code=409, detail={"message": "Conflict detected", "conflicts": conflicts})
    payload["updated_at"] = now()
    result = await db.timetables.update_one({"id": timetable_id}, {"$set": payload})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return {"id": timetable_id, **payload}


@api.get("/analytics")
async def analytics(_: dict = Depends(current_user)):
    timetable = await db.timetables.find_one({"active": True}, {"_id": 0})
    entries = timetable.get("entries", []) if timetable else []
    return {"faculty_workload": [{"name": key, "lectures": value} for key, value in Counter(e["teacher_name"] for e in entries).items()], "room_utilization": [{"name": key, "sessions": value} for key, value in Counter(e["room_name"] for e in entries).items()], "subject_distribution": [{"name": key, "sessions": value} for key, value in Counter(e["subject_name"] for e in entries).items()], "daily_density": [{"name": key, "sessions": value} for key, value in Counter(e["day"] for e in entries).items()], "quality_score": timetable.get("score", 0) if timetable else 0}


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[os.environ["FRONTEND_URL"]], allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown():
    client.close()