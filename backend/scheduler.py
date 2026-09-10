from collections import Counter, defaultdict
from typing import Any


def _available(slot_key: str, availability: list[dict[str, Any]] | None) -> bool:
    if not availability:
        return True
    values = {item.get("slot_key"): item.get("status", "available") for item in availability}
    return values.get(slot_key, "available") != "unavailable"


def generate_schedule(teachers, subjects, divisions, rooms, labs, config):
    days = config.get("working_days") or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods = int(config.get("periods_per_day") or 6)
    slots = [{"day": day, "period": period, "slot_key": f"{day}-{period}"} for day in days for period in range(1, periods + 1)]
    teacher_map = {item["id"]: item for item in teachers}
    room_list = rooms + labs
    used_teachers, used_rooms, used_divisions = set(), set(), set()
    daily_teacher = Counter()
    weekly_teacher = Counter()
    daily_division = Counter()
    entries, failures = [], []
    requests = []
    for division in divisions:
        for subject in subjects:
            count = int(subject.get("lectures_per_week") or 0)
            for occurrence in range(count):
                requests.append((subject.get("requires_lab", False), division, subject, occurrence))
    requests.sort(key=lambda item: (not item[0], item[1].get("student_count", 0)), reverse=True)
    for requires_lab, division, subject, occurrence in requests:
        assigned_teacher_id = subject.get("teacher_id")
        candidates_teachers = [teacher_map[assigned_teacher_id]] if assigned_teacher_id in teacher_map else teachers
        assigned = None
        for slot in slots:
            slot_key = slot["slot_key"]
            if (division["id"], slot_key) in used_divisions:
                continue
            for teacher in candidates_teachers:
                if (teacher["id"], slot_key) in used_teachers or not _available(slot_key, teacher.get("availability")):
                    continue
                if daily_teacher[(teacher["id"], slot["day"])] >= int(teacher.get("maximum_lectures_per_day") or 99):
                    continue
                if weekly_teacher[teacher["id"]] >= int(teacher.get("maximum_lectures_per_week") or 999):
                    continue
                room_candidates = [room for room in room_list if room.get("capacity", 0) >= division.get("student_count", 0) and (not requires_lab or room.get("room_type") == "Laboratory")]
                for room in room_candidates:
                    room_key = (room["id"], slot_key)
                    if room_key in used_rooms or not _available(slot_key, room.get("available_slots")):
                        continue
                    assigned = {"id": f"session-{len(entries) + 1}", "division_id": division["id"], "division_name": division["name"], "subject_id": subject["id"], "subject_name": subject["name"], "subject_code": subject.get("code", ""), "teacher_id": teacher["id"], "teacher_name": teacher["name"], "room_id": room["id"], "room_name": room.get("room_number") or room.get("lab_number") or room.get("name"), "day": slot["day"], "period": slot["period"], "slot_key": slot_key, "requires_lab": requires_lab}
                    break
                if assigned:
                    break
            if assigned:
                break
        if not assigned:
            failures.append({"subject": subject.get("name"), "division": division.get("name"), "reason": "No teacher, room, lab, availability, or period satisfies the hard constraints."})
            continue
        entries.append(assigned)
        used_divisions.add((division["id"], assigned["slot_key"]))
        used_teachers.add((assigned["teacher_id"], assigned["slot_key"]))
        used_rooms.add((assigned["room_id"], assigned["slot_key"]))
        daily_teacher[(assigned["teacher_id"], assigned["day"])] += 1
        weekly_teacher[assigned["teacher_id"]] += 1
        daily_division[(assigned["division_id"], assigned["day"])] += 1
    score = max(0, round(100 - (len(failures) * 12) - (len(entries) * 0.4)))
    return {"entries": entries, "failures": failures, "score": score, "slots": slots, "hard_constraint_violations": 0 if not failures else len(failures)}


def validate_entries(entries):
    conflicts = []
    seen = defaultdict(list)
    for entry in entries:
        for field, label in [("teacher_id", "Teacher"), ("room_id", "Room"), ("division_id", "Division")]:
            key = (field, entry.get(field), entry.get("slot_key"))
            if seen[key]:
                conflicts.append({"type": f"{label.lower()}_conflict", "severity": "critical", "description": f"{label} is assigned twice at {entry.get('day')} period {entry.get('period')}.", "affected_entities": [entry.get(field), seen[key][0]]})
            seen[key].append(entry.get("id"))
    return conflicts