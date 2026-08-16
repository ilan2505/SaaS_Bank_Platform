function fmtAmount(record) {
  if (record.gross_amount == null) return "—";
  return `${record.gross_amount} ${record.currency || ""}`.trim();
}

export default function RecordTable({ records, onSelect }) {
  if (records.length === 0) {
    return <div className="empty-state">No records match the current filters.</div>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Reference</th>
          <th>Date</th>
          <th>Description</th>
          <th>Amount</th>
          <th>Counterparty</th>
          <th>Category</th>
          <th>Source</th>
          <th>Status</th>
          <th>Errors</th>
        </tr>
      </thead>
      <tbody>
        {records.map((r) => (
          <tr key={r.id} className="record-row" onClick={() => onSelect(r)}>
            <td>{r.reference || <em>missing</em>}</td>
            <td>{r.transaction_date || <em>missing</em>}</td>
            <td>{r.description || <em>missing</em>}</td>
            <td>{fmtAmount(r)}</td>
            <td>{r.counterparty_name || <em>missing</em>}</td>
            <td>{r.category || <em>missing</em>}</td>
            <td>
              {r.source_type}
              <div style={{ fontSize: 11, color: "#888" }}>{r.source_document_name}</div>
            </td>
            <td>
              <span className={`badge ${r.status}`}>{r.status.replace("_", " ")}</span>
            </td>
            <td>
              {r.validation_errors.length > 0 && (
                <span className="error-count">{r.validation_errors.length} error(s)</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
