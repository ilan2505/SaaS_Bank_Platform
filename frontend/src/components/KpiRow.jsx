import { STATUS_ORDER, STATUS_COLORS, STATUS_LABELS } from "../constants";

export default function KpiRow({ records }) {
  const counts = { NEEDS_REVIEW: 0, VALID: 0, VALIDATED: 0 };
  for (const r of records) {
    if (counts[r.status] !== undefined) counts[r.status] += 1;
  }

  const cards = [
    { label: "Total", value: records.length, color: "#475467" },
    ...STATUS_ORDER.map((s) => ({ label: STATUS_LABELS[s], value: counts[s], color: STATUS_COLORS[s] })),
  ];

  return (
    <div className="kpi-row">
      {cards.map((c) => (
        <div className="kpi-card" key={c.label}>
          <div className="kpi-card-label-row">
            <span className="kpi-dot" style={{ background: c.color }} />
            <span className="kpi-label">{c.label}</span>
          </div>
          <div className="kpi-value">{c.value}</div>
        </div>
      ))}
    </div>
  );
}
