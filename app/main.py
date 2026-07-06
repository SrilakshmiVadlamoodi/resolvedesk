from fastapi import FastAPI

from app.api import router as chat_router

app = FastAPI(title="ResolveDesk")
app.include_router(chat_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
