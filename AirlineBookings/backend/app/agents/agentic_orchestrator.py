"""
Trip Planning Agent — genuinely agentic, not a fixed pipeline.

The model is given the traveler's request and a set of tools (see tools.py).
It decides, turn by turn:
  - whether to call search_flights (and with what parameters)
  - whether the results are good enough, or whether to search again with
    relaxed constraints
  - whether to check seat availability before finalizing
  - when to stop and call rank_and_finalize with its recommendation

Nothing here hardcodes "search then compare then done" — that sequence,
if it happens, is the MODEL's decision, and it can deviate from it (loop
search_flights multiple times, skip seat checks, etc). We just execute
whatever tool it asks for and feed the result back, up to a safety cap on
turns so a confused model can't loop forever.

Uses the multi-provider LLM gateway (app.services.llm) — works with
Gemini, OpenAI, or Groq depending on what's configured, with automatic
fallback between them. This module only ever deals in LLMMessage /
LLMToolCall — it never touches a provider's wire format.

Returns the final RankedResult AND a step-by-step trace of every tool call
made, so the frontend can show the reasoning process transparently — that
trace is the concrete evidence this is agentic rather than scripted.
"""

import uuid
from datetime import date

from app.agents.tools import TOOL_SCHEMAS, dispatch_tool
from app.models.schemas import AgentTraceStep, FlightOption, RankedResult, TripRequest
from app.services.cache_client import cache_set
from app.services.llm import LLMMessage, LLMToolResult, call_llm_with_tools

MAX_TURNS = 3  # safety cap so a confused model can't loop forever


def _merge_options(existing: list[FlightOption], new: list[dict]) -> list[FlightOption]:
    seen = {o.flight_number for o in existing}
    merged = list(existing)
    for raw in new:
        if raw.get("flight_number") not in seen:
            merged.append(FlightOption(**raw))
            seen.add(raw.get("flight_number"))
    return merged


SYSTEM_PROMPT_TEMPLATE = """# Role
You are a precision flight planning agent. Your task is to autonomously execute searches, evaluate results, and finalize recommendations for the traveler.

# Current date
Today's date is {today}. When the traveler gives a date without a year, assume the next upcoming occurrence relative to today — never default to a past year.

# Objective
Find the best flight(s) matching the traveler's exact criteria using the provided tools, and output a final recommendation. You do not know flight schedules or prices; you must rely entirely on the `search_flights` tool.

# Task Workflow
1. Call `search_flights` using the traveler's stated preferences.
2. Evaluate the tool's response:
   - If results meet the budget and stop constraints, proceed to finalize.
   - If results are empty or exceed budget/stop limits, call `search_flights` again with relaxed constraints (e.g., increase budget, allow more stops).
3. If the traveler explicitly requested seat preferences, call `check_seat_availability` for the top candidate flight. Do not check seats if no preference was stated.
4. Call `rank_and_finalize` exactly once to deliver your final recommendation.

# Constraints & Anti-Hallucination Rules
- Do NOT invent, guess, or hallucinate flight numbers, airlines, durations, or prices. Every detail in your final recommendation MUST exactly match the data returned by the tools.
- Do NOT call `search_flights` more than 3 times. If you reach 3 searches, you must call `rank_and_finalize` with the best options you found so far.
- If no flights exist after relaxing constraints, call `rank_and_finalize` with an empty array and state that no flights are available.
- After calling `rank_and_finalize`, do NOT call any other tools. Stop immediately."""


async def plan_trip(trip: TripRequest) -> tuple[RankedResult, list[AgentTraceStep]]:
    request_id = str(uuid.uuid4())
    trace: list[AgentTraceStep] = []

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(today=date.today().isoformat())

    user_message = f"""Plan a trip for this traveler:
{trip.model_dump_json(indent=2)}

Find and recommend the best flight(s) for them."""

    messages: list[LLMMessage] = [LLMMessage(role="user", content=user_message)]
    all_options: list[FlightOption] = []

    for turn in range(MAX_TURNS):
        response = await call_llm_with_tools(system_prompt=system_prompt, messages=messages, tools=TOOL_SCHEMAS)
        assistant_msg = response.message
        # Append the assistant turn EXACTLY as returned — this preserves
        # any provider-specific metadata (e.g. Gemini's thought_signature)
        # on each tool call, so a following turn on the SAME provider can
        # restore it, and sanitize_for_provider() strips it automatically
        # if a later turn falls back to a different provider.
        messages.append(assistant_msg)

        if not assistant_msg.tool_calls:
            # Model stopped without finalizing — bail out with whatever
            # we've gathered so far.
            break

        finalized: RankedResult | None = None

        for tc in assistant_msg.tool_calls:
            if tc.name == "rank_and_finalize":
                trace.append(
                    AgentTraceStep(step=len(trace) + 1, tool="rank_and_finalize", input=tc.arguments, output={"finalized": True})
                )
                finalized = RankedResult(
                    request_id=request_id,
                    best_picks=[FlightOption(**f) for f in tc.arguments["best_picks"]],
                    reasoning=tc.arguments["reasoning"],
                )
                messages.append(
                    LLMMessage(
                        role="tool",
                        tool_result=LLMToolResult(tool_call_id=tc.id, name=tc.name, content={"acknowledged": True}),
                    )
                )
                continue

            result = await dispatch_tool(tc.name, tc.arguments)
            if tc.name == "search_flights" and result.get("options"):
                all_options = _merge_options(all_options, result["options"])
            trace.append(AgentTraceStep(step=len(trace) + 1, tool=tc.name, input=tc.arguments, output=result))
            messages.append(
                LLMMessage(role="tool", tool_result=LLMToolResult(tool_call_id=tc.id, name=tc.name, content=result))
            )

        if finalized:
            await cache_set(
                f"search:{request_id}",
                {"request_id": request_id, "options": [o.model_dump(mode="json") for o in all_options]},
            )
            await cache_set(f"ranked:{request_id}", finalized.model_dump(mode="json"))
            await cache_set(f"approved:{request_id}", {"approved": False})
            await cache_set(f"trace:{request_id}", {"steps": [s.model_dump() for s in trace]})
            return finalized, trace

    # Safety-cap fallback: agent didn't finalize within MAX_TURNS.
    # Surface whatever the last search returned rather than failing outright.
    if all_options:
        fallback = RankedResult(
            request_id=request_id,
            best_picks=all_options[:3],
            reasoning="Agent reached its turn limit before finalizing — showing top results from its searches.",
        )
        await cache_set(
            f"search:{request_id}",
            {"request_id": request_id, "options": [o.model_dump(mode="json") for o in all_options]},
        )
        await cache_set(f"ranked:{request_id}", fallback.model_dump(mode="json"))
        await cache_set(f"approved:{request_id}", {"approved": False})
        return fallback, trace

    raise ValueError("Agent could not find any flights within the turn limit")
