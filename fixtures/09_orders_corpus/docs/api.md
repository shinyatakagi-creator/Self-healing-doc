# Orders API

## Listing orders

`GET /v1/orders` returns orders, newest first.

Params: `status` (optional, default `open`), `page_size` (optional, default 50)

## Creating orders

`POST /v1/orders` creates an order.

Params: `customer_id` (required), `items` (required, list of item names)

## Cancelling orders

`DELETE /v1/orders/{order_id}` cancels an order.

Params: `reason` (optional, free text, empty by default)
