import { CATEGORIES, STATUS_ORDER, STATUS_COLORS, STATUS_LABELS } from "../constants";

const amountFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export default function AnalyticsPanel({ records }) {
  if (!records || records.length === 0) return null;

  const statusCounts = { NEEDS_REVIEW: 0, VALID: 0, VALIDATED: 0 };
  for (const r of records) {
    if (statusCounts[r.status] !== undefined) statusCounts[r.status] += 1;
  }
  const total = records.length;

  // Absolute value, deliberately: this dataset mixes invoice-style amounts
  // (recorded at face value) with bank-statement-style amounts (recorded as
  // signed cash flow) for the same real-world payment, so the sign alone
  // doesn't reliably mean "expense" vs "income" here. This chart claims only
  // "volume," not "spend."
  //
  // Only the 15 supported categories are charted — a record with an invalid
  // category (e.g. "UNKNOWN_CATEGORY") is exactly why that record is
  // NEEDS_REVIEW in the first place, so it doesn't belong next to real
  // business categories here; it's still fully visible in the records table.
  const categoryTotals = {};
  for (const r of records) {
    if (r.net_amount == null || !CATEGORIES.includes(r.category)) continue;
    const amount = Math.abs(Number(r.net_amount));
    categoryTotals[r.category] = (categoryTotals[r.category] || 0) + amount;
  }
  const categoryEntries = Object.entries(categoryTotals).sort((a, b) => b[1] - a[1]);
  const maxCategoryValue = categoryEntries.length > 0 ? categoryEntries[0][1] : 1;

  let acc = 0;
  const segments = [];
  for (const s of STATUS_ORDER) {
    if (statusCounts[s] <= 0) continue;
    const pct = (statusCounts[s] / total) * 100;
    segments.push(`${STATUS_COLORS[s]} ${acc}% ${acc + pct}%`);
    acc += pct;
  }
  const donutStyle = segments.length > 0 ? { background: `conic-gradient(${segments.join(", ")})` } : undefined;

  return (
    <div className="card">
      <h2 className="card-label">Analytics</h2>
      <div className="analytics-grid">
        <div className="analytics-chart">
          <h3>Status breakdown</h3>
          <div className="donut-row">
            <div className="donut" style={donutStyle}>
              <div className="donut-hole">
                <div className="donut-total">{total}</div>
                <div className="donut-total-label">RECORDS</div>
              </div>
            </div>
            <div className="status-legend">
              {STATUS_ORDER.map((s) => (
                <div className="status-legend-item" key={s}>
                  <span className="status-legend-dot" style={{ background: STATUS_COLORS[s] }} />
                  {STATUS_LABELS[s]}
                  <span className="status-legend-count">{statusCounts[s]}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="analytics-chart">
          <h3>Volume by category</h3>
          {categoryEntries.length === 0 ? (
            <div className="empty-note">No categorized amounts yet.</div>
          ) : (
            <div className="category-bars">
              {categoryEntries.map(([category, value]) => (
                <div className="category-bar-row" key={category} title={`${category}: ${amountFormatter.format(value)}`}>
                  <span className="category-bar-label">{category.replace(/_/g, " ")}</span>
                  <div className="category-bar-track">
                    <div
                      className="category-bar-fill"
                      style={{ width: `${(value / maxCategoryValue) * 100}%` }}
                    />
                  </div>
                  <span className="category-bar-value">{amountFormatter.format(value)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
