import { useState } from "react";

export default function Sidebar({ batches, selectedId, onSelect, onCreate }) {
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      await onCreate(name.trim());
      setName("");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="sidebar">
      <h1>Financial Records Import</h1>

      <form className="new-batch-form" onSubmit={handleCreate}>
        <input
          placeholder="New batch name (e.g. July 2026)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button type="submit" disabled={creating || !name.trim()}>
          {creating ? "Creating…" : "+ Create batch"}
        </button>
      </form>

      <div style={{ marginTop: 24 }}>
        {batches.length === 0 && (
          <div style={{ fontSize: 13, opacity: 0.6 }}>No batches yet.</div>
        )}
        {batches.map((b) => (
          <div
            key={b.id}
            className={`batch-item${b.id === selectedId ? " active" : ""}`}
            onClick={() => onSelect(b.id)}
          >
            <div>{b.name}</div>
            <div className="batch-date">
              {new Date(b.created_at).toLocaleString()} · {b.total_records} records
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
