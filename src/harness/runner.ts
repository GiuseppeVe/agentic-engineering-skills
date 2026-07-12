import { mockAgent } from "../agents/mock-agent.js";
import { plannerAgent } from "../agents/planner-agent.js";
import { reviewerAgent } from "../agents/reviewer-agent.js";
import type { AgentRegistry, HarnessResult, TaskInput, TraceEvent } from "../types.js";
import { createContextEnvelope } from "./context.js";
import { createTraceEvent } from "./observability.js";
import { routeTask } from "./router.js";
import { validateAgentOutput } from "./validator.js";

const defaultRegistry: AgentRegistry = {
  "planner-agent": plannerAgent,
  "reviewer-agent": reviewerAgent,
  "mock-agent": mockAgent
};

interface RunHarnessOptions {
  agents?: Partial<AgentRegistry>;
  taskId?: string;
}

export function runHarness(task: TaskInput, options: RunHarnessOptions = {}): HarnessResult {
  const taskId = options.taskId ?? "task-001";
  const route = routeTask(task);
  const context = createContextEnvelope(task);
  const trace: TraceEvent[] = [
    createTraceEvent("classification", { taskId, classification: route.kind }),
    createTraceEvent("route", { agentId: route.agentId, reason: route.reason }),
    createTraceEvent("context", {
      objective: context.objective,
      constraints: context.constraints,
      evidence: context.evidence,
      state: context.state,
      budget: context.budget
    })
  ];
  const agent = options.agents?.[route.agentId] ?? defaultRegistry[route.agentId];
  const validationEvents: TraceEvent[] = [];

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    trace.push(createTraceEvent("agent-invoked", { agentId: route.agentId, attempt }));
    const validation = validateAgentOutput(agent(context));
    const validationEvent = createTraceEvent("validation", {
      attempt,
      ok: validation.ok,
      reason: validation.ok ? "Validated structured output." : validation.reason
    });
    trace.push(validationEvent);
    validationEvents.push(validationEvent);

    if (validation.ok) {
      const reason = "Validated structured output.";
      trace.push(createTraceEvent("final", { status: "completed", reason }));
      return {
        taskId,
        classification: route.kind,
        route,
        agentId: route.agentId,
        context,
        output: validation.value,
        validationEvents,
        status: "completed",
        reason,
        trace
      };
    }
  }

  const reason = "Agent output remained invalid after one retry; escalated.";
  trace.push(createTraceEvent("final", { status: "escalated", reason }));
  return { taskId, classification: route.kind, route, agentId: route.agentId, context, validationEvents, status: "escalated", reason, trace };
}
