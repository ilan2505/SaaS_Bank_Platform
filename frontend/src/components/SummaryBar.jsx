export default function SummaryBar({ summary }) {
  if (!summary) return null;
  const cards = [
    { label: "Total records", value: summary.total_records },
    { label: "Needs review", value: summary.needs_review_count },
    { label: "Valid", value: summary.valid_count },
    { label: "Validated", value: summary.validated_count },
  ];
  return (
    <div className="summary-bar">
      {cards.map((c) => (
        <div className="summary-card" key={c.label}>
          <div className="value">{c.value}</div>
          <div className="label">{c.label}</div>
        </div>
      ))}
    </div>
  );
}
