import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { chmod, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const template = path.join(root, "plugins/agentic-engineering-skills/skills/orchestrating-gemini-workers/templates/run-worker.ps1");
const powershell = process.env.GEMINI_TEST_POWERSHELL ?? (process.platform === "win32" ? "powershell.exe" : "pwsh");
const shellAvailable = spawnSync(powershell, ["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"], { windowsHide: true }).status === 0;
const briefContent = "# Worker brief\nKeep `backticks` and ${literal} intact.\n";

async function fixture(t, { worker = true } = {}) {
  const base = await mkdtemp(path.join(tmpdir(), "gemini-launcher-test-"));
  t.after(() => rm(base, { recursive: true, force: true }));
  const orchestration = path.join(base, "orchestration");
  const workspace = path.join(base, "workspace");
  const appdata = path.join(base, "appdata");
  await Promise.all([
    mkdir(path.join(orchestration, "briefs"), { recursive: true }),
    mkdir(path.join(orchestration, "reports"), { recursive: true }),
    mkdir(path.join(appdata, "npm"), { recursive: true }),
    mkdir(workspace),
  ]);
  const launcher = path.join(orchestration, "run-worker.ps1");
  const adapted = (await readFile(template, "utf8")).replaceAll("<WORKSPACE>", "workspace");
  await writeFile(launcher, adapted);
  await writeFile(path.join(orchestration, "briefs", "F01.md"), briefContent);
  await writeFile(path.join(orchestration, "reports", "F01-37.log"), "Pre-existing transcript must survive.\n");
  await writeFile(path.join(workspace, "BRIEF-F01.md"), "Pre-existing brief must survive.\n");
  await writeFile(path.join(workspace, "unrelated.txt"), "Keep this file.\n");

  if (worker) {
    const fakeWorker = path.join(base, "fake-worker.cjs");
    await writeFile(fakeWorker, `
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const args = process.argv.slice(2);
const task = args.at(-1);
const match = /Leggi AGENTS\\.md e poi (\\S+) in questa cartella\\./.exec(task);
if (!match) { console.error("worker did not receive a brief path"); process.exit(90); }
const briefName = match[1];
const briefPath = path.join(process.cwd(), briefName);
const content = fs.readFileSync(briefPath, "utf8");
const reader = spawnSync(process.env.FAKE_SHELL, ["-NoProfile", "-NonInteractive", "-Command", "[Console]::Out.Write([IO.File]::ReadAllText($env:FAKE_BRIEF))"], {
  encoding: "utf8", windowsHide: true, env: { ...process.env, FAKE_BRIEF: briefPath },
});
if (reader.status !== 0) { console.error("PowerShell reader failed: " + reader.stderr); process.exit(92); }
fs.writeFileSync(process.env.FAKE_CAPTURE, JSON.stringify({ cwd: process.cwd(), args, briefName, content, powershellContent: reader.stdout }));
fs.writeFileSync(path.join(process.cwd(), "worker-result.txt"), "Preserve worker output.\\n");
if (process.env.FAKE_BARRIER) {
  fs.writeFileSync(path.join(process.env.FAKE_BARRIER, "ready-" + process.env.FAKE_RUN_ID), "ready");
  const deadline = Date.now() + 10000;
  while (fs.readdirSync(process.env.FAKE_BARRIER).filter(name => name.startsWith("ready-")).length < 2) {
    if (Date.now() > deadline) { console.error("workers did not overlap"); process.exit(91); }
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 20);
  }
}
console.log("fake worker transcript " + process.env.FAKE_RUN_ID);
if (process.env.FAKE_STDERR === "1") console.error("fake worker diagnostic " + process.env.FAKE_RUN_ID);
process.exit(Number(process.env.FAKE_EXIT_CODE));
`);
    const command = path.join(appdata, "npm", "dsh.cmd");
    const entrypoint = process.platform === "win32"
      ? `@echo off\r\n"${process.execPath}" "${fakeWorker}" %*\r\nexit /b %errorlevel%\r\n`
      : `#!/bin/sh\nexec '${process.execPath.replaceAll("'", "'\\''")}' '${fakeWorker.replaceAll("'", "'\\''")}' "$@"\n`;
    await writeFile(command, entrypoint);
    if (process.platform !== "win32") await chmod(command, 0o755);
  }
  return { base, workspace, orchestration, appdata, launcher };
}

function launchOptions(f, { workerExit = 0, id = "single", barrier = "", stderrOutput = false } = {}) {
  return {
    encoding: "utf8",
    windowsHide: true,
    env: { ...process.env, APPDATA: f.appdata, FAKE_CAPTURE: path.join(f.base, `observation-${id}.json`), FAKE_EXIT_CODE: String(workerExit), FAKE_RUN_ID: id, FAKE_BARRIER: barrier, FAKE_SHELL: powershell, FAKE_STDERR: stderrOutput ? "1" : "0" },
    timeout: 20000,
  };
}

function launchArgs(f) {
  return ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", f.launcher, "-Model", "37", "-Brief", "F01", "-AutoApprove"];
}

function launch(f, options) {
  return spawnSync(powershell, launchArgs(f), launchOptions(f, options));
}

function launchAsync(f, options) {
  return new Promise((resolve, reject) => {
    const child = spawn(powershell, launchArgs(f), launchOptions(f, options));
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", data => { stdout += data; });
    child.stderr.setEncoding("utf8").on("data", data => { stderr += data; });
    child.on("error", reject);
    child.on("close", status => resolve({ status, stdout, stderr }));
  });
}

function reportedLog(result) {
  const match = /^log: (.+)\r?$/m.exec(result.stdout);
  assert.ok(match, `launcher did not report log path: ${result.stdout}\n${result.stderr}`);
  return match[1];
}

async function assertPreserved(f, workerRan) {
  assert.equal(await readFile(path.join(f.workspace, "BRIEF-F01.md"), "utf8"), "Pre-existing brief must survive.\n");
  assert.equal(await readFile(path.join(f.workspace, "unrelated.txt"), "utf8"), "Keep this file.\n");
  assert.equal(await readFile(path.join(f.orchestration, "reports", "F01-37.log"), "utf8"), "Pre-existing transcript must survive.\n");
  assert.deepEqual((await readdir(f.workspace)).sort(), ["BRIEF-F01.md", "unrelated.txt", ...(workerRan ? ["worker-result.txt"] : [])].sort());
  if (workerRan) assert.equal(await readFile(path.join(f.workspace, "worker-result.txt"), "utf8"), "Preserve worker output.\n");
}

for (const workerExit of [0, 17]) {
  test(`launcher preserves existing files and removes its own brief after worker exits ${workerExit}`, { skip: shellAvailable ? false : "PowerShell unavailable" }, async t => {
    const f = await fixture(t);
    const result = launch(f, { workerExit });
    assert.equal(result.error, undefined);
    assert.equal(result.status, workerExit, result.stderr);
    await assertPreserved(f, true);
    const observed = JSON.parse(await readFile(path.join(f.base, "observation-single.json"), "utf8"));
    assert.equal(observed.cwd, f.workspace);
    assert.equal(observed.content, briefContent);
    assert.equal(observed.powershellContent, briefContent);
    assert.notEqual(observed.briefName, "BRIEF-F01.md");
    assert.equal(path.basename(observed.briefName), observed.briefName);
    assert.deepEqual(observed.args.slice(0, 5), ["--profile", "headless", "--patch", path.join(f.orchestration, "dsh", "base.yml"), "--patch"]);
    assert.equal(observed.args[5], path.join(f.orchestration, "dsh", "model-37.yml"));
    const transcript = await readFile(reportedLog(result), "utf8");
    assert.match(transcript, /fake worker transcript single/);
  });
}

for (const workerExit of [0, 17]) {
  test(`worker stderr is recorded and preserves exit ${workerExit}`, { skip: shellAvailable ? false : "PowerShell unavailable" }, async t => {
    const f = await fixture(t);
    const result = launch(f, { workerExit, stderrOutput: true });
    assert.equal(result.status, workerExit, result.stderr);
    assert.match(await readFile(reportedLog(result), "utf8"), /fake worker diagnostic single/);
    await assertPreserved(f, true);
  });
}
test("launcher cleans only its own brief when the worker cannot start", { skip: shellAvailable ? false : "PowerShell unavailable" }, async t => {
  const f = await fixture(t, { worker: false });
  const result = launch(f);
  assert.equal(result.error, undefined);
  assert.notEqual(result.status, 0);
  assert.ok(await readFile(reportedLog(result), "utf8").then(() => true));
  await assertPreserved(f, false);
});

test("launcher preserves a prior transcript and uses a new log for each overlapping run", { skip: shellAvailable ? false : "PowerShell unavailable" }, async t => {
  const f = await fixture(t);
  const barrier = path.join(f.base, "barrier");
  await mkdir(barrier);
  const results = await Promise.all(["first", "second"].map(id => launchAsync(f, { id, barrier })));
  for (const result of results) assert.equal(result.status, 0, result.stderr);
  assert.equal(await readFile(path.join(f.orchestration, "reports", "F01-37.log"), "utf8"), "Pre-existing transcript must survive.\n");
  const logs = results.map(reportedLog);
  assert.notEqual(logs[0], logs[1]);
  const [first, second] = await Promise.all(logs.map(log => readFile(log, "utf8")));
  assert.match(first, /fake worker transcript first/);
  assert.doesNotMatch(first, /fake worker transcript second/);
  assert.match(second, /fake worker transcript second/);
  assert.doesNotMatch(second, /fake worker transcript first/);
  const [firstRun, secondRun] = await Promise.all(["first", "second"].map(id => readFile(path.join(f.base, `observation-${id}.json`), "utf8").then(JSON.parse)));
  assert.notEqual(firstRun.briefName, secondRun.briefName);
  assert.equal(firstRun.content, briefContent);
  assert.equal(secondRun.content, briefContent);
  assert.equal(firstRun.powershellContent, briefContent);
  assert.equal(secondRun.powershellContent, briefContent);
  await assertPreserved(f, true);
});
