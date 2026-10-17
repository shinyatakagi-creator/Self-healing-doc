import json

from shd.detect import make_complete


def quick_is_stale(code_source: str, doc_text: str) -> bool:
    reply = make_complete()(f"Is this doc stale for this code? Answer as JSON with an is_stale field.\n\n{code_source}\n\n{doc_text}")
    return json.loads(reply)["is_stale"]
