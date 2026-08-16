# Google Calendar Integration (Required for Multi-User)

The schedule assistant now requires Google Sign-In for multi-user isolation. Google Calendar
sync is enabled by default when Google OAuth credentials are configured.

## Architecture

```
Google Calendar (source of truth for event times)
      │  auto-sync on every add/update/delete (push)
      │  manual pull available via `POST /api/google/sync`
      ▼
App's SQLite + ChromaDB  (search + agent + reminders, user-scoped)
```

Events are automatically synced to Google Calendar after every agent add/update/delete
operation. Manual sync is also available.

## 1. Create Google OAuth credentials

1. Go to <https://console.cloud.google.com/apis/credentials>
2. Create an OAuth 2.0 **Web application** client.
3. Add authorized redirect URI:
   `http://127.0.0.1:8005/api/google/callback`
4. Note the **Client ID** and **Client Secret**.
5. In <https://console.cloud.google.com/apis/library>, enable the
   **Google Calendar API** for the project.
6. In OAuth consent screen, add scopes:
   - `https://www.googleapis.com/auth/calendar.events`
   - `openid`, `email`, `profile` (for Google Sign-In)

## 2. Configure the backend

In `backend/.env`:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_CALENDAR_ENABLED=true
# GOOGLE_TOKEN_KEY=<optional random string; a key file is generated if empty>
```

Also add `VITE_GOOGLE_CLIENT_ID=<your-client-id>` to `frontend/.env` and rebuild the
frontend (`npm run build`).

## 3. Usage

1. Restart the backend.
2. Users sign in with Google on the frontend.
3. After sign-in, users can click "Connect Google Calendar" in the dashboard to authorize calendar access.
4. All agent add/update/delete operations automatically sync to Google Calendar.
5. Manual sync is available: `POST /api/google/sync` `{"direction": "push"|"pull"}`

Synced events are tagged `source: "google"` in the UI, and keep their `google_event_id` so
re-syncs match up instead of duplicating.

## Security notes

- Only the **`calendar.events`** scope is requested for calendar operations (create/edit/delete events; no calendar settings, no other calendars).
- Google Sign-In uses `openid`, `email`, `profile` scopes for identity.
- The refresh token is encrypted at rest with Fernet (`GOOGLE_TOKEN_KEY`, or an auto-generated key file in `backend/data/`).
- Google may show an **"unverified app"** warning for a personal/test OAuth client. That's expected; a published app that passes Google's verification removes it. For your own calendar, use the "app is in testing mode" flow (add your email as a test user).
- OAuth state parameter uses nonce-based binding to prevent account linking attacks.
