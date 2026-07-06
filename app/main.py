from fastapi import FastAPI

app = FastAPI(title="ResolveDesk")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
