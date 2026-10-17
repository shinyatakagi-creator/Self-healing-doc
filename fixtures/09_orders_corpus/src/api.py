from fastapi import FastAPI

app = FastAPI()


@app.get("/v1/orders")
def list_orders(status: str = "open", page_size: int = 25):
    """List orders, newest first."""
    ...


@app.post("/v1/orders")
def create_order(customer_id: int, items: list[str]):
    """Create an order for a customer."""
    ...


@app.delete("/v1/orders/{order_id}")
def cancel_order(order_id: int, reason: str = ""):
    """Cancel an order."""
    ...
