"""
The tools the Trip Planning Agent is allowed to call. Each tool is:
  1. A JSON schema (Anthropic tool-use format) describing name/params to the LLM
  2. A Python function that actually executes it

The LLM sees ONLY the schemas below and decides for itself which tool to
call, with what arguments, and how many times — nothing here hardcodes a
sequence. `dispatch_tool` is the only thing that maps a tool_use block back
to real code.
"""

from typing import Any

from app.models.schemas import TripRequest

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "search_flights",
        "description": (
            "Search for available flights between two airports on a given date. "
            "Returns a list of flight options with price, duration, stops, and times. "
            "Call this first, and call it again with relaxed constraints (higher budget, "
            "more stops allowed) if the first search returns too few or no options."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Origin airport/city code"},
                "destination": {"type": "string", "description": "Destination airport/city code"},
                "depart_date": {"type": "string", "description": "YYYY-MM-DD"},
                "cabin_class": {
                    "type": "string",
                    "enum": ["economy", "premium_economy", "business", "first"],
                    "description": "Default to economy if not specified"
                },
                "max_stops": {"type": "integer", "description": "Max allowed stops, omit for no limit"},
                "budget": {"type": "number", "description": "Max price traveler will pay, omit for no limit"},
            },
            "required": ["source", "destination", "depart_date"],
        },
    },
    {
        "name": "check_seat_availability",
        "description": (
            "Check how many seats are currently available on a specific flight, broken "
            "down by cabin section (economy, premium, extra-legroom). Use this if the "
            "traveler cares about seat availability before recommending a flight, e.g. "
            "for groups or when extra-legroom is a stated preference."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "flight_number": {"type": "string"},
            },
            "required": ["flight_number"],
        },
    },
    {
        "name": "rank_and_finalize",
        "description": (
            "Once you have gathered enough flight options (via search_flights, possibly "
            "called more than once), call this EXACTLY ONCE to submit your final ranked "
            "recommendation. This ends the planning loop."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "best_picks": {
                    "type": "array",
                    "description": "Your top recommended flights, best first, in the same shape as search_flights results",
                    "items": {
                        "type": "object",
                        "properties": {
                            "airline": {"type": "string"},
                            "flight_number": {"type": "string"},
                            "price": {"type": "number"},
                            "duration_minutes": {"type": "integer"},
                            "stops": {"type": "integer"},
                            "departure_time": {"type": "string"},
                            "arrival_time": {"type": "string"},
                        },
                        "required": [
                            "airline", "flight_number", "price", "duration_minutes",
                            "stops", "departure_time", "arrival_time",
                        ],
                    },
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explain why you picked these, referencing the traveler's stated preferences",
                },
            },
            "required": ["best_picks", "reasoning"],
        },
    },
]


async def dispatch_tool(tool_name: str, tool_input: dict[str, Any]) -> dict:
    """Executes a tool the agent decided to call and returns its result."""

    if tool_name == "search_flights":
        from app.agents.search_agent import search_flights

        trip = TripRequest(
            source=tool_input["source"],
            destination=tool_input["destination"],
            depart_date=tool_input["depart_date"],
            cabin_class=tool_input.get("cabin_class", "economy"),
            max_stops=tool_input.get("max_stops"),
            budget=tool_input.get("budget"),
        )
        result = await search_flights(trip)
        return {"request_id": result.request_id, "options": [o.model_dump() for o in result.options]}

    if tool_name == "check_seat_availability":
        from app.agents.seatmap_agent import generate_seatmap

        seatmap = generate_seatmap(tool_input["flight_number"])
        counts: dict[str, int] = {}
        for seat in seatmap.seats:
            if seat.status == "available":
                counts[seat.category] = counts.get(seat.category, 0) + 1
        return {"flight_number": tool_input["flight_number"], "available_by_category": counts}

    if tool_name == "rank_and_finalize":
        # This tool has no real side effect — it's the agent's way of
        # signaling "I'm done planning", and its input IS the final answer.
        return {"acknowledged": True}

    raise ValueError(f"Unknown tool: {tool_name}")
