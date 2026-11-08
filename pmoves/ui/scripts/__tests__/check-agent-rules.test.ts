/**
 * @jest-environment node
 */
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const SCRIPT = path.resolve(__dirname, '..', 'check-agent-rules.mjs');

function run(args: string[]) {
  const result = spawnSync(process.execPath, [SCRIPT, ...args], { encoding: 'utf8' });
  return { status: result.status, out: `${result.stdout}${result.stderr}` };
}

function fixture(name: string, body: string): string {
  const dir = mkdtempSync(path.join(tmpdir(), 'agent-rules-'));
  const file = path.join(dir, name);
  writeFileSync(file, body);
  return file;
}

describe('check-agent-rules (no Next.js generated block in tracked AGENTS.md / CLAUDE.md)', () => {
  it('fails on an AGENTS.md carrying the current Next marker', () => {
    const file = fixture(
      'AGENTS.md',
      '<!-- BEGIN:nextjs-agent-rules -->\n# This is NOT the Next.js you know\n<!-- END:nextjs-agent-rules -->\n'
    );
    const { status, out } = run(['--files', file]);
    expect(status).toBe(1);
    expect(out).toContain('scanned 1 AGENTS.md/CLAUDE.md file(s), 1 finding(s)');
  });

  it('fails on the legacy marker too', () => {
    const file = fixture('CLAUDE.md', '<!-- NEXT-AGENTS-MD-START -->\nrules\n<!-- NEXT-AGENTS-MD-END -->\n');
    expect(run(['--files', file]).status).toBe(1);
  });

  it('passes a hand-written AGENTS.md and a CLAUDE.md pointer', () => {
    const agents = fixture('AGENTS.md', '# Project agents\nRun `npm test` before a PR.\n');
    const claude = fixture('CLAUDE.md', '@AGENTS.md\n');
    const { status, out } = run(['--files', agents, claude]);
    expect(status).toBe(0);
    expect(out).toContain('scanned 2 AGENTS.md/CLAUDE.md file(s), 0 finding(s)');
  });

  it('passes on the real tracked files, and scans more than zero of them', () => {
    const { status, out } = run([]);
    expect(out).toMatch(/scanned [1-9]\d* AGENTS\.md\/CLAUDE\.md file\(s\), 0 finding\(s\)/);
    expect(status).toBe(0);
  });

  it('reports could-not-measure (3), not a pass, for an unreadable file', () => {
    expect(run(['--files', path.join(tmpdir(), 'does-not-exist', 'AGENTS.md')]).status).toBe(3);
  });
});
