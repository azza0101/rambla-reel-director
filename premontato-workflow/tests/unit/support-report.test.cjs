'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { createGithubIssue } = require('../../plugin/updater');

function makeRunner({ authStatus = 0, issueOutput = 'https://github.com/azza0101/rambla-reel-director/issues/77\n', issueStatus = 0 } = {}) {
  const calls = [];
  const run = async (executable, args, options = {}) => {
    calls.push({ executable, args, options });
    if (args[0] === 'auth') return { status: authStatus, stdout: '', stderr: 'token gho_secret must not leak' };
    const bodyIndex = args.indexOf('--body-file');
    calls.at(-1).body = await fs.readFile(args[bodyIndex + 1], 'utf8');
    return { status: issueStatus, stdout: issueOutput, stderr: 'private cli error' };
  };
  return { run, calls };
}

function report() { return { reportId: '12345678-1234-1234-1234-123456789abc', title: '[Premontato debug] 0.3.1 · 2026-10-23', body: '# Segnalazione diagnostica Premontato\nDiagnostica filtrata', createdAt: '2026-10-23T10:00:00.000Z' }; }

test('creates issue only after explicit confirmation and never puts a token in command arguments', async t => {
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'premontato-support-'));
  t.after(() => fs.rm(tempDir, { recursive: true, force: true }));
  const { run, calls } = makeRunner();
  const url = await createGithubIssue(report(), { confirmed: true, expectedReportId: report().reportId, run, tempDir, executable: 'gh.exe' });
  assert.equal(url, 'https://github.com/azza0101/rambla-reel-director/issues/77');
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[0].args, ['auth', 'status', '--hostname', 'github.com']);
  assert.ok(calls[1].args.includes('--label') && calls[1].args.includes('bug'));
  assert.equal(calls[1].body, '# Segnalazione diagnostica Premontato\nDiagnostica filtrata');
  assert.ok(calls.every(call => !call.args.join(' ').includes('gho_secret')));
  assert.equal((await fs.readdir(tempDir)).length, 0);
});

test('rejects missing confirmation or stale report before calling GitHub', async () => {
  let called = false;
  const run = async () => { called = true; return { status: 0, stdout: '', stderr: '' }; };
  await assert.rejects(createGithubIssue(report(), { confirmed: false, expectedReportId: report().reportId, run }), /conferma/i);
  await assert.rejects(createGithubIssue(report(), { confirmed: true, expectedReportId: 'old-report', run }), /anteprima/i);
  assert.equal(called, false);
});

test('reports missing authentication without returning CLI stderr or tokens', async () => {
  const { run } = makeRunner({ authStatus: 1 });
  await assert.rejects(createGithubIssue(report(), { confirmed: true, expectedReportId: report().reportId, run }), error => {
    assert.match(error.message, /non autenticat/i);
    assert.doesNotMatch(error.message, /gho_secret|private cli error/i);
    return true;
  });
});

test('rejects unexpected CLI output and cleans its temporary body file', async t => {
  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'premontato-support-'));
  t.after(() => fs.rm(tempDir, { recursive: true, force: true }));
  const { run } = makeRunner({ issueOutput: 'created but no trusted URL' });
  await assert.rejects(createGithubIssue(report(), { confirmed: true, expectedReportId: report().reportId, run, tempDir }), /URL.*issue/i);
  assert.equal((await fs.readdir(tempDir)).length, 0);
});
