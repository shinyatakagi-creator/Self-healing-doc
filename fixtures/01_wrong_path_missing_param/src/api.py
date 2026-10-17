from fastapi import FastAPI

app = FastAPI()

@app.post("/v2/search")
def search(query: str, limit: int = 10, include_archived: bool = False):
    """Search the index. `include_archived` was added in v2."""
    ...
