#!/usr/bin/env node
/**
 * Fails if a tracked AGENTS.md or CLAUDE.md contains the block Next.js
 * generates on `next dev` (agentRules). The repo follows the AGENTS.md
 * convention, so those filenames are legitimate anywhere; what must never be
 * committed is Next's vendor block, which coding-agent sessions would load as
 * project instructions. next.config.mjs sets agentRules: false; this guards
 * against a copy generated before that, or by another Next app.
 *
 * Detects the current marker and the legacy one. Next's generated CLAUDE.md
 * is only the line `@AGENTS.md`, which is indistinguishable from a
 * hand-written pointer and harmless alone, so it is not flagged; the AGENTS.md
 * it points to is.
 *
 * Usage:
 *   node scripts/check-agent-rules.mjs                 # every tracked file (git ls-files)
 *   node scripts/check-agent-rules.mjs --files a b ... # explicit files (tests)
 * Exit: 0 clean, 1 generated block found, 3 could not measure.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';

const MARKERS = ['BEGIN:nextjs-agent-rules', 'NEXT-AGENTS-MD-START'];

function couldNotMeasure(message) {
  console.error(`check-agent-rules: COULD-NOT-MEASURE: ${message}`);
  process.exit(3);
}

function trackedFiles() {
  try {
    const root = execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();
    const out = execFileSync('git', ['ls-files', '-z', '--', '*AGENTS.md', '*CLAUDE.md'], {
      cwd: root,
      encoding: 'utf8',
    });
    return out
      .split('\0')
      .filter(Boolean)
      .map((file) => path.join(root, file));
  } catch (err) {
    return couldNotMeasure(`git ls-files failed: ${err.message}`);
  }
}

const args = process.argv.slice(2);
const files = args[0] === '--files' ? args.slice(1) : trackedFiles();
if (files.length === 0) couldNotMeasure('no AGENTS.md or CLAUDE.md files to scan (empty input is not a pass)');

const findings = [];
for (const file of files) {
  let text;
  try {
    text = readFileSync(file, 'utf8');
  } catch (err) {
    couldNotMeasure(`cannot read ${file}: ${err.message}`);
  }
  for (const marker of MARKERS) {
    if (text.includes(marker)) findings.push(`${file}: contains Next.js generated block (${marker})`);
  }
}

console.log(`check-agent-rules: scanned ${files.length} AGENTS.md/CLAUDE.md file(s), ${findings.length} finding(s)`);
if (findings.length > 0) {
  for (const finding of findings) console.error(`  ${finding}`);
  console.error('Remove the generated block (or the whole file if Next created it). next.config.mjs keeps agentRules: false.');
  process.exit(1);
}
