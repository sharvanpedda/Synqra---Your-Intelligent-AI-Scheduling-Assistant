"""Auth routes: Google login only (multi-user isolation)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..auth import create_session, get_current_user, get_or_create_google_user, verify_google_id_token
from ..database import get_db
from ..models import Session as SessionRow
from ..schemas import AuthResponse, LoginGoogle, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(u) -> UserOut:
    return UserOut(id=u.id, email=u.email, display_name=u.display_name, auth_source=u.auth_source)


def _seed_new_user(user_id: str) -> None:
    """Runs after the login response is already sent (see BackgroundTasks
    below) — opens its own DB session since the request's session is closed
    by the time this executes. Errors here shouldn't crash anything; the
    user just ends up with an empty dashboard, same as before this existed."""
    try:
        from ..seed import seed  # self-contained: opens/closes its own session
        n = seed(user_id)
        print(f"[auth] seeded {n} default events for new user {user_id}")
    except Exception as exc:
        print(f"[auth] background seed failed for {user_id}: {exc}")


@router.post("/google", response_model=AuthResponse)
def login_google(body: LoginGoogle, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    info = verify_google_id_token(body.id_token)
    user, is_new = get_or_create_google_user(db, info)
    token = create_session(db, user.id)
    if is_new:
        # Fire-and-forget: don't make the person wait on ChromaDB indexing to
        # finish signing in. Their dashboard may take a few extra seconds to
        # show the seeded schedule, but login itself is never blocked on it.
        background_tasks.add_task(_seed_new_user, user.id)
    return AuthResponse(token=token, user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return _user_out(user)


@router.post("/logout", status_code=204)
def logout(user=Depends(get_current_user), db: Session = Depends(get_db),
           authorization: str = Header(default="")):
    token = authorization.split(" ", 1)[1] if authorization.lower().startswith("bearer ") else ""
    if token:
        db.execute(delete(SessionRow).where(SessionRow.token == token))
        db.commit()
    return None
