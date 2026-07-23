const REVIEW_STATUSES = new Set([
  "human_review",
  "flagged",
  "review",
  "failed",
  "blocked",
  "safety_blocked",
]);

function text(
  value,
  fallback = "Not available",
) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return fallback;
  }

  return String(value);
}

export function formatMoney(
  value,
  currency = "USD",
) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return text(value);
  }

  const safeCurrency =
    String(currency || "USD").toUpperCase();

  try {
    return new Intl.NumberFormat(
      "en-US",
      {
        style: "currency",
        currency: safeCurrency,
        minimumFractionDigits: 2,
      },
    ).format(number);
  } catch {
    return `${safeCurrency} ${number.toFixed(2)}`;
  }
}

function percentage(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "Not available";
  }

  const normalized =
    number > 1
      ? number
      : number * 100;

  return `${Math.round(normalized)}%`;
}

function checkState(
  value,
  passPredicate,
) {
  if (
    value === null ||
    value === undefined
  ) {
    return "not_run";
  }

  return passPredicate(value)
    ? "pass"
    : "fail";
}

function issueToView(issue) {
  if (
    issue === null ||
    issue === undefined
  ) {
    return {
      message: "Unknown validation issue",
      severity: "warning",
    };
  }

  if (typeof issue === "string") {
    return {
      message: issue,
      severity: "warning",
    };
  }

  return {
    message:
      issue.message ||
      String(
        issue.code ||
          "Validation issue",
      ),
    severity: String(
      issue.severity || "warning",
    ).toLowerCase(),
  };
}

export function adaptResult(result) {
  const extraction =
    result?.extraction || {};

  const confidenceValues = Object.values(
    result?.confidence || {},
  )
    .map(Number)
    .filter(Number.isFinite);

  const averageConfidence =
    confidenceValues.length > 0
      ? confidenceValues.reduce(
          (sum, value) => sum + value,
          0,
        ) / confidenceValues.length
      : null;

  const status = String(
    result?.final_status || "unknown",
  ).toLowerCase();

  const flagged =
    REVIEW_STATUSES.has(status);

  const inputState = checkState(
    result?.input_safety,
    (value) =>
      String(
        value.expected_action || "",
      ).toLowerCase() !== "block",
  );

  const ragState = checkState(
    result?.rag,
    (value) =>
      String(
        value.status || "",
      ).toLowerCase() === "verified",
  );

  const outputState = checkState(
    result?.output_safety,
    (value) =>
      String(
        value.expected_action || "",
      ).toLowerCase() !== "block",
  );

  const validationIssues = Array.isArray(
    result?.validation_issues,
  )
    ? result.validation_issues
    : [];

  const validationState =
    result?.extraction
      ? validationIssues.length > 0
        ? "fail"
        : "pass"
      : "not_run";

  let callout = null;

  if (
    status === "safety_blocked" ||
    inputState === "fail"
  ) {
    callout =
      "Input safety blocked this document. Later extraction or verification stages may not have run.";
  } else if (outputState === "fail") {
    callout =
      "Output safety blocked release of the extracted result.";
  } else if (status === "failed") {
    callout =
      "Processing failed. Use the request ID when reviewing server logs.";
  } else if (flagged) {
    callout =
      "This invoice requires human review before downstream use.";
  }

  let statusLabel = "Completed";

  if (status === "safety_blocked") {
    statusLabel =
      "Blocked by safety controls";
  } else if (status === "failed") {
    statusLabel =
      "Processing failed";
  } else if (flagged) {
    statusLabel =
      "Flagged for review";
  } else if (
    status !== "completed"
  ) {
    statusLabel = text(
      status.replaceAll("_", " "),
      "Unknown status",
    );
  }

  return {
    requestId: text(
      result?.request_id,
    ),

    flagged,

    statusLabel,

    model:
      result?.model_used ||
      "Not run",

    vendor: text(
      extraction.vendor_name,
    ),

    invoiceNumber: text(
      extraction.invoice_number,
    ),

    total: formatMoney(
      extraction.amount_due ??
        extraction.total,
      extraction.currency || "USD",
    ),

    confidence:
      averageConfidence === null
        ? "Not available"
        : percentage(
            averageConfidence,
          ),

    currency:
      extraction.currency || "USD",

    lineItems: Array.isArray(
      extraction.line_items,
    )
      ? extraction.line_items
      : [],

    issues:
      validationIssues.map(
        issueToView,
      ),

    validationState,
    ragState,
    inputState,
    outputState,
    callout,

    audit: Array.isArray(
      result?.audit_events,
    )
      ? result.audit_events
      : [],
  };
}