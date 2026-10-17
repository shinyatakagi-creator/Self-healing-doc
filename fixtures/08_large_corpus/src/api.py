from fastapi import FastAPI

app = FastAPI()


@app.post("/v2/search")
def search(query: str, limit: int = 20):
    """Search the index."""
    ...
