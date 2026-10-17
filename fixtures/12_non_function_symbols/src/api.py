from dataclasses import dataclass

from fastapi import FastAPI

app = FastAPI()

max_batch_size = 100


@dataclass
class Settings:
    retry_limit: int = 3
    cache_ttl = 60


@app.post("/v1/batches")
def process_batch(items: list[str]):
    """Process a batch of items."""
    ...
