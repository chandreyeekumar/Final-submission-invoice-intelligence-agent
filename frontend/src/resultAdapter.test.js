import { describe, expect, it } from "vitest";
import {
  adaptResult,
  formatMoney,
} from "./resultAdapter.js";

describe("result adapter", () => {
  it("keeps skipped checks in not_run state", () => {
    const view = adaptResult({
      final_status: "safety_blocked",
      input_safety: {
        expected_action: "block",
      },
      audit_events: [],
    });

    expect(view.inputState).toBe("fail");
    expect(view.validationState).toBe("not_run");
    expect(view.ragState).toBe("not_run");
    expect(view.outputState).toBe("not_run");
  });

  it("marks a completed clean result as passed", () => {
    const view = adaptResult({
      request_id: "R1",
      final_status: "completed",
      extraction: {
        vendor_name: "A",
        total: 10,
        currency: "USD",
      },
      validation_issues: [],
      rag: {
        status: "verified",
      },
      input_safety: {
        expected_action: "allow",
      },
      output_safety: {
        expected_action: "allow",
      },
      confidence: {
        total: 0.9,
      },
      audit_events: [],
    });

    expect(view.validationState).toBe("pass");
    expect(view.ragState).toBe("pass");
    expect(view.outputState).toBe("pass");
    expect(view.confidence).toBe("90%");
    expect(view.requestId).toBe("R1");
  });

  it("falls back for invalid currency", () => {
    expect(
      formatMoney(12.5, "INVALID"),
    ).toBe("INVALID 12.50");
  });
});