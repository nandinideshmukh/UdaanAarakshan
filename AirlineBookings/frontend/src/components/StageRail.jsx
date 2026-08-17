const STAGES = ["Search", "Compare", "Review", "Approve", "Book"];

export default function StageRail({ currentIndex }) {
  return (
    <div className="stage-rail">
      {STAGES.map((label, i) => (
        <div className="stage-rail__group" key={label} style={{ display: "contents" }}>
          <div
            className={
              "stage-rail__step " +
              (i < currentIndex ? "done" : i === currentIndex ? "current" : "")
            }
          >
            <span className="stage-rail__dot" />
            {label}
          </div>
          {i < STAGES.length - 1 && <div className="stage-rail__rule" />}
        </div>
      ))}
    </div>
  );
}
