export type TaskKind = "plan" | "review" | "unsupported";
export type AgentId = "planner-agent" | "reviewer-agent" | "mock-agent";

export interface TaskInput {
  text: string;
  constraints?: string[];
  evidence?: string[];
  state?: Record<string, unknown>;
  budget?: { maxAttempts: number };
}

export interface ContextEnvelope {
  objective: string;
  constraints: string[];
  evidence: string[];
  state: Record<string, unknown>;
  budget: { maxAttempts: number };
}

export interface PlannerOutput {
  kind: "plan";
  summary: string;
  actions: string[];
}

export interface ReviewerOutput {
  kind: "review";
  verdict: "pass" | "fail";
  summary: string;
  evidence: string[];
}

export interface UnsupportedOutput {
  kind: "unsupported";
  reason: string;
}

export type AgentOutput = PlannerOutput | ReviewerOutput | UnsupportedOutput;

export type ValidationResult =
  | { ok: true; value: AgentOutput }
  | { ok: false; reason: string };

export interface RoutingDecision {
  kind: TaskKind;
  agentId: AgentId;
  reason: string;
}

export interface TraceEvent {
  type: "classification" | "route" | "context" | "agent-invoked" | "validation" | "final";
  data: Record<string, unknown>;
}

export interface HarnessResult {
  taskId: string;
  classification: TaskKind;
  route: RoutingDecision;
  agentId: AgentId;
  context: ContextEnvelope;
  output?: AgentOutput;
  validationEvents: TraceEvent[];
  status: "completed" | "escalated";
  reason: string;
  trace: TraceEvent[];
}

export type AgentFunction = (context: ContextEnvelope) => unknown;
export type AgentRegistry = Record<AgentId, AgentFunction>;
