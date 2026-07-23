import React, {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  processInvoice,
  validateClientFile,
} from "./api.js";

import {
  adaptResult,
  formatMoney,
} from "./resultAdapter.js";


function Pill({
  state,
  passText,
  failText,
  notRunText,
}) {
  const className =
    state === "pass"
      ? "success"
      : state === "fail"
        ? "danger"
        : "warning";

  const label =
    state === "pass"
      ? passText
      : state === "fail"
        ? failText
        : notRunText;

  return (
    <span
      className={`pill ${className}`}
      aria-label={label}
    >
      {label}
    </span>
  );
}


function Card({
  label,
  value,
}) {
  return (
    <div className="card">
      <p className="label">
        {label}
      </p>

      <p className="value">
        {value}
      </p>
    </div>
  );
}


export default function App() {
  const [file, setFile] =
    useState(null);

  const [raw, setRaw] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const controllerRef =
    useRef(null);

  const view = raw
    ? adaptResult(raw)
    : null;

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  function chooseFile(nextFile) {
    setRaw(null);
    setError("");

    try {
      if (nextFile) {
        validateClientFile(
          nextFile,
        );
      }

      setFile(nextFile);
    } catch (exception) {
      setFile(null);

      setError(
        exception instanceof Error
          ? exception.message
          : "The selected file is invalid.",
      );
    }
  }

  async function submit() {
    if (!file || loading) {
      return;
    }

    controllerRef.current?.abort();

    const controller =
      new AbortController();

    controllerRef.current =
      controller;

    setLoading(true);
    setError("");
    setRaw(null);

    try {
      const result =
        await processInvoice(
          file,
          controller.signal,
        );

      setRaw(result);
    } catch (exception) {
      if (
        exception instanceof Error &&
        exception.name !==
          "AbortError"
      ) {
        setError(
          exception.message,
        );
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">
          Governed document intelligence
        </p>

        <h1>
          Invoice Intelligence Agent
        </h1>

        <p className="subtitle">
          Upload an invoice to run
          extraction, validation, RAG
          verification and safety checks.
        </p>
      </header>

      <section
        className="upload-panel"
        aria-label="Invoice upload"
      >
        <input
          id="invoice-file"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff"
          disabled={loading}
          onChange={(event) =>
            chooseFile(
              event.target.files?.[0] ||
                null,
            )
          }
        />

        <label
          htmlFor="invoice-file"
          className="file-label"
        >
          Choose invoice
        </label>

        <span
          className="filename"
          title={file?.name || ""}
        >
          {file?.name ||
            "No file selected"}
        </span>

        <button
          type="button"
          disabled={!file || loading}
          onClick={submit}
        >
          {loading
            ? "Processing..."
            : "Process invoice"}
        </button>
      </section>

      {loading && (
        <div
          className="progress"
          role="status"
          aria-live="polite"
        >
          Running the governed workflow.
          This may take a few minutes.
        </div>
      )}

      {error && (
        <div
          className="callout danger-box"
          role="alert"
        >
          {error}
        </div>
      )}

      {view && (
        <>
          <div className="status-row">
            <span
              className={
                `status-badge ${
                  view.flagged
                    ? "danger"
                    : "success"
                }`
              }
            >
              {view.statusLabel}
            </span>

            <span className="meta">
              Model: {view.model}
            </span>

            <span className="meta">
              Request: {view.requestId}
            </span>
          </div>

          <div className="grid">
            <Card
              label="Vendor"
              value={view.vendor}
            />

            <Card
              label="Invoice number"
              value={
                view.invoiceNumber
              }
            />

            <Card
              label="Amount due"
              value={view.total}
            />

            <Card
              label="Average confidence"
              value={view.confidence}
            />
          </div>

          <section className="result-section">
            <p className="section-label">
              Validation and safety
            </p>

            <div className="pill-row">
              <Pill
                state={
                  view.validationState
                }
                passText="Validation passed"
                failText={
                  `${view.issues.length} validation issue(s)`
                }
                notRunText="Validation not run"
              />

              <Pill
                state={view.ragState}
                passText="Vendor verified"
                failText="Vendor not verified"
                notRunText="RAG not run"
              />

              <Pill
                state={view.inputState}
                passText="Input safety passed"
                failText="Input safety blocked"
                notRunText="Input safety not run"
              />

              <Pill
                state={
                  view.outputState
                }
                passText="Output safety passed"
                failText="Output safety blocked"
                notRunText="Output safety not run"
              />
            </div>

            {view.callout && (
              <div className="callout">
                {view.callout}
              </div>
            )}
          </section>

          {view.issues.length > 0 && (
            <section className="result-section">
              <p className="section-label">
                Validation issues
              </p>

              {view.issues.map(
                (issue, index) => (
                  <div
                    key={
                      `${issue.message}-${index}`
                    }
                    className={
                      `issue-row ${
                        issue.severity ===
                          "high"
                          ? "danger-box"
                          : "warning-box"
                      }`
                    }
                  >
                    {issue.message}
                  </div>
                ),
              )}
            </section>
          )}

          <section className="result-section">
            <p className="section-label">
              Line items (
              {view.lineItems.length})
            </p>

            {view.lineItems.length ===
            0 ? (
              <p className="muted">
                No line items were
                extracted.
              </p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>
                        Description
                      </th>

                      <th className="right">
                        Quantity
                      </th>

                      <th className="right">
                        Line total
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {view.lineItems.map(
                      (
                        item,
                        index,
                      ) => (
                        <tr
                          key={
                            `${
                              item.description ||
                              "item"
                            }-${index}`
                          }
                        >
                          <td>
                            {item.description ||
                              "Not available"}
                          </td>

                          <td className="right">
                            {item.quantity ??
                              "-"}
                          </td>

                          <td className="right">
                            {formatMoney(
                              item.line_total,
                              view.currency,
                            )}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <details className="audit">
            <summary>
              Audit trail (
              {view.audit.length})
            </summary>

            <div className="trail">
              {view.audit.length ===
              0 ? (
                <p className="muted">
                  No audit events
                  returned.
                </p>
              ) : (
                view.audit.map(
                  (
                    event,
                    index,
                  ) => (
                    <div
                      className="trail-item"
                      key={
                        `${
                          event.timestamp ||
                          event.occurred_at ||
                          "event"
                        }-${index}`
                      }
                    >
                      <strong>
                        {String(
                          event.event ||
                            event.event_type ||
                            "event",
                        ).replaceAll(
                          "_",
                          " ",
                        )}
                      </strong>

                      <span>
                        {event.timestamp ||
                          event.occurred_at ||
                          ""}
                      </span>
                    </div>
                  ),
                )
              )}
            </div>
          </details>
        </>
      )}
    </main>
  );
}