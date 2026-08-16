import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import UploadPanel from "./components/UploadPanel";
import RecordTable from "./components/RecordTable";
import RecordDrawer from "./components/RecordDrawer";
import AnalyticsPanel from "./components/AnalyticsPanel";
import { api } from "./api";

export default function App() {
  const [batches, setBatches] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [records, setRecords] = useState([]);
  const [allRecords, setAllRecords] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [documentFilter, setDocumentFilter] = useState("");
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
      const [s, r, all] = await Promise.all([
        api.getBatchSummary(batchId),
        api.listRecords(batchId, {
          status: statusFilter,
          sourceType: sourceFilter,
          sourceDocument: documentFilter,
        }),
        api.listRecords(batchId),
      ]);
      setSummary(s);
      setRecords(r);
      setAllRecords(all);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, sourceFilter, documentFilter]);

  useEffect(() => {
    refreshBatches();
  }, [refreshBatches]);

  useEffect(() => {
    if (selectedId) refreshBatchDetail(selectedId);
  }, [selectedId, refreshBatchDetail]);

  const documentOptions =
    sourceFilter === "CSV"
      ? summary?.csv_documents ?? []
      : sourceFilter === "PDF"
      ? summary?.pdf_documents ?? []
      : [...(summary?.csv_documents ?? []), ...(summary?.pdf_documents ?? [])].sort();

  useEffect(() => {
    if (documentFilter && !documentOptions.includes(documentFilter)) {
      setDocumentFilter("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceFilter, summary]);

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
      setAllRecords([]);
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
            <UploadPanel
              batchId={selectedId}
              onUploaded={handleUploaded}
              csvDocuments={summary?.csv_documents ?? []}
              pdfDocuments={summary?.pdf_documents ?? []}
            />

            <AnalyticsPanel records={allRecords} />

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
                <select value={documentFilter} onChange={(e) => setDocumentFilter(e.target.value)}>
                  <option value="">All files</option>
                  {documentOptions.map((name) => (
                    <option key={name} value={name}>{name}</option>
                  ))}
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
