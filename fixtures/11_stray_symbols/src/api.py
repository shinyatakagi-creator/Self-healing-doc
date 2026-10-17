from fastapi import FastAPI

app = FastAPI()


@app.get("/v1/reports")
def list_reports(owner: str, page_size: int = 25):
    """List reports for an owner."""
    ...
