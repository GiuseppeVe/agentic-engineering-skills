import { spawn } from "node:child_process";
import { parseTestSummary, testRunFailure } from "./lib/runner-summary.mjs";

const child = spawn(process.execPath, ["--test", ...process.argv.slice(2)], {
  cwd: process.cwd(),
  env: process.env,
  stdio: ["inherit", "pipe", "pipe"],
});

let output = "";
for (const [stream, destination] of [[child.stdout, process.stdout], [child.stderr, process.stderr]]) {
  stream.on("data", chunk => {
    output += chunk.toString();
    destination.write(chunk);
  });
}

child.on("error", error => {
  console.error(`Failed to start Node test runner: ${error.message}`);
  process.exitCode = 1;
});

child.on("close", (exitCode, signal) => {
  const failure = testRunFailure({ exitCode, signal, summary: parseTestSummary(output) });
  if (failure) {
    console.error(`Test guard failed: ${failure}`);
    process.exitCode = 1;
  }
});
