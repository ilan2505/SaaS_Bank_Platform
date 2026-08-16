import { useRef, useState } from "react";
import { api } from "../api";

export default function UploadPanel({ batchId, onUploaded, csvDocuments = [], pdfDocuments = [] }) {
  const fileInput = useRef(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function handleUpload() {
    const files = Array.from(fileInput.current.files || []);
    if (files.length === 0) return;

    const csvFiles = files.filter((f) => f.name.toLowerCase().endsWith(".csv"));
    const pdfFiles = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    const unsupported = files.length - csvFiles.length - pdfFiles.length;

    setBusy(true);
    setMessage("");
    try {
      let csvRecords = 0;
      for (const file of csvFiles) {
        const result = await api.uploadCsv(batchId, file);
        csvRecords += result.records_created;
      }

      let pdfRecords = 0;
      if (pdfFiles.length > 0) {
        const result = await api.uploadPdfs(batchId, pdfFiles);
        pdfRecords = result.records_created;
      }

      const parts = [];
      if (csvFiles.length) parts.push(`${csvRecords} record(s) from ${csvFiles.length} CSV file(s)`);
      if (pdfFiles.length) parts.push(`${pdfRecords} record(s) from ${pdfFiles.length} PDF file(s)`);
      if (unsupported) parts.push(`${unsupported} file(s) skipped (not .csv/.pdf)`);
      setMessage(parts.join(" · ") || "Nothing to upload");

      fileInput.current.value = "";
      onUploaded();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <h2>Upload</h2>
      <div className="upload-layout">
        <div className="upload-controls">
          <input ref={fileInput} type="file" accept=".csv,.pdf" multiple />
          <button onClick={handleUpload} disabled={busy}>
            {busy ? "Uploading…" : "Upload"}
          </button>
          {message && <div className="status-message">{message}</div>}
        </div>

        <div className="upload-file-lists">
          <FileList title="PDF files" files={pdfDocuments} />
          <FileList title="CSV files" files={csvDocuments} />
        </div>
      </div>
    </div>
  );
}

function FileList({ title, files }) {
  return (
    <div className="upload-file-list">
      <h3>{title} <span className="upload-file-count">({files.length})</span></h3>
      {files.length === 0 ? (
        <div className="upload-file-empty">None yet</div>
      ) : (
        <ul>
          {files.map((name) => (
            <li key={name} title={name}>{name}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
