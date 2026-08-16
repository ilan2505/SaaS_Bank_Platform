import { useEffect, useState } from "react";
import { api } from "../api";
import { EDITABLE_FIELDS } from "../constants";

function buildFormState(record) {
  const state = {};
  for (const f of EDITABLE_FIELDS) {
    const value = record[f.key];
    state[f.key] = value === null || value === undefined ? "" : String(value);
  }
  return state;
}

export default function RecordDrawer({ record, onClose, onChanged }) {
  const [current, setCurrent] = useState(record);
  const [form, setForm] = useState(buildFormState(record));
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    setCurrent(record);
    setForm(buildFormState(record));
    setActionError("");
  }, [record.id]);

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

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className={`drawer${showPdf ? " with-pdf" : ""}`} onClick={(e) => e.stopPropagation()}>
        {showPdf && (
          <div className="drawer-pdf-panel">
            <div className="drawer-pdf-header">
              <span>Original PDF — {current.source_document_name}</span>
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
            <h2 style={{ margin: 0 }}>
              {current.reference || "Record"} <span className={`badge ${current.status}`}>{current.status}</span>
            </h2>
            <button className="secondary" onClick={onClose}>Close</button>
          </div>

          <div className="status-message" style={{ marginBottom: 10 }}>
            Source: {current.source_type} · {current.source_document_name}
          </div>

          {current.extraction_confidence != null && (
            <div className="confidence-note">
              AI extraction confidence: {(Number(current.extraction_confidence) * 100).toFixed(0)}%
            </div>
          )}

          {generalErrors.length > 0 && (
            <div className="panel" style={{ background: "#fff5f5", marginBottom: 16 }}>
              {generalErrors.map((e, i) => (
                <div key={i} className="field-error">{e.message}</div>
              ))}
            </div>
          )}

          <div className="field-grid">
            {EDITABLE_FIELDS.map((f) => (
              <div
                key={f.key}
                className={`field-row${errorsByField[f.key] ? " has-error" : ""}`}
                style={f.full ? { gridColumn: "1 / -1" } : undefined}
              >
                <label>{f.label}</label>
                {f.type === "select" ? (
                  <select value={form[f.key]} onChange={(e) => updateField(f.key, e.target.value)}>
                    <option value="">—</option>
                    {f.options.map((o) => (
                      <option key={o} value={o}>{o}</option>
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

          {actionError && <div className="field-error" style={{ marginTop: 10 }}>{actionError}</div>}

          <div className="drawer-actions">
            <button onClick={handleSave} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={handleValidate}
              disabled={saving || current.status !== "VALID"}
              title={current.status !== "VALID" ? "Record must be VALID (save with no errors) first" : ""}
            >
              Validate
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
