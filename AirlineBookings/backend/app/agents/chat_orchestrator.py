"""
The chatbot booking agent. One HTTP call = one user message = one turn.

Within a turn, the model may call a handful of tools in sequence (e.g.
search_flights then nothing else, waiting for the traveler to pick one) —
we loop until the model produces a text-only reply, which is what lets it
pause to ask a clarifying question or wait for the traveler's next input
instead of steamrolling through the whole booking in one shot.

State (search results, selected flight/hold, passengers collected so far)
lives in Redis via chat_session.py and is injected into the system prompt
every turn as explicit ground truth — the model doesn't have to remember
it from prose, it's handed the current facts directly.

Uses the multi-provider LLM gateway (app.services.llm) — Gemini, OpenAI,
or Groq depending on what's configured, with automatic fallback. Only
LLMMessage/LLMToolCall/LLMToolResult are used here — this module never
touches a provider's wire format, and provider-specific data (like
Gemini's thought_signature) rides along transparently on each
LLMToolCall without this code ever needing to know it's there.
"""

import uuid
from datetime import date, datetime, timezone

from app.agents.chat_tools import CHAT_TOOL_SCHEMAS, dispatch_chat_tool
from app.services.chat_session import append_history, get_history, get_state, save_state
from app.services.llm import LLMError, LLMMessage, LLMToolResult, call_llm_with_tools

MAX_TOOL_TURNS = 6  # per user message — enough for e.g. set_passenger_count + add_passenger + seat in one go

SYSTEM_PROMPT_TEMPLATE = """Today's date is {today}. You are a friendly, efficient airline booking assistant, chatting
directly with a traveler in a single conversation — there are no separate
search forms or steps, everything happens through you.

When the traveler gives a date without a year (e.g. "20th September"),
assume the next upcoming occurrence of that date relative to today — do
NOT default to a past year.

Your job, roughly in this order (but follow the traveler's lead — they
may jump ahead or come back later, e.g. to check or cancel an old booking):

1. SEARCH: Understand what the traveler wants from natural language — where
   they're flying from/to, when, preferences (budget, stops, cabin). Ask
   short clarifying questions ONE AT A TIME if origin, destination, or date
   is missing. Don't call search_flights until you have those three. If the
   destination is a whole country/region rather than a specific city
   ("USA", "Europe"), ask which city — don't guess one.
   If results come back empty or nothing fits the budget, you may
   autonomously search again with relaxed constraints (higher budget, more
   stops) — but always tell the traveler you're doing that and why, e.g.
   "Nothing found under ₹6000, let me check a slightly higher budget..."
   Don't relax constraints more than twice without checking in with them.

2. SELECT: Once they confirm a choice, call select_flight — this locks the
   price and issues a PNR you should mention.

3. PASSENGER COUNT FIRST: Immediately after selecting a flight, ASK how
   many passengers are traveling (and whether any are children/infants) —
   call set_passenger_count as soon as they answer, BEFORE collecting any
   individual passenger's details. Then collect each passenger's full
   details (name, DOB, passport/ID, nationality, email, phone) one at a
   time, calling add_passenger after each, and reference progress ("got
   passenger 1 of 2, who's next?"). Fare category (infant/child/adult) is
   derived automatically from date of birth — mention it if a child/infant
   discount applies, since that's not obvious to the traveler otherwise.

4. SEATS: Offer to show the seat map (get_seatmap) and let them pick seats
   per passenger (select_seat) — optional, don't force it. Infants don't
   get their own seat. If a chosen seat was just taken by someone else
   (shown as an error with alternatives), offer those alternatives rather
   than just reporting failure.

5. ANCILLARIES: Ask about baggage/meal/wifi/priority boarding preferences
   (set_ancillaries) — optional.

6. REVIEW BEFORE PAYING: Before booking, you MUST call review_booking to
   show the traveler the full itemized price (base fare, seat fees,
   baggage, taxes, per passenger and total) and get a clear go-ahead
   ("yes, book it") — confirm_booking will refuse to run without this. If
   anything changes after showing the review (new passenger, different
   seat), call review_booking again before confirming.

7. CONFIRM: Only call confirm_booking after review_booking AND a clear
   go-ahead. Don't auto-book on an ambiguous response.

If the traveler mentions their fare hold is about to expire (see state
below), proactively remind them — don't wait to be asked.

If the traveler asks about an existing booking or wants to cancel one, use
get_booking_status / cancel_booking with their PNR. Cancelling is
irreversible in this system — make sure they clearly confirm first.

Keep replies short and conversational — this is a chat, not a report.

Current booking state (ground truth — trust this over anything said earlier
in the conversation):
{state_summary}
"""


def _summarize_state(state: dict) -> str:
    lines = []
    if state.get("cancelled"):
        lines.append("- This session's booking was CANCELLED. Start fresh if the traveler wants to book again.")
    if state.get("search_results"):
        lines.append(f"- Last search found {len(state['search_results'])} flight(s).")
    if state.get("selected_flight"):
        f = state["selected_flight"]
        lines.append(f"- Selected flight: {f['airline']} {f['flight_number']} at ₹{f['price']}.")
    if state.get("hold"):
        h = state["hold"]
        lines.append(f"- PNR issued: {h['pnr']} (price frozen at ₹{h['held_price']} until {h['expires_at']}).")
        try:
            expires = datetime.fromisoformat(str(h["expires_at"]).replace("Z", "+00:00"))
            remaining_minutes = (expires - datetime.now(timezone.utc)).total_seconds() / 60
            if 0 < remaining_minutes < 30:
                lines.append(f"  ⚠ HOLD EXPIRES IN {int(remaining_minutes)} MINUTES — proactively warn the traveler.")
            elif remaining_minutes <= 0:
                lines.append("  ⚠ HOLD HAS EXPIRED — the traveler will need to select the flight again.")
        except (ValueError, KeyError):
            pass
    if state.get("passenger_count"):
        lines.append(f"- Expected passenger count: {state['passenger_count']}.")
    if state.get("passengers"):
        names = ", ".join(p["passenger"]["full_name"] for p in state["passengers"])
        expected = state.get("passenger_count")
        progress = f" of {expected}" if expected else ""
        lines.append(f"- Passengers added so far ({len(state['passengers'])}{progress}): {names}.")
    lines.append(f"- Price review shown to traveler: {'YES' if state.get('reviewed') else 'NO — required before confirm_booking'}.")
    if state.get("booked"):
        lines.append(f"- Booking already CONFIRMED (booking_id: {state['booking']['booking_id']}, PNR: {state['booking'].get('pnr')}). Don't re-book.")
    return "\n".join(lines) if lines else "- Nothing yet. This is the start of the booking."


async def handle_chat_message(session_id: str | None, user_message: str) -> tuple[str, list[dict], str]:
    session_id = session_id or str(uuid.uuid4())

    state = await get_state(session_id)
    state["_session_id"] = session_id
    history = await get_history(session_id)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        today=date.today().isoformat(),
        state_summary=_summarize_state(state),
    )

    # Reconstruct plain text conversation for the model; tool call/result
    # messages stay local to this turn's loop and aren't persisted verbatim
    # across HTTP calls (see chat_session.py) — only the final text is.
    messages: list[LLMMessage] = [LLMMessage(role=h["role"], content=h["content"]) for h in history]
    messages.append(LLMMessage(role="user", content=user_message))

    cards: list[dict] = []
    final_text = ""

    for _ in range(MAX_TOOL_TURNS):
        try:
            response = await call_llm_with_tools(system_prompt=system_prompt, messages=messages, tools=CHAT_TOOL_SCHEMAS)
        except LLMError as e:
            final_text = f"Sorry, I hit a problem talking to the AI provider ({e.__class__.__name__}): {e}"
            break

        assistant_msg = response.message
        # Append EXACTLY as returned — preserves any provider-specific
        # metadata (e.g. Gemini thought_signature) on each tool call for
        # the next turn on the same provider; sanitize_for_provider()
        # strips it automatically if a later turn falls back elsewhere.
        messages.append(assistant_msg)

        if assistant_msg.content:
            final_text = assistant_msg.content

        if not assistant_msg.tool_calls:
            break  # model paused to talk to the user — end this turn

        for tc in assistant_msg.tool_calls:
            result, card = await dispatch_chat_tool(tc.name, tc.arguments, state)
            if card:
                cards.append(card)
            messages.append(
                LLMMessage(role="tool", tool_result=LLMToolResult(tool_call_id=tc.id, name=tc.name, content=result))
            )
    else:
        if not final_text:
            final_text = "Let me know how you'd like to continue with your booking."

    if not final_text:
        final_text = "Got it."

    await append_history(session_id, "user", user_message)
    await append_history(session_id, "assistant", final_text)
    state.pop("_session_id", None)
    await save_state(session_id, state)

    return final_text, cards, session_id
