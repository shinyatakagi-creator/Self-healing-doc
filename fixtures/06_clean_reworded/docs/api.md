# API

## Looking things up

Send a POST to `/v2/search` with the text you want to find as `query`. You get ten results back unless you ask for a different number with `limit`. Archived items are left out unless you set `include_archived` to true.
