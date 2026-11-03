import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const plugin = fileURLToPath(new URL("../plugins/agentic-engineering-skills/", import.meta.url));
function isolatedEnv(root) {
  const env = {};
  for (const key of ["PATH", "Path", "SystemRoot", "SYSTEMROOT", "WINDIR", "ComSpec", "COMSPEC", "PATHEXT", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL", "SHELL"]) {
    if (process.env[key] !== undefined) env[key] = process.env[key];
  }
  return { ...env, HOME: root, USERPROFILE: root, APPDATA: root, LOCALAPPDATA: root, TMPDIR: root, TEMP: root, TMP: root,
    XDG_CONFIG_HOME: root, XDG_CACHE_HOME: root, XDG_DATA_HOME: root, XDG_STATE_HOME: root };
}
const requested = process.env.IMPECCABLE_TEST_CLAUDE_CLI;
const command = requested && /\.[cm]?js$/i.test(requested) ? [process.execPath, requested] : [requested || "claude"];
const version = spawnSync(command[0], [...command.slice(1), "--version"], { encoding: "utf8", windowsHide: true, env: isolatedEnv(tmpdir()) });
const available = !version.error && version.status === 0;

function event(name, data) { return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`; }
function reply(role, spawnAgent) {
  const events = [["message_start", { type: "message_start", message: { id: "msg_fixture", type: "message", role: "assistant", model: "claude-sonnet-5-5", content: [], stop_reason: null, stop_sequence: null, usage: { input_tokens: 1, output_tokens: 0 } } }]];
  if (spawnAgent) {
    const input = { description: "Fixture specialist", prompt: "Inspect the fixture.", subagent_type: `agentic-engineering-skills:impeccable-${role}` };
    events.push(["content_block_start", { type: "content_block_start", index: 0, content_block: { type: "tool_use", id: "toolu_fixture", name: "Agent", input: {} } }],
      ["content_block_delta", { type: "content_block_delta", index: 0, delta: { type: "input_json_delta", partial_json: JSON.stringify(input) } }],
      ["content_block_stop", { type: "content_block_stop", index: 0 }],
      ["message_delta", { type: "message_delta", delta: { stop_reason: "tool_use", stop_sequence: null }, usage: { output_tokens: 1 } }]);
  } else {
    events.push(["content_block_start", { type: "content_block_start", index: 0, content_block: { type: "text", text: "" } }],
      ["content_block_delta", { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "fixture done" } }],
      ["content_block_stop", { type: "content_block_stop", index: 0 }],
      ["message_delta", { type: "message_delta", delta: { stop_reason: "end_turn", stop_sequence: null }, usage: { output_tokens: 1 } }]);
  }
  events.push(["message_stop", { type: "message_stop" }]);
  return events.map(([name, data]) => event(name, data)).join("");
}

// This stdio MCP implements only the handshake and one inert image tool.
const fixtureMcp = `
import readline from "node:readline";
for await (const line of readline.createInterface({ input: process.stdin })) {
  const msg = JSON.parse(line);
  if (msg.id === undefined) continue;
  const result = msg.method === "initialize" ? { protocolVersion: "2025-03-26", capabilities: { tools: {} }, serverInfo: { name: "fakeimage", version: "1" } }
    : msg.method === "tools/list" ? { tools: [{ name: "generate_image", description: "Produce a fixture image", inputSchema: { type: "object", properties: {} } }] }
    : msg.method === "tools/call" ? { content: [{ type: "text", text: "fixture image" }] } : {};
  process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result }) + "\\n");
}
`;

test("Claude asset producer sees an available MCP image tool while reviewer stays read-only", { skip: !available && !requested, timeout: 70000 }, async () => {
  assert.ok(available, `requested Claude CLI unavailable: ${version.stderr || version.error?.message || version.status}`);
  const root = await mkdtemp(path.join(tmpdir(), "impeccable-mcp-"));
  const mcp = path.join(root, "fake-image.mjs"), config = path.join(root, "mcp.json");
  await writeFile(mcp, fixtureMcp);
  await writeFile(config, JSON.stringify({ mcpServers: { fakeimage: { command: process.execPath, args: [mcp] } } }));
  let currentRole = "asset-producer", count = 0, parentTools = [], childTools = [], childReady, signalChild;
  const server = createServer(async (request, response) => {
    let raw = ""; for await (const chunk of request) raw += chunk;
    const body = JSON.parse(raw), system = JSON.stringify(body.system), tools = (body.tools || []).map(tool => tool.name);
    const child = system.includes(currentRole === "asset-producer" ? "Impeccable Asset Producer" : "Impeccable Finish Reviewer");
    if (child) { childTools = tools; signalChild(); }
    else if (count === 0) parentTools = tools;
    else if (childTools.length === 0) await Promise.race([childReady, new Promise(resolve => setTimeout(resolve, 4000))]);
    response.writeHead(200, { "content-type": "text/event-stream" });
    response.end(reply(currentRole, count++ === 0));
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  try {
    for (const role of ["asset-producer", "finish-reviewer"]) {
      currentRole = role; count = 0; parentTools = []; childTools = [];
      childReady = new Promise(resolve => { signalChild = resolve; });
      const env = { ...isolatedEnv(root), CLAUDE_CONFIG_DIR: path.join(root, `config-${role}`), ANTHROPIC_BASE_URL: `http://127.0.0.1:${server.address().port}`, ANTHROPIC_API_KEY: "fixture", ANTHROPIC_AUTH_TOKEN: "fixture", DISABLE_TELEMETRY: "1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC: "1", ENABLE_TOOL_SEARCH: "false" };
      const args = [...command.slice(1), "-p", "Fixture", "--plugin-dir", plugin, "--strict-mcp-config", "--mcp-config", config, "--setting-sources", "local", "--permission-mode", "default", "--output-format", "stream-json", "--verbose", "--allowedTools", "Agent,mcp__fakeimage__generate_image", "--model", "sonnet"];
      const child = spawn(command[0], args, { cwd: root, env, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
      let stdout = "", stderr = ""; child.stdout.setEncoding("utf8"); child.stdout.on("data", chunk => { stdout += chunk; }); child.stderr.setEncoding("utf8"); child.stderr.on("data", chunk => { stderr += chunk; });
      const timer = setTimeout(() => child.kill(), 30000); let code;
      try { [code] = await once(child, "close"); } finally { clearTimeout(timer); }
      assert.equal(code, 0, stderr);
      assert.ok(parentTools.includes("mcp__fakeimage__generate_image"), "MCP fixture was not available to parent");
      if (role === "asset-producer") assert.ok(childTools.includes("mcp__fakeimage__generate_image"), `asset producer cannot see the parent image MCP tool; child tools: ${JSON.stringify(childTools)}; parent tools: ${JSON.stringify(parentTools)}; calls: ${count}; user events: ${stdout.split(/\r?\n/).filter(line => line.includes("tool_result")).join(" ").slice(0, 1500)}`);
      else assert.deepEqual(childTools.sort(), ["Glob", "Grep", "Read"], "finish reviewer gained write or MCP tools");
    }
  } finally {
    server.close(); await rm(root, { recursive: true, force: true, maxRetries: 4, retryDelay: 100 });
  }
});
