import CardRenderer from "./cards/CardRenderer";
import { PlaneIcon } from "./icons";

export default function ChatBubble({ role, text, cards, passengerCount, onPickFlight, onSelectSeat }) {
  const isUser = role === "user";

  // Deduplicate cards by type AND data so an over-eager LLM calling the same tool
  // twice in one turn doesn't stack identical UIs in the chat window.
  const uniqueCards = [];
  const seenHashes = new Set();
  for (const card of cards || []) {
    const hash = card.type + ":" + JSON.stringify(card.data);
    if (!seenHashes.has(hash)) {
      seenHashes.add(hash);
      uniqueCards.push(card);
    }
  }

  return (
    <div className={`chat-turn ${isUser ? "chat-turn--user" : "chat-turn--agent"}`}>
      {!isUser && (
        <div className="chat-turn__avatar">
          <PlaneIcon />
        </div>
      )}
      <div className="chat-turn__body">
        {text && <div className="chat-bubble">{text}</div>}
        {uniqueCards.length > 0 && (
          <div className="chat-turn__cards">
            {uniqueCards.map((card, i) => (
              <CardRenderer
                key={`${card.type}-${i}`}
                card={card}
                passengerCount={passengerCount}
                onPickFlight={onPickFlight}
                onSelectSeat={onSelectSeat}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
