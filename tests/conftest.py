import os

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def live_embedder():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    from shd.embeddings import OpenAIEmbedder

    return OpenAIEmbedder()
