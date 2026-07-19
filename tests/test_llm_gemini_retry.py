from unittest.mock import MagicMock

import pytest
from google.genai import errors as genai_errors

from app import llm


def _rate_limit_error():
    return genai_errors.APIError(429, {"error": {"message": "rate limited"}})


def test_retries_on_429_then_succeeds():
    client = MagicMock()
    success = MagicMock()
    client.models.generate_content.side_effect = [_rate_limit_error(), _rate_limit_error(), success]

    result = llm._generate_gemini_content(client, model="gemini-2.5-flash", contents=[], config=None)

    assert result is success
    assert client.models.generate_content.call_count == 3


def test_gives_up_after_max_attempts_and_reraises():
    client = MagicMock()
    client.models.generate_content.side_effect = _rate_limit_error()

    with pytest.raises(genai_errors.APIError):
        llm._generate_gemini_content(client, model="gemini-2.5-flash", contents=[], config=None)

    assert client.models.generate_content.call_count == 3


def test_non_rate_limit_error_is_not_retried():
    client = MagicMock()
    client.models.generate_content.side_effect = genai_errors.APIError(
        500, {"error": {"message": "server error"}}
    )

    with pytest.raises(genai_errors.APIError):
        llm._generate_gemini_content(client, model="gemini-2.5-flash", contents=[], config=None)

    assert client.models.generate_content.call_count == 1
