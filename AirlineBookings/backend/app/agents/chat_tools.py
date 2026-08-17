"""
Tools available to the chatbot booking agent. Unlike the one-shot planning
agent (agents/tools.py), these span the ENTIRE booking journey — search,
selecting a flight (which freezes price + issues a PNR), passenger count
and details, seats, ancillaries, an explicit price-reviewed confirmation,
and even looking up or cancelling an existing booking — because the whole
flow now happens inside one conversation.

Each dispatch function takes the mutable session `state` dict and updates
it in place; the caller (chat_orchestrator) persists it after each turn.
"""

from typing import Any

from app.models.schemas import (
    BaggageAddon,
    GroupBookingRequest,
    InFlightServices,
    PassengerBooking,
    PassengerDetails,
)

CHAT_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "search_flights",
        "description": (
            "Search for flights. Only call this once you know at least the origin, "
            "destination, and travel date from what the traveler has said — if any of "
            "those are missing, ASK the traveler instead of guessing or calling this tool. "
            "If the results come back empty or nothing fits the stated budget, you may call "
            "this again with relaxed constraints (higher budget, more stops allowed) — but "
            "tell the traveler you're doing that and why, don't do it silently."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "depart_date": {"type": "string", "description": "YYYY-MM-DD"},
                "cabin_class": {
                    "type": "string",
                    "enum": ["economy", "premium_economy", "business", "first"],
                },
                "max_stops": {"type": "integer"},
                "budget": {"type": "number"},
            },
            "required": ["source", "destination", "depart_date"],
        },
    },
    {
        "name": "select_flight",
        "description": (
            "Call this once the traveler has clearly chosen one flight from the last "
            "search results (e.g. 'book the first one', 'the IndiGo one', by flight "
            "number). This freezes the price for 24h and issues a PNR — only call it "
            "once the traveler has actually confirmed a choice, not just browsing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"flight_number": {"type": "string"}},
            "required": ["flight_number"],
        },
    },
    {
        "name": "set_passenger_count",
        "description": (
            "Call this as soon as the traveler says how many people are traveling — ideally "
            "right after they pick a flight, BEFORE collecting anyone's details. E.g. 'just me' "
            "= 1, 'me and my wife' = 2. This lets you track progress ('passenger 2 of 3') while "
            "collecting details afterward. If they haven't said how many yet, ASK before adding "
            "any passenger."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 9}},
            "required": ["count"],
        },
    },
    {
        "name": "get_seatmap",
        "description": "Show the interactive seat map for the currently selected flight, so the traveler can pick seats. Reflects real-time availability, including seats other travelers have already taken.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_passenger",
        "description": (
            "Add one passenger to this booking. Call once per passenger, after "
            "set_passenger_count — the traveler may want to book for themselves and others "
            "(e.g. 'me and my wife'), so ask for each passenger's details one at a time if not "
            "all given up front. Required: full name, date of birth, passport/ID number, "
            "nationality, contact email, contact phone. Redress number is optional. Fare "
            "category (infant/child/adult) is derived automatically from date of birth."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "date_of_birth": {"type": "string", "description": "YYYY-MM-DD"},
                "passport_number": {"type": "string"},
                "nationality": {"type": "string"},
                "contact_email": {"type": "string"},
                "contact_phone": {"type": "string"},
                "redress_number": {"type": "string"},
            },
            "required": [
                "full_name", "date_of_birth", "passport_number",
                "nationality", "contact_email", "contact_phone",
            ],
        },
    },
    {
        "name": "select_seat",
        "description": "Assign a seat to a specific passenger (1-indexed, in the order they were added). Only call after get_seatmap has been shown and the traveler picked a seat. Infants under 2 don't get their own seat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "passenger_index": {"type": "integer", "description": "1-based index into the passenger list"},
                "row": {"type": "integer"},
                "letter": {"type": "string"},
            },
            "required": ["passenger_index", "row", "letter"],
        },
    },
    {
        "name": "set_ancillaries",
        "description": "Set baggage and in-flight service preferences for a specific passenger (1-indexed).",
        "input_schema": {
            "type": "object",
            "properties": {
                "passenger_index": {"type": "integer"},
                "extra_checked_bags": {"type": "integer"},
                "extra_carry_on": {"type": "boolean"},
                "meal": {
                    "type": "string",
                    "enum": ["none", "standard", "vegetarian", "vegan", "halal", "kosher", "gluten_free"],
                },
                "priority_boarding": {"type": "boolean"},
                "wifi": {"type": "boolean"},
                "special_assistance": {"type": "string"},
            },
            "required": ["passenger_index"],
        },
    },
    {
        "name": "review_booking",
        "description": (
            "Show the traveler a full itemized price breakdown (base fare, seat fees, baggage, "
            "services, taxes, per passenger and total) before booking. MUST be called at least "
            "once, and the traveler must give a clear go-ahead, before confirm_booking will work. "
            "Call this again if anything changes after the traveler has seen it (new passenger, "
            "different seat, etc) so what they approve matches what they're charged."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "confirm_booking",
        "description": (
            "Finalize and book the reservation. Only works after review_booking has been shown "
            "for the CURRENT state of the booking and the traveler has clearly said to go ahead "
            "— e.g. 'yes, book it', 'confirm'. Don't call this on an ambiguous or soft response."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_booking_status",
        "description": "Look up an existing confirmed booking by its PNR — use when the traveler asks about a booking they already made, in this session or a previous one.",
        "input_schema": {
            "type": "object",
            "properties": {"pnr": {"type": "string"}},
            "required": ["pnr"],
        },
    },
    {
        "name": "cancel_booking",
        "description": "Cancel an existing confirmed booking by PNR — releases any seats back to available. Only call after the traveler clearly confirms they want to cancel (this is irreversible in this system).",
        "input_schema": {
            "type": "object",
            "properties": {"pnr": {"type": "string"}},
            "required": ["pnr"],
        },
    },
]


def _to_flight_option(raw: dict):
    from app.models.schemas import FlightOption

    return FlightOption(**raw)


def _nearby_alternative_seats(seatmap, category: str, exclude: set[tuple[int, str]], limit: int = 5) -> list[str]:
    alts = [
        f"{s.row}{s.letter}"
        for s in seatmap.seats
        if s.status == "available" and s.category == category and (s.row, s.letter) not in exclude
    ]
    return alts[:limit]


async def dispatch_chat_tool(tool_name: str, tool_input: dict[str, Any], state: dict) -> tuple[dict, dict | None]:
    """
    Executes a tool, mutates `state` in place, and returns (tool_result, card).
    `card` is None when nothing new needs to be shown to the user for this tool.
    """

    if tool_name == "search_flights":
        from app.agents.search_agent import search_flights
        from app.models.schemas import TripRequest

        trip = TripRequest(
            source=tool_input["source"],
            destination=tool_input["destination"],
            depart_date=tool_input["depart_date"],
            cabin_class=tool_input.get("cabin_class", "economy"),
            max_stops=tool_input.get("max_stops"),
            budget=tool_input.get("budget"),
        )
        result = await search_flights(trip)
        options = [o.model_dump(mode="json") for o in result.options]
        state["search_results"] = options
        return (
            {"options": options, "count": len(options)},
            {"type": "flight_options", "data": {"options": options}},
        )

    if tool_name == "select_flight":
        from app.services.hold_service import create_hold

        flight_number = tool_input["flight_number"]
        match = next((o for o in state["search_results"] if o["flight_number"] == flight_number), None)
        if not match:
            return {"error": f"Flight {flight_number} not found in last search results"}, None

        hold = await create_hold(state["_session_id"], _to_flight_option(match))
        state["selected_flight"] = match
        state["hold"] = hold.model_dump(mode="json")
        state["reviewed"] = False  # new flight selected — any prior price review is stale
        return (
            {"pnr": hold.pnr, "held_price": hold.held_price, "expires_at": str(hold.expires_at)},
            {"type": "hold", "data": state["hold"]},
        )

    if tool_name == "set_passenger_count":
        count = tool_input["count"]
        state["passenger_count"] = count
        return {"passenger_count": count}, None

    if tool_name == "get_seatmap":
        from app.agents.seatmap_agent import generate_seatmap_live

        if not state.get("selected_flight"):
            return {"error": "No flight selected yet"}, None
        seatmap = await generate_seatmap_live(state["selected_flight"]["flight_number"])
        data = seatmap.model_dump(mode="json")
        return {"seat_count": len(data["seats"])}, {"type": "seatmap", "data": data}

    if tool_name == "add_passenger":
        passenger = PassengerDetails(
            full_name=tool_input["full_name"],
            date_of_birth=tool_input["date_of_birth"],
            passport_number=tool_input["passport_number"],
            nationality=tool_input["nationality"],
            contact_email=tool_input["contact_email"],
            contact_phone=tool_input["contact_phone"],
            redress_number=tool_input.get("redress_number"),
        )
        booking = PassengerBooking(passenger=passenger)
        state["passengers"].append(booking.model_dump(mode="json"))
        state["reviewed"] = False  # passenger list changed — prior review is stale

        from app.agents.booking_agent import fare_category

        category = fare_category(passenger.date_of_birth)
        return (
            {
                "passenger_count_so_far": len(state["passengers"]),
                "expected_total": state.get("passenger_count"),
                "fare_category": category,
            },
            {"type": "passenger_list", "data": {"passengers": state["passengers"]}},
        )

    if tool_name == "select_seat":
        from app.agents.seatmap_agent import generate_seatmap_live

        idx = tool_input["passenger_index"] - 1
        if idx < 0 or idx >= len(state["passengers"]):
            return {"error": "No such passenger — add the passenger first"}, None
        if not state.get("selected_flight"):
            return {"error": "No flight selected yet"}, None

        flight_number = state["selected_flight"]["flight_number"]
        seatmap = await generate_seatmap_live(flight_number)
        seat = next(
            (s for s in seatmap.seats if s.row == tool_input["row"] and s.letter == tool_input["letter"]),
            None,
        )
        if not seat:
            return {"error": "Seat not found"}, None

        taken_in_this_booking = {(p["seat"]["row"], p["seat"]["letter"]) for p in state["passengers"] if p.get("seat")}

        if seat.status == "occupied":
            # Real-world race condition: someone else may have taken this
            # seat since the map was shown. Offer alternatives in the same
            # category instead of a dead-end error.
            alts = _nearby_alternative_seats(seatmap, seat.category, taken_in_this_booking)
            return (
                {
                    "error": "That seat was just taken — it's no longer available.",
                    "alternatives": alts,
                },
                None,
            )
        if (seat.row, seat.letter) in taken_in_this_booking:
            alts = _nearby_alternative_seats(seatmap, seat.category, taken_in_this_booking)
            return (
                {
                    "error": "That seat is already assigned to another passenger in this booking.",
                    "alternatives": alts,
                },
                None,
            )

        state["passengers"][idx]["seat"] = {"row": seat.row, "letter": seat.letter}
        state["reviewed"] = False  # seat changed — prior review is stale
        return (
            {"assigned": f"{seat.row}{seat.letter}", "price": seat.price},
            {"type": "passenger_list", "data": {"passengers": state["passengers"]}},
        )

    if tool_name == "set_ancillaries":
        idx = tool_input["passenger_index"] - 1
        if idx < 0 or idx >= len(state["passengers"]):
            return {"error": "No such passenger — add the passenger first"}, None

        p = state["passengers"][idx]
        baggage = BaggageAddon(
            extra_checked_bags=tool_input.get("extra_checked_bags", p["baggage"]["extra_checked_bags"]),
            extra_carry_on=tool_input.get("extra_carry_on", p["baggage"]["extra_carry_on"]),
        )
        services = InFlightServices(
            meal=tool_input.get("meal", p["services"]["meal"]),
            priority_boarding=tool_input.get("priority_boarding", p["services"]["priority_boarding"]),
            wifi=tool_input.get("wifi", p["services"]["wifi"]),
            special_assistance=tool_input.get("special_assistance", p["services"]["special_assistance"]),
        )
        p["baggage"] = baggage.model_dump(mode="json")
        p["services"] = services.model_dump(mode="json")
        state["reviewed"] = False  # ancillaries changed — prior review is stale
        return (
            {"updated": True},
            {"type": "passenger_list", "data": {"passengers": state["passengers"]}},
        )

    if tool_name == "review_booking":
        from app.agents.booking_agent import compute_passenger_breakdown

        if not state.get("hold"):
            return {"error": "No flight selected/held yet"}, None
        if not state["passengers"]:
            return {"error": "No passengers added yet"}, None

        flight = _to_flight_option(state["selected_flight"])
        breakdowns = []
        grand_total = 0.0
        for pb_raw in state["passengers"]:
            pb = PassengerBooking(**pb_raw)
            b = compute_passenger_breakdown(flight.price, pb.passenger, None, pb.baggage, pb.services)
            # compute_passenger_breakdown needs the resolved Seat object for
            # seat_fee — re-resolve here for an accurate preview.
            if pb.seat:
                from app.agents.seatmap_agent import generate_seatmap

                seatmap = generate_seatmap(flight.flight_number)
                seat_obj = next((s for s in seatmap.seats if s.row == pb.seat.row and s.letter == pb.seat.letter), None)
                b = compute_passenger_breakdown(flight.price, pb.passenger, seat_obj, pb.baggage, pb.services)
            breakdowns.append({"passenger_name": pb.passenger.full_name, **b})
            grand_total += b["total"]

        state["reviewed"] = True
        review_data = {"flight": flight.model_dump(mode="json"), "passengers": breakdowns, "grand_total": round(grand_total, 2)}
        return (
            {"grand_total": round(grand_total, 2)},
            {"type": "review", "data": review_data},
        )

    if tool_name == "confirm_booking":
        from app.agents.booking_agent import book_group
        from app.agents.seatmap_agent import mark_seats_taken

        if not state.get("hold"):
            return {"error": "No flight selected/held yet — select a flight before booking"}, None
        if not state["passengers"]:
            return {"error": "No passengers added yet — add at least one passenger before booking"}, None
        if not state.get("reviewed"):
            return {"error": "Call review_booking first and get the traveler's go-ahead before confirming"}, None

        req = GroupBookingRequest(
            request_id=state["_session_id"],
            pnr=state["hold"]["pnr"],
            selected_flight=_to_flight_option(state["selected_flight"]),
            passengers=[PassengerBooking(**p) for p in state["passengers"]],
        )
        confirmation = await book_group(req)
        state["booked"] = True
        state["booking"] = confirmation.model_dump(mode="json")

        seats_to_mark = [
            (p["seat"]["row"], p["seat"]["letter"]) for p in state["passengers"] if p.get("seat")
        ]
        await mark_seats_taken(req.selected_flight.flight_number, seats_to_mark)

        from app.agents.email_agent import queue_group_confirmation_email

        await queue_group_confirmation_email(confirmation)

        return (
            {"booking_id": confirmation.booking_id, "total_fare": confirmation.total_fare},
            {"type": "booking_confirmation", "data": state["booking"]},
        )

    if tool_name == "get_booking_status":
        from app.services.json_store import read_json

        pnr = tool_input["pnr"].strip().upper()
        index = await read_json(f"bookings_by_pnr:{pnr}")
        if not index:
            return {"error": f"No booking found for PNR {pnr}"}, None
        record = await read_json(f"bookings:{index['booking_id']}")
        if not record:
            return {"error": f"No booking found for PNR {pnr}"}, None
        card_type = "booking_confirmation" if index.get("group") else "single_booking_confirmation"
        return {"status": record.get("status"), "pnr": pnr}, {"type": card_type, "data": record}

    if tool_name == "cancel_booking":
        from app.services.json_store import read_json, save_json
        from app.agents.seatmap_agent import release_seats

        pnr = tool_input["pnr"].strip().upper()
        index = await read_json(f"bookings_by_pnr:{pnr}")
        if not index:
            return {"error": f"No booking found for PNR {pnr}"}, None
        record = await read_json(f"bookings:{index['booking_id']}")
        if not record:
            return {"error": f"No booking found for PNR {pnr}"}, None
        if record.get("status") == "cancelled":
            return {"error": f"Booking {pnr} is already cancelled"}, None

        record["status"] = "cancelled"
        await save_json(f"bookings:{index['booking_id']}", record)

        flight_number = record["flight"]["flight_number"]
        if index.get("group"):
            seats = [(p["seat"]["row"], p["seat"]["letter"]) for p in record.get("passengers", []) if p.get("seat")]
        else:
            seats = [(record["seat"]["row"], record["seat"]["letter"])] if record.get("seat") else []
        await release_seats(flight_number, seats)

        if state.get("hold", {}).get("pnr") == pnr:
            state["cancelled"] = True

        return {"cancelled": True, "pnr": pnr}, {"type": "booking_cancelled", "data": {"pnr": pnr}}

    raise ValueError(f"Unknown tool: {tool_name}")
