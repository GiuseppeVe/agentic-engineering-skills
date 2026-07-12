import type { TraceEvent } from "../types.js";

export function createTraceEvent(type: TraceEvent["type"], data: Record<string, unknown>): TraceEvent {
  return { type, data };
}
