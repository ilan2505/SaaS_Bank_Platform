import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import SummaryBar from "./components/SummaryBar";
import UploadPanel from "./components/UploadPanel";
import RecordTable from "./components/RecordTable";
import RecordDrawer from "./components/RecordDrawer";
import { api } from "./api";

export default function App() {
  const [batches, setBatches] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [records, setRecords] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refreshBatches = useCallback(async () => {
    const list = await api.listBatches();
    setBatches(list);
    return list;
  }, []);

  const refreshBatchDetail = useCallback(async (batchId) => {
    if (!batchId) return;
    setLoading(true);
    setError("");
    try {
      const [s, r] = await Promise.all([
        api.getBatchSummary(batchId),
        api.listRecords(batchId, { status: statusFilter, sourceType: sourceFilter }),
      ]);
      setSummary(s);
      setRecords(r);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, sourceFilter]);

  useEffect(() => {
    refreshBatches();
  }, [refreshBatches]);

  useEffect(() => {
    if (selectedId) refreshBatchDetail(selectedId);
  }, [selectedId, refreshBatchDetail]);

  async function handleCreateBatch(name) {
    const batch = await api.createBatch(name);
    await refreshBatches();
    setSelectedId(batch.id);
  }

  async function handleDeleteBatch(batchId) {
    await api.deleteBatch(batchId);
    await refreshBatches();
    if (selectedId === batchId) {
      setSelectedId(null);
      setSummary(null);
      setRecords([]);
      setSelectedRecord(null);
    }
  }

  async function handleUploaded() {
    await refreshBatches();
    await refreshBatchDetail(selectedId);
  }

  async function handleRecordChanged() {
    await refreshBatches();
    await refreshBatchDetail(selectedId);
  }

  function handleSelectRecord(record) {
    setSelectedRecord(record);
  }

  function handleCloseDrawer() {
    setSelectedRecord(null);
  }

  return (
    <>
      <Sidebar
        batches={batches}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onCreate={handleCreateBatch}
        onDelete={handleDeleteBatch}
      />
      <div className="main">
        {!selectedId && (
          <div className="empty-state">
            Create or select a batch on the left to get started.
          </div>
        )}

        {selectedId && (
          <>
            <SummaryBar summary={summary} />
            <UploadPanel
              batchId={selectedId}
              onUploaded={handleUploaded}
              csvDocuments={summary?.csv_documents ?? []}
              pdfDocuments={summary?.pdf_documents ?? []}
            />

            <div className="panel">
              <h2>Records</h2>
              <div className="filters">
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                  <option value="">All statuses</option>
                  <option value="NEEDS_REVIEW">Needs review</option>
                  <option value="VALID">Valid</option>
                  <option value="VALIDATED">Validated</option>
                </select>
                <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
                  <option value="">All sources</option>
                  <option value="CSV">CSV</option>
                  <option value="PDF">PDF</option>
                </select>
              </div>

              {loading && <div className="status-message">Loading…</div>}
              {error && <div className="field-error">{error}</div>}
              {!loading && !error && (
                <RecordTable records={records} onSelect={handleSelectRecord} />
              )}
            </div>
          </>
        )}
      </div>

      {selectedRecord && (
        <RecordDrawer
          record={selectedRecord}
          onClose={handleCloseDrawer}
          onChanged={async () => {
            await handleRecordChanged();
            const updated = await api.getRecord(selectedRecord.id);
            setSelectedRecord(updated);
          }}
        />
      )}
    </>
  );
}
