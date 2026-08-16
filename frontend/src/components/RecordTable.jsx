import { STATUS_LABELS } from "../constants";

function fmtAmount(record) {
  if (record.gross_amount == null) return "—";
  return `${record.gross_amount} ${record.currency || ""}`.trim();
}

export default function RecordTable({ records, onSelect }) {
  if (records.length === 0) {
    return <div className="empty-table-row">No records match the current filters.</div>;
  }

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Reference</th>
            <th>Date</th>
            <th>Description</th>
            <th className="align-right">Amount</th>
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
              <td className="cell-mono">{r.reference || <span className="cell-missing">missing</span>}</td>
              <td className="cell-mono">{r.transaction_date || <span className="cell-missing">missing</span>}</td>
              <td className="cell-truncate">{r.description || <span className="cell-missing">missing</span>}</td>
              <td className="cell-amount">{fmtAmount(r)}</td>
              <td className="cell-truncate" style={{ maxWidth: 170 }}>
                {r.counterparty_name || <span className="cell-missing">missing</span>}
              </td>
              <td>
                {r.category ? (
                  <span className="category-pill">{r.category.replace(/_/g, " ")}</span>
                ) : (
                  <span className="cell-missing">missing</span>
                )}
              </td>
              <td>
                <div className="source-type">{r.source_type}</div>
                <div className="source-doc">{r.source_document_name}</div>
              </td>
              <td>
                <span className={`badge ${r.status}`}>{STATUS_LABELS[r.status] || r.status}</span>
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
    </div>
  );
}
