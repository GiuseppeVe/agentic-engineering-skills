import { runHarness } from "./harness/runner.js";

const taskIndex = process.argv.indexOf("--task");
const task = taskIndex >= 0 ? process.argv[taskIndex + 1] : undefined;

if (!task) {
  console.error("Missing required --task <text>.");
  process.exitCode = 1;
} else {
  const result = runHarness({ text: task });
  console.log("classification", result.classification);
  console.log("route", JSON.stringify(result.route));
  console.log("context", JSON.stringify(result.context));
  console.log("output", JSON.stringify(result.output));
  console.log("validation", JSON.stringify(result.validationEvents));
  console.log("final trace", JSON.stringify(result.trace));
}
