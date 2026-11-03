import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, rm } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const plugin = fileURLToPath(new URL("../plugins/agentic-engineering-skills/", import.meta.url));

// Keep the runtime on an allowlisted environment: no user credentials, plugin
// settings, provider switches, proxies, or host cache paths enter the child.
function isolatedEnv(root) {
  const env = {};
  for (const key of ["PATH", "Path", "SystemRoot", "SYSTEMROOT", "WINDIR", "ComSpec", "COMSPEC", "PATHEXT", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL", "SHELL"]) {
    if (process.env[key] !== undefined) env[key] = process.env[key];
  }
  return { ...env, HOME: root, USERPROFILE: root, APPDATA: root, LOCALAPPDATA: root, TMPDIR: root, TEMP: root, TMP: root,
    XDG_CONFIG_HOME: root, XDG_CACHE_HOME: root, XDG_DATA_HOME: root, XDG_STATE_HOME: root };
}

function cliCommand(name) {
  const requested = process.env[`IMPECCABLE_TEST_${name.toUpperCase()}_CLI`];
  return requested && /\.[cm]?js$/i.test(requested) ? [process.execPath, requested] : [requested || name];
}

const claudeCommand = cliCommand("claude");
const cli = spawnSync(claudeCommand[0], [...claudeCommand.slice(1), "--version"], { encoding: "utf8", windowsHide: true, env: isolatedEnv(tmpdir()) });
const available = !cli.error && cli.status === 0;
const explicitClaude = Boolean(process.env.IMPECCABLE_TEST_CLAUDE_CLI);
const expected = [
  "agentic-engineering-skills:impeccable-asset-producer",
  "agentic-engineering-skills:impeccable-documenter",
  "agentic-engineering-skills:impeccable-finish-reviewer",
  "agentic-engineering-skills:impeccable-manual-edit-applier",
];

// The real CLI discovers the plugin; the fake API only ends its turn without
// sending credentials or prompts to an external model.
test("a fresh Claude plugin session discovers all four specialist agents", { skip: !available && !explicitClaude, timeout: 45000 }, async () => {
  assert.ok(available, `requested Claude CLI is unavailable: ${cli.stderr || cli.error?.message || cli.status}`);
  const root = await mkdtemp(path.join(tmpdir(), "impeccable-discovery-"));
  const server = createServer(async (request, response) => {
    for await (const _ of request) { /* drain */ }
    const events = [
      ["message_start", { type: "message_start", message: { id: "msg_fixture", type: "message", role: "assistant", model: "claude-sonnet-5-5", content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 1, output_tokens: 0 } } }],
      ["content_block_start", { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } }],
      ["content_block_delta", { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "ok" } }],
      ["content_block_stop", { type: "content_block_stop", index: 0 }],
      ["message_delta", { type: "message_delta", delta: { stop_reason: "end_turn", stop_sequence: null }, usage: { output_tokens: 1 } }],
      ["message_stop", { type: "message_stop" }],
    ];
    response.writeHead(200, { "content-type": "text/event-stream" });
    response.end(events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join(""));
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  try {
    const env = { ...isolatedEnv(root), CLAUDE_CONFIG_DIR: path.join(root, "config"), ANTHROPIC_BASE_URL: `http://127.0.0.1:${server.address().port}`, ANTHROPIC_API_KEY: "fixture", ANTHROPIC_AUTH_TOKEN: "fixture", DISABLE_TELEMETRY: "1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1" };
    const child = spawn(claudeCommand[0], [...claudeCommand.slice(1), "-p", "ping", "--plugin-dir", plugin, "--setting-sources", "local", "--output-format", "stream-json", "--verbose", "--model", "sonnet"], { cwd: root, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "", stderr = "";
    child.stdout.setEncoding("utf8"); child.stdout.on("data", chunk => { stdout += chunk; });
    child.stderr.setEncoding("utf8"); child.stderr.on("data", chunk => { stderr += chunk; });
    const timer = setTimeout(() => child.kill(), 30000);
    let exitCode;
    try { [exitCode] = await once(child, "close"); } finally { clearTimeout(timer); }
    assert.equal(exitCode, 0, stderr);
    const messages = stdout.split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line));
    const init = messages.find(message => message.type === "system" && message.subtype === "init");
    assert.ok(init, "Claude did not emit a session inventory");
    for (const name of expected) assert.ok(init.agents.includes(name), `plugin did not register ${name}`);
  } finally {
    server.close();
    await rm(root, { recursive: true, force: true, maxRetries: 4, retryDelay: 100 });
  }
});

const codexCommand = cliCommand("codex");
const codex = spawnSync(codexCommand[0], [...codexCommand.slice(1), "--version"], { encoding: "utf8", windowsHide: true, env: isolatedEnv(tmpdir()) });
const codexAvailable = !codex.error && codex.status === 0;
const explicitCodex = Boolean(process.env.IMPECCABLE_TEST_CODEX_CLI);

function stringsDeep(value) {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(stringsDeep);
  return value && typeof value === "object" ? Object.values(value).flatMap(stringsDeep) : [];
}

test("a generic Codex subagent receives the specialist contract in a fresh context", { skip: !codexAvailable && !explicitCodex, timeout: 45000 }, async () => {
  assert.ok(codexAvailable, `requested Codex CLI is unavailable: ${codex.stderr || codex.error?.message || codex.status}`);
  const root = await mkdtemp(path.join(tmpdir(), "impeccable-codex-"));
  const contractFile = path.join(plugin, "skills/impeccable/agents/impeccable_finish_reviewer.toml");
  // The TOML contract is provided to the generic subagent by the orchestrator.
  const { readFile, mkdir, writeFile } = await import("node:fs/promises");
  const contractToml = await readFile(contractFile, "utf8");
  const contract = contractToml.match(/developer_instructions\s*=\s*'''([\s\S]*?)'''/)?.[1];
  assert.ok(contract && contract.includes("Impeccable Finish Reviewer"));
  const marker = "PARENT_ONLY_6f489";
  let first = true, waitIssued = false, childReceivedContract = false;
  const server = createServer(async (request, response) => {
    let raw = "";
    for await (const chunk of request) raw += chunk;
    const body = JSON.parse(raw), strings = stringsDeep(body.input);
    const isChild = strings.some(value => value.includes("IMPECCABLE_FIXTURE_REVIEW"));
    if (isChild && !strings.some(value => value.includes(marker))) {
      childReceivedContract = strings.some(value => value.includes(contract));
    }
    let item;
    if (first) {
      item = { id: "fc_fixture", type: "function_call", status: "completed", namespace: "multi_agent_v1", name: "spawn_agent", call_id: "call_fixture", arguments: JSON.stringify({ message: `${contract}\nIMPECCABLE_FIXTURE_REVIEW`, fork_context: false }) };
      first = false;
    } else if (strings.some(value => value.includes(marker)) && !waitIssued) {
      // The parent's tool result names the child. Wait for it so older Codex
      // versions cannot close the child before it has started its first turn.
      const output = body.input.find(value => value.type === "function_call_output" && value.call_id === "call_fixture")?.output;
      const parsed = typeof output === "string" ? JSON.parse(output) : output;
      const id = parsed?.agent_id ?? parsed?.id;
      if (!id) throw new Error("Codex spawn result did not identify the child");
      waitIssued = true;
      item = { id: "fc_wait", type: "function_call", status: "completed", namespace: "multi_agent_v1", name: "wait_agent", call_id: "call_wait", arguments: JSON.stringify({ targets: [id], timeout_ms: 10000 }) };
    } else {
      item = { id: "msg_fixture", type: "message", role: "assistant", status: "completed", content: [{ type: "output_text", text: "fixture complete", annotations: [] }] };
    }
    const result = { id: "resp_fixture", object: "response", created_at: 1, model: "fixture", status: "completed", output: [item], usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 } };
    const events = [["response.output_item.done", { type: "response.output_item.done", output_index: 0, item }], ["response.completed", { type: "response.completed", response: result }]];
    response.writeHead(200, { "content-type": "text/event-stream" });
    response.end(events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join(""));
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  try {
    const config = path.join(root, "codex");
    await mkdir(config);
    await writeFile(path.join(config, "config.toml"), `model="fixture"\nmodel_provider="fixture"\n[model_providers.fixture]\nname="fixture"\nbase_url="http://127.0.0.1:${server.address().port}/v1"\nwire_api="responses"\nrequires_openai_auth=false\n[features]\nmulti_agent=true\n`);
    const env = { ...isolatedEnv(root), CODEX_HOME: config, OPENAI_API_KEY: "fixture", OTEL_SDK_DISABLED: "true" };
    const child = spawn(codexCommand[0], [...codexCommand.slice(1), "exec", "--skip-git-repo-check", "--ephemeral", "--json", marker], { cwd: root, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stdout.resume(); child.stderr.setEncoding("utf8"); child.stderr.on("data", chunk => { stderr += chunk; });
    const timer = setTimeout(() => child.kill(), 30000);
    let exitCode;
    try { [exitCode] = await once(child, "close"); } finally { clearTimeout(timer); }
    assert.equal(exitCode, 0, stderr);
    assert.equal(childReceivedContract, true, "specialist instructions were not sent to a fresh child");
  } finally {
    server.close();
    await rm(root, { recursive: true, force: true, maxRetries: 4, retryDelay: 100 });
  }
});
