import { useRef, useState } from "react";
import { api } from "../api";

export default function UploadPanel({ batchId, onUploaded, csvDocuments = [], pdfDocuments = [] }) {
  const fileInput = useRef(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [deletingFile, setDeletingFile] = useState(null);

  function handleChooseFiles() {
    fileInput.current.click();
  }

  function handleFilesSelected(e) {
    setSelectedFiles(Array.from(e.target.files || []));
    setMessage("");
  }

  async function handleUpload() {
    if (selectedFiles.length === 0) return;

    const csvFiles = selectedFiles.filter((f) => f.name.toLowerCase().endsWith(".csv"));
    const pdfFiles = selectedFiles.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    const unsupported = selectedFiles.length - csvFiles.length - pdfFiles.length;

    const duplicates = [
      ...csvFiles.filter((f) => csvDocuments.includes(f.name)),
      ...pdfFiles.filter((f) => pdfDocuments.includes(f.name)),
    ].map((f) => f.name);

    if (duplicates.length > 0) {
      const proceed = window.confirm(
        `This file was already uploaded to this batch: ${duplicates.join(", ")}. ` +
          "Uploading it again will create duplicate records. Upload anyway?"
      );
      if (!proceed) {
        fileInput.current.value = "";
        setSelectedFiles([]);
        return;
      }
    }

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
      setSelectedFiles([]);
      onUploaded();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteDocument(filename) {
    if (!window.confirm(`Delete "${filename}" and all its records from this batch? This cannot be undone.`)) {
      return;
    }
    setDeletingFile(filename);
    try {
      await api.deleteDocument(batchId, filename);
      onUploaded();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setDeletingFile(null);
    }
  }

  return (
    <>
      <div className="panel">
        <h2>Upload</h2>
        <div className="upload-controls">
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.pdf"
            multiple
            onChange={handleFilesSelected}
            className="visually-hidden-input"
          />
          <div className="upload-picker-row">
            <button type="button" className="secondary" onClick={handleChooseFiles}>
              Choose files
            </button>
            <span className="upload-picker-label">
              {selectedFiles.length === 0
                ? "No files selected"
                : `${selectedFiles.length} file(s) selected`}
            </span>
          </div>
          <button onClick={handleUpload} disabled={busy || selectedFiles.length === 0}>
            {busy ? "Uploading…" : "Upload"}
          </button>
          {message && <div className="status-message">{message}</div>}
        </div>
      </div>

      <div className="panel">
        <h2>Uploaded files</h2>
        <div className="upload-file-lists">
          <FileList
            title="PDF files"
            files={pdfDocuments}
            deletingFile={deletingFile}
            onDelete={handleDeleteDocument}
          />
          <FileList
            title="CSV files"
            files={csvDocuments}
            deletingFile={deletingFile}
            onDelete={handleDeleteDocument}
          />
        </div>
      </div>
    </>
  );
}

function FileList({ title, files, deletingFile, onDelete }) {
  return (
    <div className="upload-file-list">
      <h3>{title} <span className="upload-file-count">({files.length})</span></h3>
      {files.length === 0 ? (
        <div className="upload-file-empty">None yet</div>
      ) : (
        <ul>
          {files.map((name) => (
            <li key={name} title={name}>
              <span className="upload-file-name">{name}</span>
              <button
                type="button"
                className="upload-file-delete"
                title={`Delete ${name}`}
                onClick={() => onDelete(name)}
                disabled={deletingFile === name}
              >
                {deletingFile === name ? "…" : "×"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
