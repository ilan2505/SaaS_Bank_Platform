import { useMemo, useState } from "react";

export default function Sidebar({ batches, selectedId, onSelect, onCreate, onDelete }) {
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("date");
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
    if (!window.confirm(`Delete batch "${batch.name}" and all its records? This cannot be undone.`)) return;
    setDeletingId(batch.id);
    try {
      await onDelete(batch.id);
    } finally {
      setDeletingId(null);
    }
  }

  const visibleBatches = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = query ? batches.filter((b) => b.name.toLowerCase().includes(query)) : batches;
    const sorted = [...filtered];
    if (sortBy === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    return sorted;
  }, [batches, search, sortBy]);

  return (
    <div className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">S</div>
        <div>
          <div className="sidebar-brand-name">SaaS Bank Platform</div>
          <div className="sidebar-brand-sub">Financial records import</div>
        </div>
      </div>

      <div className="sidebar-body">
        <div>
          <div className="sidebar-section-label">New batch</div>
          <form className="new-batch-form" onSubmit={handleCreate}>
            <input
              placeholder="e.g. September 2026"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <button type="submit" disabled={creating || !name.trim()}>
              {creating ? "…" : "Add"}
            </button>
          </form>
        </div>

        <input
          className="batch-search"
          placeholder="Search batches…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <div className="sort-toggle">
          <button type="button" className={sortBy === "date" ? "active" : ""} onClick={() => setSortBy("date")}>
            Date
          </button>
          <button type="button" className={sortBy === "name" ? "active" : ""} onClick={() => setSortBy("name")}>
            A–Z
          </button>
        </div>

        <div className="batch-list">
          {batches.length === 0 && <div className="sidebar-empty">No batches yet.</div>}
          {batches.length > 0 && visibleBatches.length === 0 && (
            <div className="sidebar-empty">No batches match your search.</div>
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
                {new Date(b.created_at).toLocaleDateString()} · {b.total_records} records
              </div>
              {b.needs_review_count > 0 && (
                <div className="batch-needs-review">{b.needs_review_count} need review</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
