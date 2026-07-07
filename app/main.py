from fastapi import FastAPI

from app.admin_api import router as admin_router
from app.api import router as chat_router

app = FastAPI(title="ResolveDesk")
app.include_router(chat_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
