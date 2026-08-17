"""
The orchestrator is intentionally NOT one giant synchronous function call.
Each stage is its own FastAPI route (see routers/trip.py) so no single
request has to run all four agents end-to-end inside one function
invocation — that's how you avoid hitting Vercel's execution time limit.

The frontend drives the state machine: search -> compare -> confirm ->
book -> (queued) email. Each step's output is cached in Redis keyed by
request_id so later steps can rehydrate state without holding anything
in memory between calls.
"""

from app.models.schemas import RankedResult, SearchResult, TripRequest
from app.services.cache_client import cache_get, cache_set


async def start_search(trip: TripRequest) -> SearchResult:
    from app.agents.search_agent import search_flights

    result = await search_flights(trip)
    await cache_set(f"search:{result.request_id}", result.model_dump(mode="json"))
    return result


async def compare_results(request_id: str, trip: TripRequest) -> RankedResult:
    from app.agents.comparator_agent import rank_flights

    cached = await cache_get(f"search:{request_id}")
    if not cached:
        raise ValueError("Search results expired or not found — re-run search")

    search_result = SearchResult(**cached)
    ranked = await rank_flights(trip, search_result)
    await cache_set(f"ranked:{request_id}", ranked.model_dump(mode="json"))
    # Any new ranking invalidates a prior approval — the human must review again
    await cache_set(f"approved:{request_id}", {"approved": False})
    return ranked


async def refine_comparison(request_id: str, trip: TripRequest, feedback: str) -> RankedResult:
    """
    Human-in-the-loop step: re-runs the Comparator Agent with the person's
    feedback folded into the prompt (e.g. "prefer fewer stops", "I'd rather
    pay more for a direct flight"). Does NOT touch the original search
    results, so this can be called repeatedly until the person is happy.
    """
    from app.agents.comparator_agent import rank_flights

    cached_search = await cache_get(f"search:{request_id}")
    if not cached_search:
        raise ValueError("Search results expired or not found — re-run search")

    search_result = SearchResult(**cached_search)
    ranked = await rank_flights(trip, search_result, user_feedback=feedback)
    await cache_set(f"ranked:{request_id}", ranked.model_dump(mode="json"))
    await cache_set(f"approved:{request_id}", {"approved": False})
    return ranked


async def approve_selection(request_id: str) -> None:
    """Human explicitly approves the current ranked picks — unlocks booking."""
    if not await cache_get(f"ranked:{request_id}"):
        raise ValueError("No ranked results to approve — run /compare first")
    await cache_set(f"approved:{request_id}", {"approved": True})


async def is_approved(request_id: str) -> bool:
    status = await cache_get(f"approved:{request_id}")
    return bool(status and status.get("approved"))
