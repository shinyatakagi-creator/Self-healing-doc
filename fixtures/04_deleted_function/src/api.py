from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    """Liveness probe."""
    return {"ok": True}
