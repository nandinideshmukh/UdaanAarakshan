from fastapi import APIRouter, Depends, HTTPException

from app.agents.orchestrator import is_approved
from app.agents.seatmap_agent import generate_seatmap
from app.core.security import get_current_user
from app.models.schemas import (
    AncillarySelection,
    BaggageAddon,
    FlightOption,
    HoldResponse,
    InFlightServices,
    PassengerDetails,
    Seat,
    SeatMapResponse,
)
from app.services.cache_client import cache_get, cache_set
from app.services.hold_service import create_hold, get_hold, resolve_pnr
from app.services.json_store import read_json, save_json

router = APIRouter()


# ---------------------------------------------------------------------------
# Hold Booking / Price Freeze + PNR generation
# ---------------------------------------------------------------------------

@router.post("/hold/{request_id}", response_model=HoldResponse)
async def hold_flight(
    request_id: str,
    flight: FlightOption,
    user_id: str = Depends(get_current_user),
):
    """
    Locks the traveler's chosen flight's price for 24h and issues a PNR.
    Requires the ranking for this request_id to have been approved first
    (the human-in-the-loop gate from /trip/approve).
    """
    if not await is_approved(request_id):
        raise HTTPException(
            status_code=400,
            detail="Selection not approved yet — call /api/trip/approve/{request_id} first",
        )
    hold = await create_hold(request_id, flight)
    return hold


@router.get("/hold/{request_id}", response_model=HoldResponse)
async def get_hold_status(request_id: str, user_id: str = Depends(get_current_user)):
    hold = await get_hold(request_id)
    if not hold:
        raise HTTPException(status_code=404, detail="No active hold for this request — it may have expired")
    return hold


@router.get("/pnr/{pnr}")
async def lookup_pnr(pnr: str, user_id: str = Depends(get_current_user)):
    request_id = await resolve_pnr(pnr)
    if not request_id:
        raise HTTPException(status_code=404, detail="PNR not found or expired")
    hold = await get_hold(request_id)
    return hold


# ---------------------------------------------------------------------------
# Passenger details
# ---------------------------------------------------------------------------

@router.post("/passenger/{request_id}", response_model=PassengerDetails)
async def submit_passenger(
    request_id: str,
    passenger: PassengerDetails,
    user_id: str = Depends(get_current_user),
):
    if not await get_hold(request_id):
        raise HTTPException(status_code=400, detail="No active hold — hold a flight before adding passenger details")
    await save_json(f"passenger:{request_id}", passenger.model_dump(mode="json"))
    return passenger


@router.get("/passenger/{request_id}", response_model=PassengerDetails)
async def get_passenger(request_id: str, user_id: str = Depends(get_current_user)):
    data = await read_json(f"passenger:{request_id}")
    if not data:
        raise HTTPException(status_code=404, detail="No passenger details submitted yet")
    return PassengerDetails(**data)


# ---------------------------------------------------------------------------
# Seat map + selection
# ---------------------------------------------------------------------------

@router.get("/seatmap/{flight_number}", response_model=SeatMapResponse)
async def seatmap(flight_number: str, user_id: str = Depends(get_current_user)):
    return generate_seatmap(flight_number)


@router.post("/ancillaries/{request_id}", response_model=AncillarySelection)
async def submit_ancillaries(
    request_id: str,
    selection: AncillarySelection,
    user_id: str = Depends(get_current_user),
):
    hold = await get_hold(request_id)
    if not hold:
        raise HTTPException(status_code=400, detail="No active hold for this request")

    if selection.seat:
        seatmap_data = generate_seatmap(hold.flight.flight_number)
        match = next(
            (s for s in seatmap_data.seats if s.row == selection.seat.row and s.letter == selection.seat.letter),
            None,
        )
        if not match:
            raise HTTPException(status_code=404, detail="Seat not found on this flight")
        if match.status == "occupied":
            raise HTTPException(status_code=409, detail="That seat is already taken — pick another")

    await cache_set(f"ancillaries:{request_id}", selection.model_dump(mode="json"))
    return selection


@router.get("/ancillaries/{request_id}", response_model=AncillarySelection)
async def get_ancillaries(request_id: str, user_id: str = Depends(get_current_user)):
    data = await cache_get(f"ancillaries:{request_id}")
    if not data:
        return AncillarySelection(request_id=request_id, baggage=BaggageAddon(), services=InFlightServices())
    return AncillarySelection(**data)
