from fastapi import APIRouter, Depends, HTTPException
from httpx import HTTPStatusError

from app.agents.agentic_orchestrator import plan_trip
from app.core.security import get_current_user
from app.models.schemas import AgentPlanResponse, TripRequest

router = APIRouter()


@router.post("/plan-trip", response_model=AgentPlanResponse)
async def plan(trip: TripRequest, user_id: str = Depends(get_current_user)):
    """
    Runs the autonomous Trip Planning Agent: it decides for itself which
    tools to call (search_flights, check_seat_availability), how many
    times, and when it has enough information to finalize a recommendation.
    Returns the final picks AND the full tool-call trace so the reasoning
    process is visible, not just the answer.
    """
    try:
        ranked, trace = await plan_trip(trip)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider request failed: {e.response.status_code} {e.response.text[:300]}",
        ) from e

    return AgentPlanResponse(
        request_id=ranked.request_id,
        best_picks=ranked.best_picks,
        reasoning=ranked.reasoning,
        trace=trace,
    )
