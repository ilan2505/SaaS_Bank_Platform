import { useEffect, useState } from "react";
import { api } from "../api";
import { EDITABLE_FIELDS, STATUS_LABELS } from "../constants";

function buildFormState(record) {
  const state = {};
  for (const f of EDITABLE_FIELDS) {
    const value = record[f.key];
    state[f.key] = value === null || value === undefined ? "" : String(value);
  }
  return state;
}

const FIELD_LABELS = Object.fromEntries(EDITABLE_FIELDS.map((f) => [f.key, f.label]));
function fieldLabel(key) {
  return FIELD_LABELS[key] || key;
}

export default function RecordDrawer({ record, onClose, onChanged }) {
  const [current, setCurrent] = useState(record);
  const [form, setForm] = useState(buildFormState(record));
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");
  const [history, setHistory] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    setCurrent(record);
    setForm(buildFormState(record));
    setActionError("");
    refreshHistory(record.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record.id]);

  async function refreshHistory(recordId) {
    try {
      setHistory(await api.getRecordHistory(recordId));
    } catch {
      // non-critical: leave history empty rather than blocking the drawer
    }
  }

  const errorsByField = {};
  for (const e of current.validation_errors) {
    errorsByField[e.field] = errorsByField[e.field] ? `${errorsByField[e.field]}; ${e.message}` : e.message;
  }
  const generalErrors = current.validation_errors.filter(
    (e) => !EDITABLE_FIELDS.some((f) => f.key === e.field)
  );

  function updateField(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setActionError("");
    try {
      const patch = {};
      for (const f of EDITABLE_FIELDS) patch[f.key] = form[f.key];
      await api.editRecord(current.id, patch);
      const revalidated = await api.revalidateRecord(current.id);
      setCurrent(revalidated);
      setForm(buildFormState(revalidated));
      await refreshHistory(current.id);
      onChanged();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleValidate() {
    setSaving(true);
    setActionError("");
    try {
      const updated = await api.validateRecord(current.id);
      setCurrent(updated);
      setForm(buildFormState(updated));
      onChanged();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const showPdf = current.has_source_file;
  const canValidate = current.status === "VALID";

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className={`drawer${showPdf ? " with-pdf" : ""}`} onClick={(e) => e.stopPropagation()}>
        {showPdf && (
          <div className="drawer-pdf-panel">
            <div className="drawer-pdf-header">
              <span>Original PDF · {current.source_document_name}</span>
              <a href={api.sourceFileUrl(current.id)} target="_blank" rel="noreferrer">
                Open in new tab ↗
              </a>
            </div>
            <iframe
              src={api.sourceFileUrl(current.id)}
              title={`Source document for ${current.reference || current.id}`}
              className="drawer-pdf-frame"
            />
          </div>
        )}

        <div className="drawer-form-panel">
          <div className="drawer-header">
            <h2>
              {current.reference || "Record"}
              <span className={`badge ${current.status}`}>{STATUS_LABELS[current.status] || current.status}</span>
            </h2>
            <button className="drawer-close" onClick={onClose}>✕</button>
          </div>

          <div className="drawer-meta">
            Source: {current.source_type} · {current.source_document_name}
          </div>

          {current.extraction_confidence != null && (
            <div className="confidence-note">
              AI extraction confidence: {(Number(current.extraction_confidence) * 100).toFixed(0)}%
            </div>
          )}

          {generalErrors.length > 0 && (
            <div className="general-error-banner">
              {generalErrors.map((e, i) => (
                <div key={i}>{e.message}</div>
              ))}
            </div>
          )}

          <div className="field-grid">
            {EDITABLE_FIELDS.map((f) => (
              <div
                key={f.key}
                className={`field-row${f.full ? " full" : ""}${errorsByField[f.key] ? " has-error" : ""}`}
              >
                <label>{f.label}</label>
                {f.type === "select" ? (
                  <select value={form[f.key]} onChange={(e) => updateField(f.key, e.target.value)}>
                    <option value="">—</option>
                    {f.options.map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={form[f.key]}
                    onChange={(e) => updateField(f.key, e.target.value)}
                  />
                )}
                {errorsByField[f.key] && <div className="field-error">{errorsByField[f.key]}</div>}
              </div>
            ))}
          </div>

          <div className="history-section">
            <button type="button" className="history-toggle" onClick={() => setHistoryOpen((v) => !v)}>
              {historyOpen ? "▾" : "▸"} Edit history ({history.length})
            </button>
            {historyOpen &&
              (history.length === 0 ? (
                <div className="empty-note" style={{ marginTop: 10 }}>
                  No changes recorded yet.
                </div>
              ) : (
                <ul className="history-list">
                  {history.map((h) => (
                    <li key={h.id}>
                      <span className="history-field">{fieldLabel(h.field)}</span>
                      <span className="history-values">
                        {h.old_value ?? "—"} → {h.new_value ?? "—"}
                      </span>
                      <span className="history-meta">
                        {h.source === "reconciliation" ? "auto-reconciled" : "manual edit"} ·{" "}
                        {new Date(h.edited_at).toLocaleString()}
                      </span>
                    </li>
                  ))}
                </ul>
              ))}
          </div>

          {actionError && (
            <div className="field-error" style={{ marginTop: 10 }}>
              {actionError}
            </div>
          )}

          <div className="drawer-actions">
            <button className="btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              className={canValidate ? "btn-validate-active" : "btn-validate-inactive"}
              onClick={handleValidate}
              disabled={saving || !canValidate}
              title={!canValidate ? "Record must be VALID (save with no errors) first" : ""}
            >
              Validate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
