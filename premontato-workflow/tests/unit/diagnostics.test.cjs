'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { createDiagnostics } = require('../../plugin/updater');

async function fixture(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'premontato-diagnostics-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  return createDiagnostics({ logPath: path.join(root, 'diagnostics.jsonl'), appVersion: '0.3.1', platform: 'win32', release: '10.0.1' });
}

test('preview includes only allowlisted technical details and redacts paths and token-like strings', async t => {
  const diagnostics = await fixture(t);
  const error = new Error('private transcript C:\\Users\\Marta\\Videos\\scene 01.mov github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789');
  await diagnostics.record('operation_failed', { operation: 'analyze', error, mediaName: 'secret.mov', scriptText: 'private dialogue' });
  const report = await diagnostics.preview();
  assert.match(report.body, /Versione: 0\.3\.1/);
  assert.match(report.body, /operation_failed · analyze/);
  assert.doesNotMatch(report.body, /C:\\Users|Marta|scene 01|secret\.mov|private dialogue|github_pat_/i);
});

test('preview is bounded to the latest 200 events and 64 KiB', async t => {
  const diagnostics = await fixture(t);
  for (let i = 0; i < 230; i++) await diagnostics.record('operation_failed', { operation: 'analyze', error: Object.assign(new Error('x'.repeat(1000)), { stack: `Error\n    at frame${i} (C:\\Users\\Marta\\app.js:${i}:1)` }) });
  const report = await diagnostics.preview();
  assert.ok(Buffer.byteLength(report.body, 'utf8') <= 64 * 1024);
  assert.match(report.body, /frame229/);
  assert.doesNotMatch(report.body, /frame0\b/);
});

test('clear removes stored events from the next preview', async t => {
  const diagnostics = await fixture(t);
  await diagnostics.record('application_started');
  await diagnostics.clear();
  assert.doesNotMatch((await diagnostics.preview()).body, /application_started/);
});
