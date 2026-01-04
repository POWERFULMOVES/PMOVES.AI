#!/usr/bin/env node

import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment from the pmoves/ folder (not repo root)
const pmovesRoot = path.resolve(__dirname, '..', '..');
const uiRoot = path.resolve(__dirname, '..');

const singleMode = String(process.env.SINGLE_ENV_MODE || '1') === '1';
const envCandidates = singleMode
  ? [
      path.join(pmovesRoot, 'env.shared'),
      path.join(pmovesRoot, 'env.shared.generated'),
    ]
  : [
      path.join(pmovesRoot, 'env.shared'),
      path.join(pmovesRoot, 'env.shared.generated'),
      path.join(pmovesRoot, '.env.generated'),
      path.join(pmovesRoot, '.env.local'),
      path.join(uiRoot, '.env.local'),
    ];

for (const file of envCandidates) {
  if (!fs.existsSync(file)) continue;
  dotenv.config({ path: file, override: true });
}

const [, , ...argv] = process.argv;

if (argv.length === 0) {
  console.error('Usage: node scripts/with-env.mjs <command> [args...]');
  process.exit(1);
}

const child = spawn(argv[0], argv.slice(1), {
  stdio: 'inherit',
  env: process.env,
  shell: process.platform === 'win32',
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 0);
  }
});
