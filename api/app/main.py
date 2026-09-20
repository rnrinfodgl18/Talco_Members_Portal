import hashlib
from datetime import datetime, timezone

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.database import database_status
from app.db import SessionLocal
from app.models.auth import AuthToken, User
from app.routers.accounts import router as accounts_router
from app.routers.user_access import router as user_access_router
from app.routers.auth import router as auth_router
from app.routers.circulars import router as circulars_router
from app.routers.dashboard import router as dashboard_router
from app.routers.notifications import router as notifications_router
from app.routers.imports import router as imports_router
from app.routers.reports import router as reports_router
from app.routers.invite_options import router as invite_options_router
from app.routers.mappings import router as mappings_router
from app.routers.settings import router as settings_router
from app.routers.portal import router as portal_router
from app.routers.pumps import router as pumps_router
from app.routers.tanneries import router as tanneries_router

app = FastAPI(title="TALCO CETP Member Portal API", version="0.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "PUT"], allow_headers=["*"])


@app.middleware("http")
async def protect_administration(request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    protected = request.url.path.startswith(("/api/imports", "/api/mappings", "/api/tanneries"))
    if not protected:
        return await call_next(request)
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
    with SessionLocal() as session:
        token = session.scalar(select(AuthToken).where(AuthToken.token_hash == digest,
                                                        AuthToken.purpose == "session",
                                                        AuthToken.used_at.is_(None)))
        now = datetime.now(timezone.utc)
        if not token or token.expires_at.replace(tzinfo=timezone.utc) <= now:
            return JSONResponse({"detail": "Session is invalid or expired"}, status_code=401)
        user = session.get(User, token.user_id)
        if not user or not user.active or user.must_set_password:
            return JSONResponse({"detail": "Account is not ready"}, status_code=401)
        if user.role not in {"talco_admin", "talco_staff"}:
            return JSONResponse({"detail": "Administration access required"}, status_code=403)
        headers = [(key, value) for key, value in request.scope["headers"]
                   if key not in {b"x-talco-role", b"x-talco-actor"}]
        headers.extend([(b"x-talco-role", user.role.encode()), (b"x-talco-actor", user.email.encode())])
        request.scope["headers"] = headers
    return await call_next(request)


app.include_router(auth_router)
app.include_router(circulars_router)
app.include_router(dashboard_router)
app.include_router(notifications_router)
app.include_router(accounts_router)
app.include_router(user_access_router)
app.include_router(invite_options_router)
app.include_router(portal_router)
app.include_router(tanneries_router)
app.include_router(pumps_router)
app.include_router(imports_router)
app.include_router(reports_router)
app.include_router(mappings_router)
app.include_router(settings_router)


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    connected, database = database_status()
    if not connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": database}
    return {"status": "ok", "database": database}
