from fastapi import FastAPI

app = FastAPI()


@app.get("/v1/notes/search")
def search_notes(text: str, limit: int = 20):
    """Search notes by text."""
    ...
