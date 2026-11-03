import { lstat, open, readFile, realpath } from "node:fs/promises";
import { isIP } from "node:net";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { listPatchBundlePaths, loadPatchBytes, PATCH_CHUNK_POINTER_MAGIC } from "./lib/manifest.mjs";

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
  ["private-path:windows-home", /\b[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s"']+(?:[\\/]+[^\s"']*)?/i],
  [
    "url:non-public",
    /https?:\/\/[^\s"'`<>]+/gi,
  ],
  [
    "legal-template:unresolved",
    /(?:\[(?:year|yyyy|fullname|copyright holder|organization)\]|<(?:year|yyyy|fullname|copyright holder|organization)>)/i,
  ],
];

// Exact path and count plus an explicit localhost/127.0.0.0/8 authority check.
const controlledLoopbackArtifacts = new Map([
  ["manifests/patches/brainstorming.patch", 2],
  ["manifests/patches/impeccable.patch", 18],
  ["manifests/patches/ui-ux-pro-max.patch", 1],
  ["plugins/agentic-engineering-skills/skills/archify/bin/open-artifact.mjs", 1],
  ["plugins/agentic-engineering-skills/skills/brainstorming/visual-companion.md", 1],
  ["plugins/agentic-engineering-skills/skills/impeccable/reference/generate.md", 1],
  ["plugins/agentic-engineering-skills/skills/impeccable/reference/live-setup.md", 5],
  ["plugins/agentic-engineering-skills/skills/marketing-screenshots/SKILL.md", 1],
  ["plugins/agentic-engineering-skills/skills/marketing-screenshots/references/examples.md", 1],
  ["plugins/agentic-engineering-skills/skills/marketing-screenshots/references/marketing-screenshots.config.mjs.example", 1],
  ["plugins/agentic-engineering-skills/skills/marketing-screenshots/scripts/marketing-screenshots.mjs", 1],
  ["plugins/agentic-engineering-skills/skills/marketing-screenshots/tests/marketing-screenshots.test.mjs", 2],
]);

const fixtureServerUrl = ["http:/", "127.0.0.1:" + ["$", "{server.address().port}"].join("")].join("/");
const controlledTestLoopbackArtifacts = new Map([
  ["tests/impeccable-agent-discovery.test.mjs", [fixtureServerUrl, fixtureServerUrl + "/v1"]],
  ["tests/impeccable-agent-mcp.test.mjs", [fixtureServerUrl]],
]);

const controlledIpv6LoopbackArtifacts = new Map();

// One exact fixture path match; any extra or different Linux home path still fails.
const controlledSyntheticPathArtifacts = new Map([
  ["plugins/agentic-engineering-skills/skills/marketing-screenshots/tests/marketing-screenshots.test.mjs", {
    rule: "private-path:linux-home",
    count: 1,
    prefix: "/tmp/assets",
    match: ["", "home", "home--raw.png'"].join("/"),
  }],
  ["manifests/patches/ui-ux-pro-max.patch", {
    rule: "private-path:windows-home",
    count: 1,
    prefix: '@""',
    match: ["C:", "Users", "data", "config.json"].join("\\"),
  }],
]);

const controlledRemovedPrivateUrlArtifacts = new Map([
  ["manifests/patches/archify.patch", {
    count: 1,
    match: ["http:/", "git.internal:3000", "Platform", "Services", "service"].join("/"),
    section: "diff --git a/archify/references/authoring-contract.md b/archify/references/authoring-contract.md",
  }],
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
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-browser.js", { "url:non-public": 21 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-complete.mjs", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-inject.mjs", { "url:non-public": 2 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-poll.mjs", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-server.mjs", { "url:non-public": 3 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live-status.mjs", { "url:non-public": 1 }],
  ["plugins/agentic-engineering-skills/skills/impeccable/scripts/live/sveltekit-adapter.mjs", { "url:non-public": 1 }],
]);

function literalNonPublicUrlMatches(content) {
  const candidates = /https?:\/\/[^\s"'`<>]+/gi;
  const schemes = /https?:\/\//gi;
  const matches = [];
  for (const candidate of content.matchAll(candidates)) {
    if (isNonPublicUrl(candidate)) matches.push(candidate);
    for (const scheme of candidate[0].matchAll(schemes)) {
      if (scheme.index === 0) continue;
      // Classify the authority without repeatedly parsing the shared URL tail.
      const authorityStart = scheme.index + scheme[0].length;
      const separator = candidate[0].slice(authorityStart).search(/[/?#\\]/);
      const authorityEnd = separator < 0 ? candidate[0].length : authorityStart + separator;
      const authorityUrl = candidate[0].slice(scheme.index, authorityEnd);
      if (!isNonPublicUrl({ 0: authorityUrl })) continue;
      // Keep the original match and position for exact exceptions.
      const match = [candidate[0].slice(scheme.index)];
      match.index = candidate.index + scheme.index;
      matches.push(match);
    }
  }
  return matches;
}

function decodeQueryValue(value, offsets, decodePlus) {
  let decoded = "";
  const nextOffsets = [];
  let changed = false;
  for (let index = 0; index < value.length; index += 1) {
    const sourceOffset = offsets ? offsets[index] : index;
    const hex = value[index] === "%" ? value.slice(index + 1, index + 3) : "";
    if (/^[\da-f]{2}$/i.test(hex)) {
      const byte = Number.parseInt(hex, 16);
      if (byte <= 0x7f) {
        decoded += String.fromCharCode(byte);
        nextOffsets.push(sourceOffset);
        changed = true;
        index += 2;
        continue;
      }
    }
    if (decodePlus && value[index] === "+") {
      decoded += " ";
      changed = true;
    } else {
      decoded += value[index];
    }
    nextOffsets.push(sourceOffset);
  }
  return { value: decoded, offsets: nextOffsets, changed };
}

function nonPublicUrlMatches(content) {
  const matches = literalNonPublicUrlMatches(content);
  const seen = new Set(matches.map((match) => match.index));
  const candidates = /https?:\/\/[^\s"'`<>]+/gi;
  for (const candidate of content.matchAll(candidates)) {
    const text = candidate[0];
    const question = text.indexOf("?");
    if (question < 0) continue;
    const fragment = text.indexOf("#", question + 1);
    const queryEnd = fragment < 0 ? text.length : fragment;
    let segmentStart = question + 1;
    while (segmentStart <= queryEnd) {
      const ampersand = text.indexOf("&", segmentStart);
      const segmentEnd = ampersand < 0 || ampersand > queryEnd ? queryEnd : ampersand;
      const segment = text.slice(segmentStart, segmentEnd);
      const equals = segment.indexOf("=");
      const valueStart = equals >= 0 ? segmentStart + equals + 1 : segmentStart;
      const rawValue = text.slice(valueStart, segmentEnd);
      let value = rawValue;
      let offsets;
      // Inspect the literal value, then decode at most two ASCII percent-encoding layers.
      for (let pass = 0; pass <= 2; pass += 1) {
        for (const match of literalNonPublicUrlMatches(value)) {
          const rawOffset = offsets ? offsets[match.index] : match.index;
          const index = candidate.index + valueStart + rawOffset;
          if (seen.has(index)) continue;
          const recovered = [rawValue.slice(rawOffset)];
          recovered.index = index;
          recovered.recoveredFromQuery = true;
          matches.push(recovered);
          seen.add(index);
        }
        if (pass === 2 || (!value.includes("%") && (pass > 0 || !value.includes("+")))) break;
        const decoded = decodeQueryValue(value, offsets, pass === 0);
        if (!decoded.changed) break;
        value = decoded.value;
        offsets = decoded.offsets;
      }
      if (segmentEnd === queryEnd) break;
      segmentStart = segmentEnd + 1;
    }
  }
  return matches;
}

function urlAuthority(match) {
  const authorityStart = match[0].indexOf("://") + 3;
  const authority = match[0].slice(authorityStart).split(/[/?#\\]/, 1)[0];
  const hostStart = authority.lastIndexOf("@") + 1;
  const ipv6Close = authority[hostStart] === "[" ? authority.indexOf("]", hostStart) : -1;
  const protectedBracket = ipv6Close < 0 ? -1 : authorityStart + ipv6Close;
  let end = match[0].length;
  while (end > authorityStart && /[)\],.!?;]/.test(match[0][end - 1])) {
    // The bracket enclosing a literal IPv6 hostname belongs to the URL.
    if (end - 1 === protectedBracket) break;
    end -= 1;
  }
  const candidate = match[0].slice(0, end);
  try {
    const url = new URL(candidate);
    return {
      hostname: url.hostname.toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, ""),
      hasUserInfo: url.username !== "" || url.password !== "",
    };
  } catch {
    // Static loopback authorities with templated ports are still classifiable.
  }
  try {
    const schemeEnd = candidate.indexOf("://");
    if (schemeEnd < 0) throw new Error("invalid URL");
    const authority = candidate.slice(schemeEnd + 3).split(/[/?#]/, 1)[0];
    const at = authority.lastIndexOf("@");
    const hasUserInfo = at >= 0;
    const hostPort = authority.slice(at + 1);
    let host = hostPort;
    let port = "";
    if (hostPort.startsWith("[")) {
      const close = hostPort.indexOf("]");
      if (close < 0) throw new Error("invalid IPv6 authority");
      host = hostPort.slice(0, close + 1);
      port = hostPort.slice(close + 1);
    } else {
      const colon = hostPort.lastIndexOf(":");
      if (colon >= 0 && hostPort.indexOf(":") === colon) {
        host = hostPort.slice(0, colon);
        port = hostPort.slice(colon);
      }
    }
    if (!host || /[${}]/.test(host)) throw new Error("ambiguous host");
    // Dynamic port placeholders do not change hostname classification.
    if (/[${}]/.test(port)) port = ":1";
    const url = new URL(`${candidate.slice(0, schemeEnd)}://${host}${port}/`);
    return {
      hostname: url.hostname.toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, ""),
      hasUserInfo,
    };
  } catch {
    return { hostname: "<invalid>", hasUserInfo: true };
  }
}

function isNonPublicUrl(match) {
  const { hostname } = urlAuthority(match);
  if (!hostname) return false;
  if (hostname === "localhost" || /\.(?:internal|local|localhost)$/.test(hostname)) return true;

  if (isIP(hostname) === 4) {
    const octets = hostname.split(".").map(Number);
    if (octets.length !== 4) return false;
    const [first, second] = octets;
    return first === 0
      || first === 10
      || first === 127
      || (first === 169 && second === 254)
      || (first === 172 && second >= 16 && second <= 31)
      || (first === 192 && second === 168)
      || (first === 100 && second >= 64 && second <= 127);
  }

  if (isIP(hostname) !== 6) return false;
  if (hostname === "::" || hostname === "::1" || /^(?:fc|fd)/.test(hostname)) return true;
  const firstHextet = Number.parseInt(hostname.split(":", 1)[0], 16);
  if (firstHextet >= 0xfe80 && firstHextet <= 0xfebf) return true;
  const mapped = hostname.match(/^::ffff:([\da-f]{1,4}):([\da-f]{1,4})$/i);
  if (!mapped) return false;
  const high = Number.parseInt(mapped[1], 16);
  const low = Number.parseInt(mapped[2], 16);
  const ipv4 = `${high >>> 8}.${high & 255}.${low >>> 8}.${low & 255}`;
  return isNonPublicUrl({ 0: `http://${ipv4}` });
}

function hasOnlyControlledLoopbackUrls(path, content) {
  const expected = controlledLoopbackArtifacts.get(path);
  if (!expected) return false;
  const matches = nonPublicUrlMatches(content);
  const ipv6Expected = controlledIpv6LoopbackArtifacts.get(path) ?? 0;
  if (matches.length !== expected + ipv6Expected) return false;
  const ipv6Matches = matches.filter(isControlledIpv6LoopbackUrl);
  return ipv6Matches.length === ipv6Expected
    && matches.every((match) => isLoopbackUrl(match) || isControlledIpv6LoopbackUrl(match));
}

function hasOnlyControlledTestLoopbackUrls(path, content) {
  const expected = controlledTestLoopbackArtifacts.get(path);
  if (!expected) return false;
  const matches = nonPublicUrlMatches(content);
  if (matches.length !== expected.length) return false;
  const urls = matches.map((match) => match[0]).sort();
  return [...expected].sort().every((url, index) => urls[index] === url);
}

function isLoopbackUrl(match) {
  const { hostname, hasUserInfo } = urlAuthority(match);
  if (!hostname || hasUserInfo) return false;
  if (hostname === "localhost") return true;
  return isIP(hostname) === 4 && Number(hostname.split(".")[0]) === 127;
}

function isControlledIpv6LoopbackUrl(match) {
  const { hostname, hasUserInfo } = urlAuthority(match);
  return !hasUserInfo && hostname === "::1";
}

function hasOnlyControlledSyntheticPath(path, content, rule, pattern) {
  const expected = controlledSyntheticPathArtifacts.get(path);
  if (!expected || expected.rule !== rule) return false;
  const flags = pattern.flags.includes("g") ? pattern.flags : `${pattern.flags}g`;
  const matches = [...content.matchAll(new RegExp(pattern.source, flags))];
  if (matches.length !== expected.count) return false;
  return matches.every((match) => match[0] === expected.match
    && content.slice(match.index - expected.prefix.length, match.index) === expected.prefix);
}

function hasOnlyControlledRemovedPrivateUrls(path, content, rule) {
  if (rule !== "url:non-public") return false;
  const expected = controlledRemovedPrivateUrlArtifacts.get(path);
  if (!expected) return false;
  const matches = nonPublicUrlMatches(content);
  if (matches.length !== expected.count) return false;
  return matches.every((match) => {
    if (match[0] !== expected.match) return false;
    const lineStart = content.lastIndexOf("\n", match.index) + 1;
    if (content[lineStart] !== "-") return false;
    const sectionStart = content.lastIndexOf("diff --git ", match.index);
    if (sectionStart < 0) return false;
    const sectionEnd = content.indexOf("\n", sectionStart);
    const section = content.slice(sectionStart, sectionEnd < 0 ? content.length : sectionEnd);
    return section === expected.section;
  });
}

function hasOnlyControlledLoopbackChunk(parentPath, aggregate, chunk) {
  if (!hasOnlyControlledLoopbackUrls(parentPath, aggregate)) return false;
  const matches = nonPublicUrlMatches(chunk);
  return matches.every(isLoopbackUrl);
}

function hasOnlyControlledSyntheticChunk(parentPath, aggregate, chunk, rule, pattern) {
  if (!hasOnlyControlledSyntheticPath(parentPath, aggregate, rule, pattern)) return false;
  const expected = controlledSyntheticPathArtifacts.get(parentPath);
  const flags = pattern.flags.includes("g") ? pattern.flags : `${pattern.flags}g`;
  const matches = [...chunk.matchAll(new RegExp(pattern.source, flags))];
  return matches.every((match) => expected.match.includes(match[0]));
}

function hasOnlyControlledThirdPartyMatches(path, content, rule) {
  const expected = controlledThirdPartyArtifacts.get(path)?.[rule];
  if (!expected || rule !== "url:non-public") return false;
  const matches = nonPublicUrlMatches(content);
  if (matches.length !== expected) return false;
  return matches.every(isLoopbackUrl);
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

function isWithin(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
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
    const trustedRoot = relative && !relative.startsWith("..") && !path.isAbsolute(relative)
      ? root
      : path.dirname(absolute);
    return { path: absolute, displayPath, trustedRoot };
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

async function readCapped(filePath, maxFileBytes, trustedRoot) {
  const absoluteRoot = path.resolve(trustedRoot);
  const absoluteFile = path.resolve(filePath);
  if (!isWithin(absoluteRoot, absoluteFile)) throw new Error("public audit path escapes trusted root");
  const rootMetadata = await lstat(absoluteRoot);
  if (rootMetadata.isSymbolicLink() || !rootMetadata.isDirectory()) {
    throw new Error("public audit trusted root must be a regular directory");
  }
  const [realRoot, realFile] = await Promise.all([realpath(absoluteRoot), realpath(absoluteFile)]);
  if (!isWithin(realRoot, realFile)) throw new Error("public audit path escapes trusted root through a linked ancestor");

  const metadata = await lstat(absoluteFile);
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error("public audit requires a regular file");
  }
  if (metadata.size > maxFileBytes) return { oversized: true };
  const handle = await open(absoluteFile, "r");
  try {
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
  const trackedPaths = new Set(files.map((file) => path.resolve(file.path)));
  const legalTemplateAllowed = await legalTemplateAllowedPaths(root);
  const findings = [];
  const patchContentByPath = new Map();
  const verifiedBundleByChunkPath = new Map();

  for (const file of files.filter((candidate) => candidate.path.endsWith(".patch"))) {
    const trustedRoot = file.trustedRoot ?? root;
    const pointer = await readCapped(file.path, maxFileBytes, trustedRoot);
    if (pointer.oversized) continue;
    if (!pointer.content.startsWith("diff --git ") && !pointer.content.startsWith(PATCH_CHUNK_POINTER_MAGIC)) {
      throw new Error(`invalid patch artifact header: ${file.displayPath}`);
    }

    const bundlePaths = await listPatchBundlePaths(file.path, trustedRoot);
    const chunkPaths = bundlePaths.slice(1);
    const everyChunkTracked = chunkPaths.every((chunkPath) => trackedPaths.has(path.resolve(chunkPath)));
    if (!everyChunkTracked) findings.push(`${file.displayPath}:patch:untracked-chunk`);

    let everyChunkWithinLimit = true;
    for (const chunkPath of chunkPaths) {
      const metadata = await lstat(chunkPath);
      if (metadata.isSymbolicLink() || !metadata.isFile()) {
        throw new Error(`patch chunk must be a regular file: ${chunkPath}`);
      }
      if (metadata.size > maxFileBytes) {
        findings.push(`${path.relative(root, chunkPath)}:size:release-limit`);
        everyChunkWithinLimit = false;
      }
    }
    if (!everyChunkWithinLimit) continue;

    const content = (await loadPatchBytes(file.path, trustedRoot)).toString("utf8");
    patchContentByPath.set(path.resolve(file.path), content);
    if (chunkPaths.length > 0 && everyChunkTracked) {
      const bundle = {
        parentPath: file.displayPath.split(path.sep).join("/"),
        content,
      };
      for (const chunkPath of chunkPaths) verifiedBundleByChunkPath.set(path.resolve(chunkPath), bundle);
    }
  }

  for (const file of files) {
    const basename = path.basename(file.path);
    const forbiddenName = nameRules.find(([, matches]) => matches(basename));
    if (forbiddenName) {
      findings.push(`${file.displayPath}:${forbiddenName[0]}`);
      continue;
    }

    const result = await readCapped(file.path, maxFileBytes, file.trustedRoot ?? root);
    if (result.oversized) {
      findings.push(`${file.displayPath}:size:release-limit`);
      continue;
    }
    const absolutePath = path.resolve(file.path);
    if (file.displayPath.split(path.sep).join("/").includes(".patch.parts/")
      && !verifiedBundleByChunkPath.has(absolutePath)) {
      throw new Error(`patch chunk has no validated pointer: ${file.displayPath}`);
    }
    const content = file.path.endsWith(".patch")
      ? patchContentByPath.get(absolutePath) ?? result.content
      : result.content;
    const bundle = verifiedBundleByChunkPath.get(absolutePath);

    for (const [rule, pattern] of contentRules) {
      const normalizedPath = file.displayPath.split(path.sep).join("/");
      if (rule.startsWith("legal-template:") && legalTemplateAllowed.has(normalizedPath)) continue;
      if (rule === "url:non-public") {
        const urlMatches = nonPublicUrlMatches(content);
        if (urlMatches.length === 0) continue;
        // Query-recovered matches never qualify for fixture exceptions.
        if (urlMatches.some((match) => match.recoveredFromQuery)) {
          findings.push(file.displayPath + ":" + rule);
          continue;
        }
        if (hasOnlyControlledLoopbackUrls(normalizedPath, content)
          || hasOnlyControlledTestLoopbackUrls(normalizedPath, content)
          || hasOnlyControlledThirdPartyMatches(normalizedPath, content, rule)
          || hasOnlyControlledRemovedPrivateUrls(normalizedPath, content, rule)
          || (bundle && hasOnlyControlledLoopbackChunk(bundle.parentPath, bundle.content, content))) continue;
        findings.push(`${file.displayPath}:${rule}`);
        continue;
      }
      if (hasOnlyControlledSyntheticPath(normalizedPath, content, rule, pattern)) continue;
      if (bundle && hasOnlyControlledSyntheticChunk(bundle.parentPath, bundle.content, content, rule, pattern)) continue;
      if (hasOnlyControlledThirdPartyMatches(normalizedPath, content, rule)) continue;
      if (pattern.test(content)) findings.push(`${file.displayPath}:${rule}`);
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
