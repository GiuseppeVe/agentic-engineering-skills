import type { ValidationResult } from "../types.js";

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function nonEmptyStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.length > 0 && value.every(nonEmptyString);
}

export function validateAgentOutput(candidate: unknown): ValidationResult {
  if (typeof candidate !== "object" || candidate === null) {
    return { ok: false, reason: "Output must be an object." };
  }

  const output = candidate as Record<string, unknown>;
  if (output.kind === "plan") {
    if (!nonEmptyString(output.summary)) return { ok: false, reason: "Plan summary is required." };
    if (!nonEmptyStringArray(output.actions)) return { ok: false, reason: "Plan actions are required." };
    return { ok: true, value: { kind: "plan", summary: output.summary, actions: output.actions } };
  }
  if (output.kind === "review") {
    if (output.verdict !== "pass" && output.verdict !== "fail") return { ok: false, reason: "Review verdict is required." };
    if (!nonEmptyString(output.summary)) return { ok: false, reason: "Review summary is required." };
    if (!Array.isArray(output.evidence) || !output.evidence.every(nonEmptyString)) return { ok: false, reason: "Review evidence must be strings." };
    return { ok: true, value: { kind: "review", verdict: output.verdict, summary: output.summary, evidence: output.evidence } };
  }
  if (output.kind === "unsupported" && nonEmptyString(output.reason)) {
    return { ok: true, value: { kind: "unsupported", reason: output.reason } };
  }
  return { ok: false, reason: "Unknown or malformed output kind." };
}
