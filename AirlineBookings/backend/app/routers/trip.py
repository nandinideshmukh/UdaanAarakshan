from fastapi import APIRouter, Depends, HTTPException
from httpx import HTTPStatusError
from json import JSONDecodeError

from app.agents.booking_agent import book_flight
from app.agents.email_agent import queue_confirmation_email
from app.agents.orchestrator import (
    approve_selection,
    compare_results,
    is_approved,
    refine_comparison,
    start_search,
)
from app.core.security import get_current_user
from app.models.schemas import (
    ApprovalStatus,
    BookingConfirmation,
    BookingRequest,
    RankedResult,
    RefineRequest,
    SearchResult,
    TripRequest,
)
from app.services.json_store import list_keys, read_json

router = APIRouter()


@router.post("/search", response_model=SearchResult)
async def search(trip: TripRequest, user_id: str = Depends(get_current_user)):
    try:
        return await start_search(trip)
    except (JSONDecodeError, KeyError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Search Agent returned malformed data from the LLM: {e}",
        ) from e
    except HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider request failed: {e.response.status_code} {e.response.text[:200]}",
        ) from e


@router.post("/compare/{request_id}", response_model=RankedResult)
async def compare(request_id: str, trip: TripRequest, user_id: str = Depends(get_current_user)):
    try:
        return await compare_results(request_id, trip)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/refine/{request_id}", response_model=RankedResult)
async def refine(
    request_id: str,
    trip: TripRequest,
    refinement: RefineRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Human-in-the-loop: person reviews /compare's picks and doesn't like them
    ('too many stops', 'I'd pay more to fly direct', etc). This re-runs the
    Comparator Agent with that feedback and returns a new ranking to review.
    Can be called as many times as needed before /approve.
    """
    try:
        return await refine_comparison(request_id, trip, refinement.feedback)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/approve/{request_id}", response_model=ApprovalStatus)
async def approve(request_id: str, user_id: str = Depends(get_current_user)):
    """Human explicitly signs off on the current ranked picks — required before /book."""
    try:
        await approve_selection(request_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ApprovalStatus(request_id=request_id, approved=True)


@router.post("/book", response_model=BookingConfirmation)
async def book(booking: BookingRequest, user_id: str = Depends(get_current_user)):
    from app.services.hold_service import get_hold

    if not await is_approved(booking.request_id):
        raise HTTPException(
            status_code=400,
            detail="Selection not approved yet — call /api/trip/approve/{request_id} first",
        )

    hold = await get_hold(booking.request_id)
    if not hold:
        raise HTTPException(
            status_code=400,
            detail="No active price hold for this request — it may have expired. Hold the flight again.",
        )
    if hold.pnr != booking.pnr:
        raise HTTPException(status_code=400, detail="PNR does not match the active hold for this request")

    confirmation = await book_flight(booking)
    # Enqueue instead of sending inline — keeps this request fast
    await queue_confirmation_email(confirmation)
    return confirmation


@router.get("/bookings", response_model=list[BookingConfirmation])
async def list_bookings(user_id: str = Depends(get_current_user)):
    """Lets the user review booking history — reads straight from Redis JSON store."""
    keys = await list_keys("bookings:*")
    records = [await read_json(k) for k in keys]
    return [BookingConfirmation(**r) for r in records if r]


@router.get("/bookings/{booking_id}", response_model=BookingConfirmation)
async def get_booking(booking_id: str, user_id: str = Depends(get_current_user)):
    record = await read_json(f"bookings:{booking_id}")
    if not record:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingConfirmation(**record)