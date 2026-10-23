'use strict';
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');

const REPOSITORY = 'azza0101/rambla-reel-director';
const RELEASES_URL = `https://api.github.com/repos/${REPOSITORY}/releases?per_page=100`;
const MAX_ARCHIVE_BYTES = 350 * 1024 * 1024;

function parseVersion(value) {
  if (typeof value !== 'string' || !/^\d+\.\d+\.\d+$/.test(value)) throw new Error('Versione Premontato non valida');
  return value.split('.').map(Number);
}

function isNewerVersion(candidate, current) {
  const a = parseVersion(candidate), b = parseVersion(current);
  for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] > b[i];
  return false;
}

function validateReleaseManifest(manifest, tag) {
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest) ||
      !/^\d+\.\d+\.\d+$/.test(String(manifest.version || '')) ||
      manifest.archive !== `Premontato-${manifest.version}.zip` ||
      !/^[a-f0-9]{64}$/.test(String(manifest.sha256 || ''))) throw new Error('Manifest aggiornamento Premontato non valido');
  if (tag !== `premontato-v${manifest.version}`) throw new Error('Tag release Premontato non corrispondente');
  return { version: manifest.version, archive: manifest.archive, sha256: manifest.sha256 };
}

function isInside(root, candidate) {
  const relative = path.relative(path.resolve(root), path.resolve(candidate));
  return relative !== '' && relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

function resolveGithubCredentialPath(programData = process.env.PROGRAMDATA) {
  if (!programData) return null;
  const autoCutRoot = path.join(programData, 'Blackmagic Design', 'DaVinci Resolve', 'Support', 'Workflow Integration Plugins', 'com.rambla.autocut');
  const configPath = path.join(autoCutRoot, 'runtime.json');
  try {
    if (fs.lstatSync(autoCutRoot).isSymbolicLink() || fs.lstatSync(configPath).isSymbolicLink()) return null;
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8').replace(/^\uFEFF/, ''));
    if (typeof config.app_root !== 'string' || !path.isAbsolute(config.app_root)) return null;
    const appRoot = path.resolve(config.app_root);
    const dataRoot = path.resolve(path.dirname(appRoot), 'rambla-data');
    if (!isInside(path.dirname(appRoot), appRoot) || !isInside(path.dirname(appRoot), dataRoot)) return null;
    const credential = path.join(dataRoot, 'credentials', 'github-token.dpapi');
    if (!isInside(dataRoot, credential) || fs.lstatSync(credential).isSymbolicLink() || !fs.statSync(credential).isFile()) return null;
    return credential;
  } catch { return null; }
}

function loadProtectedToken(credentialPath, spawn = spawnSync) {
  if (!credentialPath || !fs.existsSync(credentialPath)) throw new Error('Credenziale GitHub RMBL non trovata');
  const script = [
    "$ErrorActionPreference='Stop'",
    "$ProgressPreference='SilentlyContinue'",
    "Add-Type -AssemblyName System.Security",
    "$blob=[IO.File]::ReadAllBytes($env:PREMONTATO_DPAPI_PATH)",
    "$clear=[Security.Cryptography.ProtectedData]::Unprotect($blob,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)",
    "[Console]::Out.Write([Text.Encoding]::UTF8.GetString($clear))"
  ].join(';');
  const encoded = Buffer.from(script, 'utf16le').toString('base64');
  const result = spawn('powershell.exe', ['-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], {
    windowsHide: true, encoding: 'utf8', timeout: 15000, maxBuffer: 4096,
    env: { SYSTEMROOT: process.env.SYSTEMROOT, WINDIR: process.env.WINDIR, PREMONTATO_DPAPI_PATH: credentialPath }
  });
  if (result.error || result.status !== 0) throw new Error('Non riesco a leggere la credenziale GitHub protetta da Windows');
  const token = result.stdout;
  if (!/^github_pat_[a-zA-Z0-9_]{30,250}$/.test(token)) throw new Error('La credenziale GitHub RMBL non è un token fine-grained valido');
  return token;
}

async function githubJson(url, token, fetchImpl = globalThis.fetch) {
  const response = await fetchImpl(url, { headers: {
    Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'RAMBLA-Premontato-Updater'
  }, signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(response.status === 401 || response.status === 403
    ? 'GitHub ha rifiutato la credenziale: servono permessi di lettura sui release di rambla-reel-director'
    : `GitHub non disponibile (HTTP ${response.status})`);
  return response.json();
}

function findReleaseAsset(release, name) {
  return Array.isArray(release.assets) ? release.assets.find(asset => asset.name === name && Number(asset.size) > 0) : null;
}

async function downloadAssetBytes(asset, token, maxBytes, fetchImpl = globalThis.fetch) {
  const assetUrl = new URL(asset?.url || '');
  if (assetUrl.protocol !== 'https:' || assetUrl.hostname !== 'api.github.com' ||
      !assetUrl.pathname.startsWith(`/repos/${REPOSITORY}/releases/assets/`)) throw new Error('URL del pacchetto GitHub non valido');
  if (!Number.isFinite(Number(asset.size)) || Number(asset.size) <= 0 || Number(asset.size) > maxBytes) throw new Error('Dimensione del pacchetto non valida');
  const response = await fetchImpl(assetUrl.href, { headers: {
    Authorization: `Bearer ${token}`, Accept: 'application/octet-stream',
    'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'RAMBLA-Premontato-Updater'
  }, signal: AbortSignal.timeout(120000) });
  if (!response.ok) throw new Error(`Download aggiornamento non riuscito (HTTP ${response.status})`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length !== Number(asset.size) || bytes.length > maxBytes) throw new Error('Download aggiornamento incompleto o troppo grande');
  return bytes;
}

async function findLatestUpdate(currentVersion, token, fetchImpl = globalThis.fetch) {
  parseVersion(currentVersion);
  const releases = await githubJson(RELEASES_URL, token, fetchImpl);
  if (!Array.isArray(releases)) throw new Error('Elenco release GitHub non valido');
  const release = releases.filter(item => !item.draft && !item.prerelease && /^premontato-v\d+\.\d+\.\d+$/.test(item.tag_name || ''))
    .sort((a, b) => {
      const av = parseVersion(a.tag_name.slice('premontato-v'.length));
      const bv = parseVersion(b.tag_name.slice('premontato-v'.length));
      for (let i = 0; i < 3; i++) if (av[i] !== bv[i]) return bv[i] - av[i];
      return 0;
    })[0];
  if (!release) return { status: 'unpublished' };
  const version = release.tag_name.slice('premontato-v'.length);
  if (!isNewerVersion(version, currentVersion)) return { status: 'current', version: currentVersion };
  const manifestAsset = findReleaseAsset(release, 'premontato-update.json');
  const archiveAsset = findReleaseAsset(release, `Premontato-${version}.zip`);
  if (!manifestAsset || !archiveAsset || archiveAsset.size > MAX_ARCHIVE_BYTES) throw new Error('La release non contiene un pacchetto aggiornamento valido');
  let rawManifest;
  try { rawManifest = JSON.parse((await downloadAssetBytes(manifestAsset, token, 16 * 1024, fetchImpl)).toString('utf8')); }
  catch (error) { if (error instanceof SyntaxError) throw new Error('Manifest aggiornamento Premontato non leggibile'); throw error; }
  const manifest = validateReleaseManifest(rawManifest, release.tag_name);
  if (manifest.archive !== archiveAsset.name) throw new Error('Il pacchetto non corrisponde al manifest della release');
  return { status: 'available', release, manifest, archiveAsset };
}

async function downloadVerifiedArchive(update, token, destination, fetchImpl = globalThis.fetch) {
  if (!update || update.status !== 'available' || !update.archiveAsset?.url) throw new Error('Aggiornamento non pronto per il download');
  const bytes = await downloadAssetBytes(update.archiveAsset, token, MAX_ARCHIVE_BYTES, fetchImpl);
  const digest = crypto.createHash('sha256').update(bytes).digest('hex');
  if (digest !== update.manifest.sha256) throw new Error('SHA-256 del pacchetto aggiornamento non valido');
  await fsp.mkdir(path.dirname(destination), { recursive: true });
  await fsp.writeFile(destination, bytes, { flag: 'wx' });
  return destination;
}

module.exports = { MAX_ARCHIVE_BYTES, isNewerVersion, validateReleaseManifest, resolveGithubCredentialPath,
  loadProtectedToken, findLatestUpdate, downloadVerifiedArchive };
