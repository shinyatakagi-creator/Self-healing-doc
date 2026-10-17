from fastapi import FastAPI

app = FastAPI()

@app.post("/v1/search")
def search(query: str, limit: int = 20):
    """Search the index."""
    ...
