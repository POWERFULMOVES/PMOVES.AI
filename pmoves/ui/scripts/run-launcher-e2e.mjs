#!/usr/bin/env node
/**
 * Runs playwright.launcher.config.ts and then puts back the two tracked files
 * that `next dev` rewrites when it runs with a custom distDir:
 *   - tsconfig.json   (Next adds include globs for .next-e2e-*)
 *   - next-env.d.ts   (Next points the route-types import at the last distDir)
 * Without this, every local run leaves those two files modified, and the change
 * is easy to commit by accident. The exit code is Playwright's.
 *
 * Usage: npm run test:e2e:launcher [-- <extra playwright args>]
 */
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const uiRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const guarded = ['tsconfig.json', 'next-env.d.ts'].map((name) => path.join(uiRoot, name));
const snapshot = new Map(guarded.map((file) => [file, readFileSync(file)]));

let restored = false;
function restore() {
  if (restored) return;
  restored = true;
  for (const [file, original] of snapshot) {
    let current = null;
    try {
      current = readFileSync(file);
    } catch {
      // Deleted during the run: fall through and rewrite it.
    }
    if (!current || !current.equals(original)) {
      writeFileSync(file, original);
      console.log(`[run-launcher-e2e] restored ${path.relative(uiRoot, file)} (next dev had rewritten it)`);
    }
  }
}

const child = spawn(
  'npx',
  ['playwright', 'test', '-c', 'playwright.launcher.config.ts', ...process.argv.slice(2)],
  { cwd: uiRoot, stdio: 'inherit', shell: process.platform === 'win32' }
);

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal));
}

child.on('error', (err) => {
  restore();
  console.error(`[run-launcher-e2e] failed to start playwright: ${err.message}`);
  process.exit(1);
});

child.on('exit', (code, signal) => {
  restore();
  process.exit(code ?? (signal ? 1 : 0));
});
