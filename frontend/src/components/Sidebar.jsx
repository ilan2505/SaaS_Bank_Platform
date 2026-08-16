import { useMemo, useState } from "react";

export default function Sidebar({ batches, selectedId, onSelect, onCreate, onDelete }) {
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("date"); // "date" | "name"
  const [deletingId, setDeletingId] = useState(null);

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

  async function handleDelete(e, batch) {
    e.stopPropagation();
    if (!window.confirm(`Delete batch "${batch.name}" and all its records? This cannot be undone.`)) {
      return;
    }
    setDeletingId(batch.id);
    try {
      await onDelete(batch.id);
    } finally {
      setDeletingId(null);
    }
  }

  const visibleBatches = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = query
      ? batches.filter((b) => b.name.toLowerCase().includes(query))
      : batches;

    const sorted = [...filtered];
    if (sortBy === "name") {
      sorted.sort((a, b) => a.name.localeCompare(b.name));
    } else {
      sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }
    return sorted;
  }, [batches, search, sortBy]);

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

      <div className="batch-controls">
        <input
          className="batch-search"
          placeholder="Search batches…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="sort-toggle">
          <button
            type="button"
            className={sortBy === "date" ? "active" : ""}
            onClick={() => setSortBy("date")}
          >
            Date
          </button>
          <button
            type="button"
            className={sortBy === "name" ? "active" : ""}
            onClick={() => setSortBy("name")}
          >
            A–Z
          </button>
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        {batches.length === 0 && (
          <div style={{ fontSize: 13, opacity: 0.6 }}>No batches yet.</div>
        )}
        {batches.length > 0 && visibleBatches.length === 0 && (
          <div style={{ fontSize: 13, opacity: 0.6 }}>No batches match "{search}".</div>
        )}
        {visibleBatches.map((b) => (
          <div
            key={b.id}
            className={`batch-item${b.id === selectedId ? " active" : ""}`}
            onClick={() => onSelect(b.id)}
          >
            <button
              className="batch-delete"
              title="Delete batch"
              onClick={(e) => handleDelete(e, b)}
              disabled={deletingId === b.id}
            >
              {deletingId === b.id ? "…" : "×"}
            </button>
            <div className="batch-name">{b.name}</div>
            <div className="batch-date">
              {new Date(b.created_at).toLocaleString()} · {b.total_records} records
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
