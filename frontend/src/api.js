export const MAX_CLIENT_UPLOAD_BYTES =
  15 * 1024 * 1024;

const ALLOWED_EXTENSIONS = new Set([
  "pdf",
  "png",
  "jpg",
  "jpeg",
  "tif",
  "tiff",
]);

export function validateClientFile(file) {
  if (!file) {
    throw new Error("Choose a file first.");
  }

  const filename = String(file.name || "");
  const extension =
    filename.split(".").pop()?.toLowerCase() || "";

  if (!ALLOWED_EXTENSIONS.has(extension)) {
    throw new Error(
      "Supported formats: PDF, PNG, JPEG and TIFF.",
    );
  }

  if (file.size <= 0) {
    throw new Error(
      "The selected file is empty.",
    );
  }

  if (file.size > MAX_CLIENT_UPLOAD_BYTES) {
    throw new Error(
      "The selected file exceeds the 15 MB client limit.",
    );
  }
}

function requestIdFromPayload(payload) {
  return (
    payload?.request_id ||
    payload?.requestId ||
    null
  );
}

export async function processInvoice(
  file,
  signal,
) {
  validateClientFile(file);

  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    "/api/invoices/process",
    {
      method: "POST",
      body: formData,
      signal,
    },
  );

  let payload = null;

  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail =
      payload?.detail ||
      `Request failed with status ${response.status}.`;

    const requestId =
      requestIdFromPayload(payload);

    const suffix = requestId
      ? ` Request ID: ${requestId}`
      : "";

    throw new Error(`${detail}${suffix}`);
  }

  return payload;
}