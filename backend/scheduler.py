from collections import Counter, defaultdict
from typing import Any


def _available(slot_key: str, availability: list[dict[str, Any]] | None) -> bool:
    if not availability:
        return True

    values = {
        item.get("slot_key"): item.get("status", "available")
        for item in availability
    }

    return values.get(slot_key, "available") != "unavailable"


def generate_schedule(teachers, subjects, divisions, rooms, labs, config):
    days = config.get("working_days") or [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
    ]

    periods = int(config.get("periods_per_day") or 6)

    slots = [
        {
            "day": day,
            "period": period,
            "slot_key": f"{day}-{period}",
        }
        for day in days
        for period in range(1, periods + 1)
    ]

    # Map both internal teacher ID and employee ID.
    # Subjects currently store employee IDs such as OS_IT, DS_IT, HOD_IT.
    teacher_map = {
        item["id"]: item
        for item in teachers
    }

    for teacher in teachers:
        if teacher.get("employee_id"):
            teacher_map[teacher["employee_id"]] = teacher

    print("TEACHER MAP:", teacher_map)

    room_list = rooms + labs

    used_teachers = set()
    used_rooms = set()
    used_divisions = set()

    daily_teacher = Counter()
    weekly_teacher = Counter()
    daily_division = Counter()

    entries = []
    failures = []
    requests = []

    # Build all scheduling requests.
    for division in divisions:
        chosen = [
            s
            for s in subjects
            if s["id"] in set(division.get("subjects") or [])
        ] or [
            s
            for s in subjects
            if (
                not s.get("department")
                or not division.get("department")
                or s.get("department") == division.get("department")
            )
        ]

        for subject in chosen:
            count = int(subject.get("lectures_per_week") or 0)

            for occurrence in range(count):
                requests.append(
                    (
                        subject.get("requires_lab", False),
                        division,
                        subject,
                        occurrence,
                    )
                )

    # Practical/lab requests first.
    requests.sort(
        key=lambda item: (
            not item[0],
            item[1].get("student_count", 0),
        ),
        reverse=True,
    )

    multi_department = (
        config.get("department_mode", "single") == "multi"
    )

    def teaches(teacher, subject):
        department = subject.get("department")

        if not department:
            return True

        if multi_department:
            return department in {
                teacher.get("department"),
                *(teacher.get("departments") or []),
            }

        return teacher.get("department") == department

    # Schedule every requested lecture.
    for requires_lab, division, subject, occurrence in requests:

        assigned_teacher_id = subject.get("teacher_id")

        print(
            "SUBJECT:",
            subject.get("code"),
            subject.get("name"),
            "TEACHER_ID:",
            subject.get("teacher_id"),
        )

        # Prefer the explicitly assigned teacher.
        # Because teacher_map contains employee_id as well as UUID,
        # values such as OS_IT now resolve correctly.
        if assigned_teacher_id in teacher_map:
            candidates_teachers = [
                teacher_map[assigned_teacher_id]
            ]
        else:
            candidates_teachers = [
                teacher
                for teacher in teachers
                if teaches(teacher, subject)
            ]

        assigned = None

        for slot in slots:
            slot_key = slot["slot_key"]

            # A division cannot have two classes in the same period.
            if (division["id"], slot_key) in used_divisions:
                continue

            for teacher in candidates_teachers:

                # Teacher cannot teach two classes at the same time.
                if (
                    teacher["id"],
                    slot_key,
                ) in used_teachers:
                    continue

                # Respect teacher availability.
                if not _available(
                    slot_key,
                    teacher.get("availability"),
                ):
                    continue

                # Respect maximum daily lectures.
                if (
                    daily_teacher[
                        (teacher["id"], slot["day"])
                    ]
                    >= int(
                        teacher.get(
                            "maximum_lectures_per_day"
                        )
                        or 99
                    )
                ):
                    continue

                # Respect maximum weekly lectures.
                if (
                    weekly_teacher[teacher["id"]]
                    >= int(
                        teacher.get(
                            "maximum_lectures_per_week"
                        )
                        or 999
                    )
                ):
                    continue

                # Find suitable rooms/labs.
                room_candidates = [
                    room
                    for room in room_list
                    if room.get("capacity", 0)
                    >= division.get("student_count", 0)
                    and (
                        not requires_lab
                        or room.get("room_type")
                        == "Laboratory"
                    )
                ]

                for room in room_candidates:

                    room_key = (
                        room["id"],
                        slot_key,
                    )

                    # Room cannot be used by another class
                    # in the same period.
                    if room_key in used_rooms:
                        continue

                    if not _available(
                        slot_key,
                        room.get("available_slots"),
                    ):
                        continue

                    assigned = {
                        "id": f"session-{len(entries) + 1}",
                        "division_id": division["id"],
                        "division_name": division["name"],
                        "subject_id": subject["id"],
                        "subject_name": subject["name"],
                        "subject_code": subject.get("code", ""),
                        "teacher_id": teacher["id"],
                        "teacher_name": teacher["name"],
                        "room_id": room["id"],
                        "room_name": (
                            room.get("room_number")
                            or room.get("lab_number")
                            or room.get("name")
                        ),
                        "day": slot["day"],
                        "period": slot["period"],
                        "slot_key": slot_key,
                        "requires_lab": requires_lab,
                    }

                    break

                if assigned:
                    break

            if assigned:
                break

        # No valid slot found.
        if not assigned:
            failures.append(
                {
                    "subject": subject.get("name"),
                    "division": division.get("name"),
                    "reason": (
                        "No teacher, room, lab, availability, "
                        "or period satisfies the hard constraints."
                        if candidates_teachers
                        else (
                            f"No teacher belongs to the "
                            f"{subject.get('department')} department "
                            f"({'multi' if multi_department else 'single'}"
                            "-department mode)."
                        )
                    ),
                }
            )

            continue

        # Save successful assignment.
        entries.append(assigned)

        used_divisions.add(
            (
                assigned["division_id"],
                assigned["slot_key"],
            )
        )

        used_teachers.add(
            (
                assigned["teacher_id"],
                assigned["slot_key"],
            )
        )

        used_rooms.add(
            (
                assigned["room_id"],
                assigned["slot_key"],
            )
        )

        daily_teacher[
            (
                assigned["teacher_id"],
                assigned["day"],
            )
        ] += 1

        weekly_teacher[
            assigned["teacher_id"]
        ] += 1

        daily_division[
            (
                assigned["division_id"],
                assigned["day"],
            )
        ] += 1

    score = max(
        0,
        round(
            100
            - (len(failures) * 12)
            - (len(entries) * 0.4)
        ),
    )

    return {
        "entries": entries,
        "failures": failures,
        "score": score,
        "slots": slots,
        "hard_constraint_violations": (
            0 if not failures else len(failures)
        ),
    }


def validate_entries(entries):
    conflicts = []

    seen = defaultdict(list)

    for entry in entries:
        for field, label in [
            ("teacher_id", "Teacher"),
            ("room_id", "Room"),
            ("division_id", "Division"),
        ]:
            key = (
                field,
                entry.get(field),
                entry.get("slot_key"),
            )

            if seen[key]:
                conflicts.append(
                    {
                        "type": f"{label.lower()}_conflict",
                        "severity": "critical",
                        "description": (
                            f"{label} is assigned twice at "
                            f"{entry.get('day')} "
                            f"period {entry.get('period')}."
                        ),
                        "affected_entities": [
                            entry.get(field),
                            seen[key][0],
                        ],
                    }
                )

            seen[key].append(entry.get("id"))

    return conflicts