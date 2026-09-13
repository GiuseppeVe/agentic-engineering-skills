import { open, readFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";

const DEFAULT_MAX_FILE_BYTES = 1024 * 1024;

const nameRules = [
  ["name:environment-file", (name) => /^\.env(?:\..+)?$/i.test(name)],
  ["name:log-file", (name) => /(?:^|\.)logs?$/i.test(name)],
  ["name:generated-archive", (name) => /\.(?:zip|7z|rar|tgz|tar(?:\.(?:gz|bz2|xz))?|gz|bz2|xz)$/i.test(name)],
];

const contentRules = [
  ["secret:openai-project-key", new RegExp(`\\b${["sk", "proj"].join("-")}-[A-Za-z0-9_-]+`)],
  ["secret:anthropic-key", new RegExp(`\\b${["sk", "ant"].join("-")}-[A-Za-z0-9_-]+`)],
  ["secret:google-api-key", new RegExp(`\\b${["AI", "za"].join("")}[A-Za-z0-9_-]{20,}`)],
  ["secret:github-token", new RegExp(`\\b${["ghp", ""].join("_")}[A-Za-z0-9]{20,}`)],
  ["secret:pem-private-key", new RegExp(`${["-----BEGIN", "(?:[A-Z0-9]+ )?PRIVATE", "KEY-----"].join(" ")}`)],
  ["private-path:linux-home", /\/home\/[^/\s]+(?:\/[^\s]*)?/],
  ["private-path:windows-home", /\b[A-Za-z]:\\Users\\[^\\\s]+(?:\\[^\s]*)?/i],
  [
    "url:non-public",
    /https?:\/\/(?:localhost|127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|[^\s/:]+\.(?:internal|local|localhost))(?:[:/][^\s]*)?/i,
  ],
  [
    "legal-template:unresolved",
    /(?:\[(?:year|yyyy|fullname|copyright holder|organization)\]|<(?:year|yyyy|fullname|copyright holder|organization)>)/i,
  ],
];

const controlledLoopbackArtifacts = new Map([
  ["plugins/agentic-engineering-skills/skills/importing-handoff/references/contract-schema.md", 1],
  ["plugins/agentic-engineering-skills/skills/importing-handoff/scripts/run-reference.mjs", 2],
  ["plugins/agentic-engineering-skills/skills/graph-engineering-v5-2/scripts/graph_v5/service_supervisor.py", 1],
  ["plugins/agentic-engineering-skills/skills/graph-engineering-v5-2/tests/integration/test_local_system_journey.py", 1],
  ["plugins/agentic-engineering-skills/skills/graph-engineering-v5-2/tests/unit/test_adapter_manifest.py", 5],
  ["plugins/agentic-engineering-skills/skills/graph-engineering-v5-2/tests/unit/test_models.py", 2],
  ["plugins/agentic-engineering-skills/skills/graph-engineering-v5-2/tests/unit/test_real_admission.py", 2],
  ["plugins/agentic-engineering-skills/skills/graph-engineering-v5-2/tests/unit/test_store_integrity.py", 1],
]);

// These are public, pinned upstream examples retained inside the imported
// Impeccable package. Keep the exceptions file-specific and count-specific so
// new paths or extra matches still fail the release audit.
const controlledThirdPartyArtifacts = new Map([
  ["plugins/agentic-engineering-skills/skills/impeccable/reference/critique.md", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/reference/init.md", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/reference/live.md", { "url:non-public": 5 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/detector/cli/main.mjs", { "url:non-public": 2 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/detector/node/file-system.mjs", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-browser.js", { "url:non-public": 19 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-complete.mjs", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-copy-edit-agent.mjs", { "secret:anthropic-key": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-inject.mjs", { "url:non-public": 4 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-poll.mjs", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-server.mjs", { "url:non-public": 3 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-status.mjs", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live/sveltekit-adapter.mjs", { "url:non-public": 1 }],
]);

function hasOnlyControlledLoopbackUrls(path, content, pattern) {
  const expected = controlledLoopbackArtifacts.get(path);
  if (!expected) return false;
  const flags = pattern.flags.includes("g") ? pattern.flags : `${pattern.flags}g`;
  const matches = [...content.matchAll(new RegExp(pattern.source, flags))];
  return matches.length === expected && matches.every((match) => /^https?:\/\/(?:localhost|127(?:\.\d{1,3}){3})/i.test(match[0]));
}

function hasOnlyControlledThirdPartyMatches(path, content, rule, pattern) {
  const expected = controlledThirdPartyArtifacts.get(path)?.[rule];
  if (!expected) return false;
  const flags = pattern.flags.includes("g") ? pattern.flags : `${pattern.flags}g`;
  const matches = [...content.matchAll(new RegExp(pattern.source, flags))];
  if (matches.length !== expected) return false;
  if (rule === "url:non-public") return matches.every((match) => /^https?:\/\/(?:localhost|127(?:\.\d{1,3}){3})/i.test(match[0]));
  return rule === "secret:anthropic-key";
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exitCode = 2;
}

function parseArgs(argv) {
  let testFileList;
  let maxFileBytes = DEFAULT_MAX_FILE_BYTES;
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--test-file-list") {
      testFileList = argv[++index];
      if (!testFileList) throw new Error("--test-file-list requires a path");
    } else if (argument === "--max-file-bytes") {
      maxFileBytes = Number(argv[++index]);
      if (!Number.isSafeInteger(maxFileBytes) || maxFileBytes < 1) {
        throw new Error("--max-file-bytes requires a positive integer");
      }
    } else {
      throw new Error(`unknown argument: ${argument}`);
    }
  }
  return { testFileList, maxFileBytes };
}

function gitTrackedFiles(root) {
  const result = spawnSync("git", ["ls-files", "-z"], {
    cwd: root,
    encoding: "buffer",
    windowsHide: true,
  });
  if (result.status !== 0) {
    throw new Error("git ls-files failed; public audit requires a Git worktree");
  }
  return result.stdout
    .toString("utf8")
    .split("\0")
    .filter(Boolean)
    .map((displayPath) => ({ path: path.resolve(root, displayPath), displayPath }));
}

async function explicitTestFiles(listPath, root) {
  if (process.env.NODE_ENV !== "test") {
    throw new Error("--test-file-list is test-only");
  }
  const parsed = JSON.parse(await readFile(listPath, "utf8"));
  if (!Array.isArray(parsed) || parsed.some((entry) => typeof entry !== "string")) {
    throw new Error("test file list must be a JSON array of paths");
  }
  return parsed.map((file) => {
    const absolute = path.resolve(file);
    const relative = path.relative(root, absolute);
    const displayPath = relative && !relative.startsWith("..") && !path.isAbsolute(relative)
      ? relative
      : path.basename(absolute);
    return { path: absolute, displayPath };
  });
}

async function legalTemplateAllowedPaths(root) {
  const allowed = new Set(["LICENSE"]);
  const lockPath = path.join(root, "manifests", "skills.lock.json");
  let lock;
  try {
    lock = JSON.parse(await readFile(lockPath, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") return allowed;
    throw error;
  }
  for (const skill of lock.skills ?? []) {
    for (const license of skill.licenseFiles ?? []) {
      if (typeof license.path !== "string") continue;
      const absolute = path.resolve(root, license.path);
      const relative = path.relative(root, absolute);
      if (relative && !relative.startsWith("..") && !path.isAbsolute(relative)) {
        allowed.add(relative.split(path.sep).join("/"));
      }
    }
  }
  return allowed;
}

async function readCapped(filePath, maxFileBytes) {
  const handle = await open(filePath, "r");
  try {
    const metadata = await handle.stat();
    if (metadata.size > maxFileBytes) return { oversized: true };
    const buffer = Buffer.allocUnsafe(maxFileBytes + 1);
    const { bytesRead } = await handle.read(buffer, 0, buffer.length, 0);
    if (bytesRead > maxFileBytes) return { oversized: true };
    return { oversized: false, content: buffer.subarray(0, bytesRead).toString("utf8") };
  } finally {
    await handle.close();
  }
}

async function main() {
  const root = process.cwd();
  const { testFileList, maxFileBytes } = parseArgs(process.argv.slice(2));
  const files = testFileList
    ? await explicitTestFiles(testFileList, root)
    : gitTrackedFiles(root);
  const legalTemplateAllowed = await legalTemplateAllowedPaths(root);
  const findings = [];

  for (const file of files) {
    const basename = path.basename(file.path);
    const forbiddenName = nameRules.find(([, matches]) => matches(basename));
    if (forbiddenName) {
      findings.push(`${file.displayPath}:${forbiddenName[0]}`);
      continue;
    }

    const result = await readCapped(file.path, maxFileBytes);
    if (result.oversized) {
      findings.push(`${file.displayPath}:size:release-limit`);
      continue;
    }

    for (const [rule, pattern] of contentRules) {
      const normalizedPath = file.displayPath.split(path.sep).join("/");
      if (rule.startsWith("legal-template:") && legalTemplateAllowed.has(normalizedPath)) continue;
      if (rule === "url:non-public" && hasOnlyControlledLoopbackUrls(normalizedPath, result.content, pattern)) continue;
      if (hasOnlyControlledThirdPartyMatches(normalizedPath, result.content, rule, pattern)) continue;
      if (pattern.test(result.content)) findings.push(`${file.displayPath}:${rule}`);
    }
  }

  for (const finding of [...new Set(findings)].sort()) process.stdout.write(`${finding}\n`);
  if (findings.length > 0) process.exitCode = 1;
}

try {
  await main();
} catch (error) {
  fail(error instanceof Error ? error.message : String(error));
}
