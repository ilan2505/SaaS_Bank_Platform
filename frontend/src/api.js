const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore, keep statusText
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  listBatches: () => fetch(`${API_URL}/api/batches`).then(handle),

  createBatch: (name) =>
    fetch(`${API_URL}/api/batches`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }).then(handle),

  getBatchSummary: (batchId) =>
    fetch(`${API_URL}/api/batches/${batchId}`).then(handle),

  listRecords: (batchId, { status, sourceType } = {}) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (sourceType) params.set("source_type", sourceType);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return fetch(`${API_URL}/api/batches/${batchId}/records${qs}`).then(handle);
  },

  uploadCsv: (batchId, file) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_URL}/api/batches/${batchId}/upload/csv`, {
      method: "POST",
      body: form,
    }).then(handle);
  },

  uploadPdfs: (batchId, files) => {
    const form = new FormData();
    for (const file of files) form.append("files", file);
    return fetch(`${API_URL}/api/batches/${batchId}/upload/pdf`, {
      method: "POST",
      body: form,
    }).then(handle);
  },

  getRecord: (recordId) =>
    fetch(`${API_URL}/api/records/${recordId}`).then(handle),

  getRecordErrors: (recordId) =>
    fetch(`${API_URL}/api/records/${recordId}/errors`).then(handle),

  editRecord: (recordId, patch) =>
    fetch(`${API_URL}/api/records/${recordId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }).then(handle),

  revalidateRecord: (recordId) =>
    fetch(`${API_URL}/api/records/${recordId}/revalidate`, { method: "POST" }).then(handle),

  validateRecord: (recordId) =>
    fetch(`${API_URL}/api/records/${recordId}/validate`, { method: "POST" }).then(handle),
};
