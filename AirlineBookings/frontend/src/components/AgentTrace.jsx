const TOOL_LABELS = {
  search_flights: "Searched flights",
  check_seat_availability: "Checked seat availability",
  rank_and_finalize: "Finalized recommendation",
};

function summarize(step) {
  if (step.tool === "search_flights") {
    const count = step.output?.options?.length ?? 0;
    const budget = step.input?.budget ? ` under ₹${step.input.budget}` : "";
    return `${step.input.source} → ${step.input.destination}${budget} — found ${count} option${count === 1 ? "" : "s"}`;
  }
  if (step.tool === "check_seat_availability") {
    const cats = step.output?.available_by_category ?? {};
    return Object.entries(cats).map(([k, v]) => `${v} ${k}`).join(", ") || "no seats found";
  }
  if (step.tool === "rank_and_finalize") {
    return `${step.input?.best_picks?.length ?? 0} pick(s) submitted`;
  }
  return "";
}

export default function AgentTrace({ trace }) {
  if (!trace || trace.length === 0) return null;

  return (
    <div className="agent-trace">
      <div className="agent-trace__label">
        <span className="live-dot" style={{ marginRight: 8 }} />
        Agent reasoning trace — decided autonomously, not scripted
      </div>
      <ol className="agent-trace__list">
        {trace.map((step) => (
          <li className="agent-trace__step" key={step.step}>
            <span className="agent-trace__index">{String(step.step).padStart(2, "0")}</span>
            <div>
              <div className="agent-trace__tool">{TOOL_LABELS[step.tool] ?? step.tool}</div>
              <div className="agent-trace__summary">{summarize(step)}</div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
