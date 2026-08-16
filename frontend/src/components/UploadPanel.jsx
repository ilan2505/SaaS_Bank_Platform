import { useRef, useState } from "react";
import { api } from "../api";

export default function UploadPanel({ batchId, onUploaded }) {
  const csvInput = useRef(null);
  const pdfInput = useRef(null);
  const [busy, setBusy] = useState(null); // "csv" | "pdf" | null
  const [message, setMessage] = useState("");

  async function handleCsv() {
    const file = csvInput.current.files[0];
    if (!file) return;
    setBusy("csv");
    setMessage("");
    try {
      const result = await api.uploadCsv(batchId, file);
      setMessage(`Imported ${result.records_created} records from ${file.name}`);
      csvInput.current.value = "";
      onUploaded();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setBusy(null);
    }
  }

  async function handlePdf() {
    const files = Array.from(pdfInput.current.files || []);
    if (files.length === 0) return;
    setBusy("pdf");
    setMessage("");
    try {
      const result = await api.uploadPdfs(batchId, files);
      setMessage(`Extracted ${result.records_created} records from ${files.length} PDF(s)`);
      pdfInput.current.value = "";
      onUploaded();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="panel">
      <h2>Upload</h2>
      <div className="upload-row">
        <div className="upload-group">
          <input ref={csvInput} type="file" accept=".csv" />
          <button onClick={handleCsv} disabled={busy !== null}>
            {busy === "csv" ? "Importing…" : "Upload CSV"}
          </button>
        </div>
        <div className="upload-group">
          <input ref={pdfInput} type="file" accept=".pdf" multiple />
          <button onClick={handlePdf} disabled={busy !== null}>
            {busy === "pdf" ? "Extracting…" : "Upload PDF(s)"}
          </button>
        </div>
      </div>
      {message && <div className="status-message" style={{ marginTop: 10 }}>{message}</div>}
    </div>
  );
}
