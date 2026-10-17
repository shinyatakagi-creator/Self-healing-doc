from fastapi import FastAPI

app = FastAPI()


@app.post("/v1/search")
def run_search(query: str, limit: int = 10):
    """Search the index."""
    ...
