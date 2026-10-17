# API

## Health check

`GET /health` returns `{"ok": true}`.

## Delete item

`DELETE /v1/items/{item_id}` removes an item. Call `delete_item(item_id)` to do the same from Python.
