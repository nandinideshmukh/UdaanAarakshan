"""
Tests for the multi-provider LLM gateway, focused on the Gemini
thought_signature correctness rules (never fabricate, always preserve
exactly, always strip before reaching another provider).

These test the pure conversion functions directly (no real network calls
— this sandbox can't reach api.groq.com / generativelanguage.googleapis.com
/ api.openai.com anyway, and these functions are pure/deterministic so
that's the right level to test them at).

Run with: python -m pytest tests/test_llm_gateway.py -v
      or: python tests/test_llm_gateway.py   (falls back to a manual runner)
"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.llm.adapters.gemini_adapter import (
    _from_gemini_response,
    _is_plausible_base64,
    _to_gemini_contents,
)
from app.services.llm.errors import InvalidRequestError
from app.services.llm.sanitize import sanitize_for_provider
from app.services.llm.types import LLMMessage, LLMToolCall, LLMToolResult

VALID_SIG = base64.b64encode(b"some-opaque-gemini-signature-bytes").decode()


def test_signature_survives_round_trip():
    raw_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {"name": "search_flights", "args": {"source": "BOM"}},
                            "thoughtSignature": VALID_SIG,
                        }
                    ]
                }
            }
        ]
    }
    response = _from_gemini_response(raw_response, model="gemini-3.6-flash")
    tc = response.message.tool_calls[0]
    assert tc.provider_metadata["gemini"]["thought_signature"] == VALID_SIG, "signature must be copied through exactly"

    messages = [LLMMessage(role="user", content="hi"), response.message]
    contents = _to_gemini_contents(messages)
    model_turn = next(c for c in contents if c["role"] == "model")
    fc_part = next(p for p in model_turn["parts"] if "functionCall" in p)
    assert fc_part["thoughtSignature"] == VALID_SIG, "signature must be restored EXACTLY on the next Gemini request"
    print("PASS: test_signature_survives_round_trip")


def test_missing_signature_not_fabricated():
    raw_response = {
        "candidates": [
            {"content": {"parts": [{"functionCall": {"name": "search_flights", "args": {}}}]}}
        ]
    }
    response = _from_gemini_response(raw_response, model="gemini-3.6-flash")
    tc = response.message.tool_calls[0]
    assert "gemini" not in tc.provider_metadata, "must not invent a gemini metadata entry when none was returned"

    messages = [response.message]
    contents = _to_gemini_contents(messages)
    assert "functionCall" not in contents[0]["parts"][0], "unsigned call must be flattened to text"
    assert "Action: called search_flights" in contents[0]["parts"][0]["text"]
    print("PASS: test_missing_signature_not_fabricated")


def test_fallback_strips_gemini_metadata_for_openai():
    tc = LLMToolCall(
        id="call_1", name="search_flights", arguments={"source": "BOM"},
        provider_metadata={"gemini": {"thought_signature": VALID_SIG}},
    )
    messages = [LLMMessage(role="assistant", tool_calls=[tc])]

    sanitized = sanitize_for_provider(messages, "openai")
    assert sanitized[0].tool_calls[0].provider_metadata == {}, "gemini metadata must be stripped when targeting openai"
    assert messages[0].tool_calls[0].provider_metadata == {"gemini": {"thought_signature": VALID_SIG}}, "original must be untouched"
    print("PASS: test_fallback_strips_gemini_metadata_for_openai")


def test_fallback_to_gemini_does_not_fabricate_signature():
    tc = LLMToolCall(id="call_1", name="search_flights", arguments={"source": "BOM"}, provider_metadata={})
    messages = [LLMMessage(role="assistant", tool_calls=[tc])]

    sanitized = sanitize_for_provider(messages, "gemini")
    contents = _to_gemini_contents(sanitized)
    assert "functionCall" not in contents[0]["parts"][0], "must convert non-Gemini unsigned call to text, not fabricate signature"
    assert "Action: called search_flights" in contents[0]["parts"][0]["text"]
    print("PASS: test_fallback_to_gemini_does_not_fabricate_signature")


def test_full_tool_lifecycle():
    raw_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {"name": "search_flights", "args": {"source": "BOM", "destination": "DEL"}},
                            "thoughtSignature": VALID_SIG,
                        }
                    ]
                }
            }
        ]
    }
    response = _from_gemini_response(raw_response, model="gemini-3.6-flash")
    tc = response.message.tool_calls[0]

    tool_result_msg = LLMMessage(
        role="tool",
        tool_result=LLMToolResult(tool_call_id=tc.id, name=tc.name, content={"options": [{"flight_number": "6E123"}]}),
    )

    messages = [LLMMessage(role="user", content="find flights"), response.message, tool_result_msg]
    contents = _to_gemini_contents(messages)

    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["thoughtSignature"] == VALID_SIG
    assert contents[2]["role"] == "user"
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "search_flights"
    assert contents[2]["parts"][0]["functionResponse"]["response"]["options"][0]["flight_number"] == "6E123"
    print("PASS: test_full_tool_lifecycle")


def test_malformed_signature_rejected():
    assert _is_plausible_base64("default_signature") is False, "'default_signature' is not valid base64 and must be rejected"
    assert _is_plausible_base64(VALID_SIG) is True

    tc = LLMToolCall(
        id="call_1", name="search_flights", arguments={},
        provider_metadata={"gemini": {"thought_signature": "not_base64_!!**"}},
    )
    messages = [LLMMessage(role="assistant", tool_calls=[tc])]

    raised = False
    try:
        _to_gemini_contents(messages)
    except InvalidRequestError as e:
        raised = True
        assert e.retryable is False, "a malformed signature error must NOT be marked retryable (don't retry unchanged)"
    assert raised, "must raise InvalidRequestError instead of sending a malformed signature"
    print("PASS: test_malformed_signature_rejected")


def test_streaming_not_implemented_honestly():
    """
    Streaming is intentionally NOT implemented — nothing in this
    application currently streams a response (both orchestrators run a
    complete tool-call turn before returning), so building and
    maintaining a Gemini streaming path with correct thought_signature
    accumulation across chunks would be unused complexity. Documenting
    this explicitly rather than silently omitting it or faking support.
    If streaming is added later, the same rule applies: a thoughtSignature
    may arrive on its own chunk separate from the functionCall chunk it
    belongs to, and must be matched up by index/id and preserved exactly,
    never defaulted.
    """
    from app.services.llm.adapters.gemini_adapter import GeminiAdapter

    assert not hasattr(GeminiAdapter, "stream"), "documenting current scope: no streaming method exists yet"
    print("PASS (documented gap, not implemented): test_streaming_not_implemented_honestly")


def run_all():
    tests = [
        test_signature_survives_round_trip,
        test_missing_signature_not_fabricated,
        test_fallback_strips_gemini_metadata_for_openai,
        test_fallback_to_gemini_does_not_fabricate_signature,
        test_full_tool_lifecycle,
        test_malformed_signature_rejected,
        test_streaming_not_implemented_honestly,
    ]
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failures += 1
            print(f"FAIL: {t.__name__} — {e}")
    print()
    if failures:
        print(f"{failures}/{len(tests)} tests FAILED")
        sys.exit(1)
    print(f"All {len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
