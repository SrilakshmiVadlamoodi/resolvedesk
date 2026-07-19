from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin_api import router as admin_router
from app.api import router as chat_router
from app.config import settings

app = FastAPI(title="ResolveDesk")

# Frontend (Vite dev server locally, Vercel in production) is a different
# origin from this API, and sends the session token via `Authorization:
# Bearer <token>` rather than a cookie — so the browser's CORS preflight must
# explicitly allow that header, or every request fails before it's even sent.
# ALLOWED_ORIGINS is comma-separated so the production Vercel domain can be
# added via env var, without another code change.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(chat_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
