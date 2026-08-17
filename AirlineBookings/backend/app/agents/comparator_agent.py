# app/agents/comparator_agent.py
import json

from app.models.schemas import FlightOption, RankedResult, SearchResult, TripRequest
from app.services.llm_client import call_groq
from app.services.llm_client import extract_json

async def rank_flights(trip: TripRequest, results: SearchResult, user_feedback: str | None = None) -> RankedResult:
    """
    Rank flights based on traveler preferences using Groq (free tier).
    """
    feedback_clause = (
        f'\nThe traveler reviewed a previous ranking and gave this feedback: "{user_feedback}". '
        "Incorporate it into the new ranking and reasoning."
        if user_feedback
        else ""
    )

    prompt = f"""Rank the following flight options based on the traveler's preferences.

Traveler Preferences:
{trip.model_dump_json()}
{feedback_clause}

Available Options:
{json.dumps([o.model_dump() for o in results.options])}

Constraint: Return ONLY a raw JSON object. Do not include markdown code fences, explanations, or any text before or after the JSON.
Required Format:
{{
  "best_picks": [...subset of the provided options, ordered best to worst...],
  "reasoning": "Brief explanation of why these flights were chosen based on the preferences."
}}"""

    raw = await call_groq(
        prompt=prompt,
        temperature=0.2,
    )

    result = extract_json(raw)

    if "best_picks" not in result:
        raise ValueError("Missing 'best_picks' in LLM response")

    return RankedResult(
        request_id=results.request_id,
        best_picks=[FlightOption(**o) for o in result["best_picks"]],
        reasoning=result.get("reasoning", ""),
    )