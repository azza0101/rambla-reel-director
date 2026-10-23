'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { isNewerVersion, validateReleaseManifest, resolveGithubCredentialPath, findLatestUpdate, downloadVerifiedArchive } = require('../../plugin/updater');

test('detects semantic version updates without confusing 0.10 with 0.2', () => {
  assert.equal(isNewerVersion('0.10.0', '0.2.9'), true);
  assert.equal(isNewerVersion('0.2.0', '0.2.0'), false);
  assert.equal(isNewerVersion('0.1.9', '0.2.0'), false);
  assert.throws(() => isNewerVersion('latest', '0.2.0'), /versione/i);
});

test('accepts only a versioned Premontato release manifest with a matching archive digest', () => {
  const valid = { version: '0.3.0', archive: 'Premontato-0.3.0.zip', sha256: 'a'.repeat(64) };
  assert.deepEqual(validateReleaseManifest(valid, 'premontato-v0.3.0'), valid);
  assert.throws(() => validateReleaseManifest({ ...valid, archive: '../payload.zip' }, 'premontato-v0.3.0'), /manifest/i);
  assert.throws(() => validateReleaseManifest({ ...valid, sha256: 'bad' }, 'premontato-v0.3.0'), /manifest/i);
  assert.throws(() => validateReleaseManifest(valid, 'autocut-v0.3.0'), /tag/i);
});

test('finds the existing RMBL DPAPI credential through the installed Auto-Cut runtime config', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'premontato-auth-'));
  try {
    const programData = path.join(root, 'ProgramData');
    const autoCut = path.join(programData, 'Blackmagic Design', 'DaVinci Resolve', 'Support', 'Workflow Integration Plugins', 'com.rambla.autocut');
    const appRoot = path.join(root, 'qwen-embedding-smoke', 'api-first-v5-cloud');
    const credential = path.join(root, 'qwen-embedding-smoke', 'rambla-data', 'credentials', 'github-token.dpapi');
    fs.mkdirSync(autoCut, { recursive: true });
    fs.mkdirSync(path.dirname(credential), { recursive: true });
    fs.writeFileSync(path.join(autoCut, 'runtime.json'), JSON.stringify({ app_root: appRoot }));
    fs.writeFileSync(credential, Buffer.from('dpapi-placeholder'));
    assert.equal(resolveGithubCredentialPath(programData), credential);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('does not derive a credential path from an untrusted runtime config', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'premontato-auth-'));
  try {
    const autoCut = path.join(root, 'Blackmagic Design', 'DaVinci Resolve', 'Support', 'Workflow Integration Plugins', 'com.rambla.autocut');
    fs.mkdirSync(autoCut, { recursive: true });
    fs.writeFileSync(path.join(autoCut, 'runtime.json'), JSON.stringify({ app_root: path.join(root, '..', 'outside') }));
    assert.equal(resolveGithubCredentialPath(root), null);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('finds a newer private GitHub release and downloads only its hash-matched asset', async () => {
  const token = 'github_pat_' + 'x'.repeat(48);
  const archive = Buffer.from('premontato-test-update');
  const sha256 = require('node:crypto').createHash('sha256').update(archive).digest('hex');
  const manifest = Buffer.from(JSON.stringify({ version: '0.3.0', archive: 'Premontato-0.3.0.zip', sha256 }));
  const release = { tag_name: 'premontato-v0.3.0', draft: false, prerelease: false, assets: [
    { id: 11, name: 'premontato-update.json', size: manifest.length, url: 'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/11' },
    { id: 12, name: 'Premontato-0.3.0.zip', size: archive.length, url: 'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/12' }
  ] };
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url: String(url), accept: options.headers.Accept });
    if (String(url).endsWith('/releases?per_page=100')) return new Response(JSON.stringify([release]), { status: 200 });
    if (String(url).endsWith('/assets/11')) return new Response(manifest, { status: 200 });
    if (String(url).endsWith('/assets/12')) return new Response(archive, { status: 200 });
    return new Response('', { status: 404 });
  };
  const update = await findLatestUpdate('0.2.0', token, fetchImpl);
  assert.equal(update.status, 'available');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'premontato-download-'));
  try {
    const destination = path.join(root, 'update.zip');
    await downloadVerifiedArchive(update, token, destination, fetchImpl);
    assert.deepEqual(fs.readFileSync(destination), archive);
    assert.equal(calls.filter(call => call.accept === 'application/octet-stream').length, 2);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('reports current when the latest published release is not newer', async () => {
  const release = { tag_name: 'premontato-v0.3.0', draft: false, prerelease: false, assets: [] };
  const update = await findLatestUpdate('0.3.0', 'token', async () => new Response(JSON.stringify([release]), { status: 200 }));
  assert.deepEqual(update, { status: 'current', version: '0.3.0' });
});

test('checks dedicated Premontato prereleases without considering other products', async () => {
  const archive = Buffer.from('premontato-next');
  const digest = require('node:crypto').createHash('sha256').update(archive).digest('hex');
  const manifest = Buffer.from(JSON.stringify({ version: '0.3.1', archive: 'Premontato-0.3.1.zip', sha256: digest }));
  const release = { tag_name: 'premontato-v0.3.1', draft: false, prerelease: true, assets: [
    { id: 21, name: 'premontato-update.json', size: manifest.length, url: 'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/21' },
    { id: 22, name: 'Premontato-0.3.1.zip', size: archive.length, url: 'https://api.github.com/repos/azza0101/rambla-reel-director/releases/assets/22' }
  ] };
  const other = { tag_name: 'autocut-v99.0.0', draft: false, prerelease: false, assets: [] };
  const fetchImpl = async url => {
    if (String(url).endsWith('/releases?per_page=100')) return new Response(JSON.stringify([other, release]), { status: 200 });
    if (String(url).endsWith('/assets/21')) return new Response(manifest, { status: 200 });
    if (String(url).endsWith('/assets/22')) return new Response(archive, { status: 200 });
    return new Response('', { status: 404 });
  };
  const update = await findLatestUpdate('0.3.0', 'token', fetchImpl);
  assert.equal(update.status, 'available');
  assert.equal(update.manifest.version, '0.3.1');
});
