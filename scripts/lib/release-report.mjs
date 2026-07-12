const heading = "## Excluded skills";

function exclusions(entries) {
  return entries
    .filter(entry => entry.excluded)
    .map(entry => ({ name: entry.name, reason: entry.exclusionReason }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function renderExclusionSection(entries) {
  const excluded = exclusions(entries);
  const rows = excluded.length
    ? excluded.map(({ name, reason }) => `| \`${name}\` | ${reason} |`).join("\n")
    : "| _None_ | No requested skills excluded. |";
  return `${heading}\n\n| Skill | Objective reason |\n| --- | --- |\n${rows}\n`;
}

export function verifyExclusionSection(entries, report) {
  const section = report.match(/^## Excluded skills\s*$([\s\S]*?)(?=^##\s|(?![\s\S]))/m)?.[1] ?? "";
  const actual = [...section.matchAll(/^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$/gm)]
    .map(([, name, reason]) => ({ name, reason }))
    .sort((a, b) => a.name.localeCompare(b.name));
  const expected = exclusions(entries);
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`exclusion report mismatch: expected ${JSON.stringify(expected)}; got ${JSON.stringify(actual)}`);
  }
  return actual;
}

export function replaceExclusionSection(report, entries) {
  const replacement = renderExclusionSection(entries).trimEnd();
  const pattern = /^## Excluded skills\s*$[\s\S]*?(?=^##\s|(?![\s\S]))/m;
  if (!pattern.test(report)) throw new Error("release report missing Excluded skills section");
  return report.replace(pattern, `${replacement}\n\n`);
}
