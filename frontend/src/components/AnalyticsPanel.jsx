// Status is a workflow pipeline (NEEDS_REVIEW -> VALID -> VALIDATED), and the
// three colors here match the badges used everywhere else in the app
// (RecordTable, RecordDrawer) so identity stays consistent across views.
const STATUS_ORDER = ["NEEDS_REVIEW", "VALID", "VALIDATED"];
const STATUS_COLORS = {
  NEEDS_REVIEW: "#eda100",
  VALID: "#3b5bdb",
  VALIDATED: "#008300",
};
const STATUS_LABELS = {
  NEEDS_REVIEW: "Needs review",
  VALID: "Valid",
  VALIDATED: "Validated",
};

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
  const categoryTotals = {};
  for (const r of records) {
    if (r.net_amount == null || !r.category) continue;
    const amount = Math.abs(Number(r.net_amount));
    categoryTotals[r.category] = (categoryTotals[r.category] || 0) + amount;
  }
  const categoryEntries = Object.entries(categoryTotals).sort((a, b) => b[1] - a[1]);
  const maxCategoryValue = categoryEntries.length > 0 ? categoryEntries[0][1] : 1;

  return (
    <div className="panel">
      <h2>Analytics</h2>
      <div className="analytics-grid">
        <div className="analytics-chart">
          <h3>Status breakdown</h3>
          <div className="status-stacked-bar">
            {STATUS_ORDER.filter((s) => statusCounts[s] > 0).map((s) => (
              <div
                key={s}
                className="status-segment"
                style={{ width: `${(statusCounts[s] / total) * 100}%`, background: STATUS_COLORS[s] }}
                title={`${STATUS_LABELS[s]}: ${statusCounts[s]} of ${total}`}
              />
            ))}
          </div>
          <div className="status-legend">
            {STATUS_ORDER.map((s) => (
              <div className="status-legend-item" key={s}>
                <span className="status-dot" style={{ background: STATUS_COLORS[s] }} />
                {STATUS_LABELS[s]} <strong>{statusCounts[s]}</strong>
              </div>
            ))}
          </div>
        </div>

        <div className="analytics-chart">
          <h3>Total volume by category (absolute)</h3>
          {categoryEntries.length === 0 ? (
            <div className="upload-file-empty">No categorized amounts yet.</div>
          ) : (
            <div className="category-bars">
              {categoryEntries.map(([category, value]) => (
                <div
                  className="category-bar-row"
                  key={category}
                  title={`${category}: ${amountFormatter.format(value)}`}
                >
                  <span className="category-bar-label">{category}</span>
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
