# Authentication testing playbook

1. Verify the seeded admin exists in MongoDB with role `admin` and a bcrypt password hash.
2. POST `/api/auth/login` with the admin email/password and save cookies.
3. GET `/api/auth/me` with those cookies; expect the admin identity.
4. POST `/api/auth/logout`, then verify `/api/auth/me` returns 401.
5. Verify invalid credentials return 401 without exposing implementation details.