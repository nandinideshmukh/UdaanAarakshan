import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import ChatBubble from "./ChatBubble";
import { SendIcon, PlaneIcon } from "./icons";

const EXAMPLES = [
  "Book a flight from Pune to Bangalore on 20th September, for me and my wife",
  "Delhi to Mumbai tomorrow, just me",
  "Check my booking, PNR ABC123",
];

const STAGES = ["Search", "Select", "Passengers", "Seats", "Review", "Booked"];

function currentStageIndex(messages) {
  let idx = 0;
  for (const m of messages) {
    for (const card of m.cards || []) {
      if (card.type === "flight_options") idx = Math.max(idx, 0);
      if (card.type === "hold") idx = Math.max(idx, 1);
      if (card.type === "passenger_list") idx = Math.max(idx, 2);
      if (card.type === "seatmap") idx = Math.max(idx, 3);
      if (card.type === "review") idx = Math.max(idx, 4);
      if (card.type === "booking_confirmation" || card.type === "single_booking_confirmation") idx = Math.max(idx, 5);
    }
  }
  return idx;
}

function WelcomeRoute() {
  return (
    <svg className="welcome__route" viewBox="0 0 220 56" fill="none">
      <path className="welcome__route-path" d="M8,44 C60,44 60,10 110,10 C160,10 160,44 212,44" />
      <path className="welcome__route-path-draw" d="M8,44 C60,44 60,10 110,10 C160,10 160,44 212,44" />
      <circle className="welcome__route-dot" cx="8" cy="44" r="3.5" />
      <circle className="welcome__route-dot" cx="212" cy="44" r="3.5" />
      <g className="welcome__route-plane">
        <path d="M0,-4 L4,0 L0,1.5 L-1,4 L-2,1.5 L-4,0.5 Z" transform="scale(1.4)" />
      </g>
    </svg>
  );
}

export default function ChatApp() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  const passengerCount = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const card = messages[i].cards?.find((c) => c.type === "passenger_list");
      if (card) return card.data.passengers.length;
    }
    return 1;
  })();

  const stageIndex = useMemo(() => currentStageIndex(messages), [messages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  async function sendMessage(text) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setMessages((m) => [...m, { role: "user", text: trimmed, cards: [] }]);
    setInput("");
    setError(null);
    setSending(true);

    try {
      const res = await api.sendChatMessage(sessionId, trimmed);
      setSessionId(res.session_id);
      setMessages((m) => [...m, { role: "assistant", text: res.reply, cards: res.cards }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  function handlePickFlight(flight) {
    sendMessage(`I'll take the ${flight.airline} ${flight.flight_number} flight, please book it.`);
  }

  function handleSelectSeat(passengerIndex, row, letter) {
    sendMessage(`Select seat ${row}${letter} for passenger ${passengerIndex}.`);
  }

  function handleSubmit(e) {
    e.preventDefault();
    sendMessage(input);
  }

  const hasStarted = messages.length > 0;

  return (
    <div className="chat-app">
      {hasStarted && (
        <div className="route-progress">
          {STAGES.map((label, i) => (
            <div key={label} style={{ display: "contents" }}>
              <div
                className={
                  "route-progress__stage " +
                  (i < stageIndex ? "is-done" : i === stageIndex ? "is-active" : "")
                }
              >
                <span className="route-progress__dot" />
                {label}
              </div>
              {i < STAGES.length - 1 && <div className="route-progress__line" />}
            </div>
          ))}
        </div>
      )}

      <div className="chat-app__thread" ref={scrollRef}>
        <div className="chat-app__thread-inner">
          {!hasStarted && (
            <div className="welcome">
              <WelcomeRoute />
              <h1 className="welcome__title">Where would you like to fly?</h1>
              <p className="welcome__subtitle">
                Tell me your trip in plain language — origin, destination, date, who's
                travelling — and I'll search, price, and book it right here.
              </p>
              <div className="welcome__examples">
                {EXAMPLES.map((ex) => (
                  <button key={ex} className="welcome__example" onClick={() => sendMessage(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <ChatBubble
              key={i}
              role={m.role}
              text={m.text}
              cards={m.cards}
              passengerCount={passengerCount}
              onPickFlight={handlePickFlight}
              onSelectSeat={handleSelectSeat}
            />
          ))}

          {sending && (
            <div className="chat-turn chat-turn--agent">
              <div className="chat-turn__avatar">
                <PlaneIcon />
              </div>
              <div className="chat-turn__body">
                <div className="chat-bubble chat-bubble--typing">
                  <span className="typing-dot" />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="chat-app__input-row">
        <div style={{ width: "100%", maxWidth: 700 }}>
          {error && <div className="chat-card chat-card--error chat-app__error">{error}</div>}
          <form className="chat-app__input-inner" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="Tell me about your trip…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={sending}
              autoFocus
            />
            <button className="chat-app__send-btn" type="submit" disabled={sending || !input.trim()} aria-label="Send">
              <SendIcon />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
