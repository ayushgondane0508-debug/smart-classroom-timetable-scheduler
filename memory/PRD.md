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

## Implemented (2026-09-10, round 2)
- Real server-side exports: `GET /api/timetable/{id}/export/excel` (multi-sheet .xlsx, one grid per division) and `/export/pdf` (landscape A4 report) — verified downloads in browser
- Teacher portal: public read-only page at `/teacher/{id}` (no login) backed by `GET /api/public/teacher/{id}`; copy-link button on each Teachers row
- Timetable versions: Versions page lists every generation, "Set active" (`POST /api/timetable/{id}/activate`), pick two → side-by-side compare with amber diff highlighting
- Drag & drop editing: in single-division view, drag lectures to free slots or onto sessions to swap; instant client-side conflict check (teacher/room/division double-booking) + server 409 validation; blocked moves show inline warning

## Implemented (2026-09-10, round 3)
- Mobile day-by-day card view (`DayCards.js`, framer-motion tabs/stagger) on admin timetable page, teacher portal and teacher workspace at ≤760px; table hidden on phones
- Email schedule alerts via Resend (`emailer.py`): fired in background on generate + set-active, manual `POST /api/timetable/{id}/notify`, "Email teachers" button, Email alerts page (`NotificationsView.js`) with provider banner + log. RESEND_API_KEY intentionally empty → alerts stored with status `skipped` (MOCKED delivery until key added)
- Multi-role auth: `current_user` (any role) / `admin_user` / `teacher_user`; admin creates teacher logins (`PUT/DELETE /api/teachers/{id}/credentials`), teacher login page `/teacher-login` (`TeacherAuth.js`) → own schedule via `GET /api/me/schedule`; `POST /api/auth/change-password` with Change-password form for admin (Settings) and teachers; brute-force lockout (5 fails / 15 min)
- Emergent Object Storage (`storage.py`): teacher profile photos (`POST /api/teachers/{id}/photo`, public `GET /api/files/{id}`), Documents library (`/api/documents` upload/list/soft-delete, auth-gated download), auto-archived export history (`GET /api/exports`) — Files & exports page (`FilesView.js`)
- Department mode (single/multi) in Timetable settings; teacher `departments` list (multi mode only); scheduler restricts fallback teachers by department; Department filter on timetable page when >1 department
- Verified by testing agent: iteration_2.json — backend 11/11, frontend 100%

## Backlog
- P1: Add a real RESEND_API_KEY + verified sender to deliver emails (currently logged only)
- P2: Chart.js-based analytics charts (currently styled bars)
- P2: Student portal / student role
- P3: Split server.py into routers (auth, files, timetable)
