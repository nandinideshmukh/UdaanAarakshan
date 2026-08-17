from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, EmailStr


class CabinClass(str, Enum):
    economy = "economy"
    premium_economy = "premium_economy"
    business = "business"
    first = "first"


class TripRequest(BaseModel):
    source: str
    destination: str
    depart_date: str
    return_date: str | None = None
    max_stops: int | None = None
    cabin_class: CabinClass = CabinClass.economy
    budget: float | None = None
    preferred_airlines: list[str] = []


class FlightOption(BaseModel):
    airline: str
    flight_number: str
    price: float
    currency: str = "INR"
    duration_minutes: int
    stops: int
    departure_time: str
    arrival_time: str


class SearchResult(BaseModel):
    request_id: str
    options: list[FlightOption]


class RankedResult(BaseModel):
    request_id: str
    best_picks: list[FlightOption]
    reasoning: str


class FeedbackRequest(BaseModel):
    request_id: str
    rating: int  # 1-5
    comment: str | None = None


class RefineRequest(BaseModel):
    """Mid-workflow human feedback that steers the Comparator's ranking."""
    feedback: str


class ApprovalStatus(BaseModel):
    request_id: str
    approved: bool


# ---------------------------------------------------------------------------
# Agentic planning (real tool-use loop, see agents/agentic_orchestrator.py)
# ---------------------------------------------------------------------------

class AgentTraceStep(BaseModel):
    """One tool call made by the autonomous Trip Planning Agent."""
    step: int
    tool: str
    input: dict
    output: dict


class AgentPlanResponse(BaseModel):
    """Result of the autonomous agent's planning run — includes its trace
    so the UI can show the reasoning process, not just the final answer."""
    request_id: str
    best_picks: list[FlightOption]
    reasoning: str
    trace: list[AgentTraceStep]


# ---------------------------------------------------------------------------
# Reservation & passenger data
# ---------------------------------------------------------------------------

class PassengerDetails(BaseModel):
    full_name: str
    date_of_birth: date
    passport_number: str
    nationality: str
    contact_email: EmailStr
    contact_phone: str
    redress_number: str | None = None


class HoldResponse(BaseModel):
    """Hold Booking / Price Freeze — locks a fare for a window before payment."""
    pnr: str
    request_id: str
    flight: FlightOption
    held_price: float
    expires_at: datetime


# ---------------------------------------------------------------------------
# Ancillaries & seat selection
# ---------------------------------------------------------------------------

SeatCategory = Literal["standard", "extra_legroom", "premium"]
SeatStatus = Literal["available", "occupied", "selected"]


class Seat(BaseModel):
    row: int
    letter: str
    category: SeatCategory
    status: SeatStatus
    price: float
    aisle_side: bool = False


class SeatMapResponse(BaseModel):
    flight_number: str
    rows: int
    seats: list[Seat]


class SeatSelectionRequest(BaseModel):
    row: int
    letter: str


class BaggageAddon(BaseModel):
    extra_checked_bags: int = 0
    extra_carry_on: bool = False


class MealPreference(str, Enum):
    standard = "standard"
    vegetarian = "vegetarian"
    vegan = "vegan"
    halal = "halal"
    kosher = "kosher"
    gluten_free = "gluten_free"
    none = "none"


class InFlightServices(BaseModel):
    meal: MealPreference = MealPreference.none
    priority_boarding: bool = False
    wifi: bool = False
    special_assistance: str | None = None  # free text, e.g. "wheelchair"


class AncillarySelection(BaseModel):
    request_id: str
    seat: SeatSelectionRequest | None = None
    baggage: BaggageAddon = BaggageAddon()
    services: InFlightServices = InFlightServices()


class ReservationSummary(BaseModel):
    """Everything gathered before final booking — the full itinerary as
    the traveler has built it up through hold -> passenger -> seat -> ancillary."""
    request_id: str
    pnr: str
    flight: FlightOption
    passenger: PassengerDetails
    seat: Seat | None = None
    baggage: BaggageAddon
    services: InFlightServices
    fare_total: float


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------

class BookingRequest(BaseModel):
    request_id: str
    pnr: str
    selected_flight: FlightOption
    passenger: PassengerDetails
    seat: SeatSelectionRequest | None = None
    baggage: BaggageAddon = BaggageAddon()
    services: InFlightServices = InFlightServices()


class BookingConfirmation(BaseModel):
    booking_id: str
    pnr: str
    status: str
    flight: FlightOption
    passenger: PassengerDetails
    seat: Seat | None = None
    baggage: BaggageAddon
    services: InFlightServices
    fare_total: float


# ---------------------------------------------------------------------------
# Multi-passenger group booking (additive — the single-passenger BookingRequest
# / BookingConfirmation above are untouched and still work as before)
# ---------------------------------------------------------------------------

class PassengerBooking(BaseModel):
    passenger: PassengerDetails
    seat: SeatSelectionRequest | None = None
    baggage: BaggageAddon = BaggageAddon()
    services: InFlightServices = InFlightServices()


class PassengerBookingResult(BaseModel):
    passenger: PassengerDetails
    seat: Seat | None = None
    baggage: BaggageAddon
    services: InFlightServices
    fare_total: float


class GroupBookingRequest(BaseModel):
    request_id: str
    pnr: str
    selected_flight: FlightOption
    passengers: list[PassengerBooking]


class GroupBookingConfirmation(BaseModel):
    booking_id: str
    pnr: str
    status: str
    flight: FlightOption
    passengers: list[PassengerBookingResult]
    total_fare: float


# ---------------------------------------------------------------------------
# Conversational (chatbot) booking agent
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = None  # omit on first message, server generates one
    message: str


class ChatCard(BaseModel):
    """A structured UI card the frontend renders inline in the chat thread
    (flight options, seat map, PNR/hold, passenger list, booking confirmation)."""
    type: str
    data: dict


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    cards: list[ChatCard] = []
