import { describe, expect, it } from "vitest";
import {
  MAX_CLIENT_UPLOAD_BYTES,
  validateClientFile,
} from "./api.js";

describe("client file validation", () => {
  it("accepts a non-empty PDF", () => {
    const file = new File(
      ["x"],
      "invoice.pdf",
      { type: "application/pdf" },
    );

    expect(() => validateClientFile(file)).not.toThrow();
  });

  it("rejects unsupported extensions", () => {
    const file = new File(
      ["x"],
      "invoice.exe",
    );

    expect(() => validateClientFile(file)).toThrow(
      /Supported formats/,
    );
  });

  it("rejects empty files", () => {
    const file = new File(
      [],
      "invoice.pdf",
    );

    expect(() => validateClientFile(file)).toThrow(
      /empty/,
    );
  });

  it("rejects files over 15 MB", () => {
    const file = {
      name: "invoice.pdf",
      size: MAX_CLIENT_UPLOAD_BYTES + 1,
    };

    expect(() => validateClientFile(file)).toThrow(
      /15 MB/,
    );
  });
});