# T3 DeepSeek routing

Apply this branch only when the owner or plan explicitly routes the complete
implementation thread to DeepSeek V4.1 Flash through Vibe. When DeepSeek is not
selected, use the normal host routing unchanged. When DeepSeek is selected but
T3 orchestration tools are unavailable, follow [Fallback](#fallback).

## Verify the compatibility bridge

Use the receiving project's reviewed bridge setup and health checks. Confirm the OpenCode server, approved model route, and credential isolation before dispatch. If the project has no verified bridge, stop and follow the owner-approved fallback procedure below.

## Resolve the target

Call `orchestrator_capabilities` before dispatch. Select an available instance
whose driver is `opencode` and whose advertised catalog contains the requested
Vibe model. Resolve the supported variant at the same time: select `high` when
advertised, otherwise record the supported effective variant and keep the
variant requirement open if it cannot be proven compliant. Pass the exact
`providerInstanceId`, model ID and selected variant to `delegate_task`. If the
instance, authentication, model or required variant is unavailable,
follow [Fallback](#fallback).

## Dispatch one implementation task

Create one fresh child per plan task with:

- the exact task instruction plus plan and spec paths in `task`, without parent
  conversation history;
- `target.providerInstanceId` and `target.model` set to the resolved values;
- `options.variant` set to the resolved variant, using `high` when supported;
- `role: implementation`;
- a runtime mode that inherits or narrows the parent's authority; and
- a stable `clientRequestId` for retries of that dispatch request.

The child invokes `task-implement`; it does not receive the plan queue or
authority to accept tasks. Record the returned `taskId`, `childThreadId`,
`providerInstanceId`, `model`, status and summary. Verify that provider and
model equal the requested target and that the recorded variant equals the
selected variant. A terminal provider state or empty summary
is not task completion; verify the shared result contract, workspace diff and
checks under the runtime protocol.

OpenCode has no automatic approval reviewer: T3 `Auto` follows `Supervised`
rules. Record the effective permission mode. Never broaden it beyond the
parent or grant remote, secret, external-directory or Git authority absent
from the task.

## Wait, review and retry

Follow the running delegate's returned next action. A wait timeout does not
cancel the child. Cancel only when required and authorized.

After implementation verification, dispatch the separate reviewer under the
runtime protocol. If a substantial in-scope correction is needed, send the
precise findings through the supported implementation handoff. After one
unsuccessful correction, follow [Fallback](#fallback).

## Fallback

Report the blocker and ask the owner whether to retry DeepSeek, switch to an
available GPT or Claude route, or leave the task blocked. Wait for the owner's
choice before switching providers.
