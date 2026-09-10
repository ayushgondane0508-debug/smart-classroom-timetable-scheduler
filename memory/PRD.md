# Smart Classroom & Timetable Scheduler — PRD

## Original problem statement
Upgrade a premium SaaS-style landing page into a fully functional "Smart Classroom & Timetable Scheduler" full-stack app: persistent MongoDB models (teachers, subjects, divisions, classrooms, labs, time slots, availability), admin dashboard with CRUD + charts, deterministic scheduling engine with hard/soft constraints and conflict detection, interactive timetable grid with editing and real-time validation, analytics, exports (PDF/Excel/Print), and a Load Demo Data feature.

## User personas
- Admin (primary): manages all entities, configures days/periods, generates and edits timetables, reviews analytics.
- Teacher / Student (planned): read-only personal schedule views (P1).

## Architecture
- Frontend: React SPA + Tailwind + Framer Motion (`/app/frontend`), landing page preserved, `/scheduler` protected route for the admin workspace.
- Backend: FastAPI (`/app/backend/server.py`) + scheduling engine (`/app/backend/scheduler.py`), JWT cookie auth (httpOnly), MongoDB via MONGO_URL.
- DB: MongoDB collections — users, teachers, subjects, divisions, classrooms, laboratories, timetables, settings, contact_messages.

## Implemented (2026-09-10)
- Landing page with all sections, dark mode, animations (done earlier)
- JWT cookie auth with seeded admin (admin@smartclassroom.com / SmartClassroom2026!) — fixed Pydantic email validation by using `.com` domain; removed stale `.local` user
- CRUD API + UI for teachers, subjects, divisions, classrooms, laboratories
- Timetable settings (working days, periods, breaks) via /api/config
- Deterministic scheduling engine with hard/soft constraints, scoring, validation
- Demo data loader (`POST /api/demo/load`) + reset
- Dashboard with stats, generator screen, weekly timetable grid (division filter), conflict center, analytics (workload, room utilization, subject distribution)
- Export UI: Print/Save PDF, Export Excel buttons on timetable view
- Fixed: generate_schedule kwarg mismatch (rooms/labs vs classrooms/laboratories), ObjectId `_id` leak in /api/contact

## Verified
- Backend: login, /auth/me, demo load, generate (score 88, 0 conflicts), timetable list, analytics, dashboard stats — all pass via curl
- Frontend: landing renders, Live Demo → /scheduler login → dashboard with stats, timetable grid renders 30 entries, teachers CRUD table, analytics charts — verified via screenshots

## Backlog
- P0: Drag & drop timetable editing with real-time conflict validation
- P0: Verify Export Excel / Print PDF flows end to end
- P1: Teacher/Student role views
- P1: Multiple timetable versions & comparison
- P1: Mobile layout for timetable grid
- P2: Chart.js-based analytics charts (currently styled bars)
