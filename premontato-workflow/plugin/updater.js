'use strict';
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const os = require('node:os');
const { spawnSync, spawn } = require('node:child_process');

const REPOSITORY = 'azza0101/rambla-reel-director';
const RELEASES_URL = `https://api.github.com/repos/${REPOSITORY}/releases?per_page=100`;
const MAX_ARCHIVE_BYTES = 350 * 1024 * 1024;
const MAX_DIAGNOSTIC_EVENTS = 200;
const MAX_DIAGNOSTIC_BYTES = 64 * 1024;
const ALLOWED_DIAGNOSTIC_EVENTS = new Set(['application_started', 'operation_failed']);
const ALLOWED_OPERATIONS = new Set(['resolveSnapshot', 'selectScript', 'selectMedia', 'transcribeSelected', 'analyzeIntellisearch', 'analyze', 'cancelAnalysis', 'getReviewState', 'confirmTakes', 'createReviewTimeline', 'update', 'prepareSupportReport', 'submitSupportReport']);

function parseVersion(value) {
  if (typeof value !== 'string' || !/^\d+\.\d+\.\d+$/.test(value)) throw new Error('Versione Premontato non valida');
  return value.split('.').map(Number);
}

function safeDiagnosticText(value, maxLength = 400) {
  return String(value || '')
    .replace(/github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|Bearer\s+\S+/gi, '[redacted credential]')
    .replace(/(?:[A-Za-z]:\\|\\\\)[^\r\n"'<>|)]*/g, '[percorso locale]')
    .replace(/\/(?:Users|home|private|var|tmp|opt)\/[^\s)"']+/g, '[percorso locale]')
    .replace(/[\r\n\t]+/g, ' ')
    .slice(0, maxLength);
}

function diagnosticError(error) {
  if (!(error instanceof Error)) return { name: 'Error', frames: [] };
  const name = /^[A-Za-z][A-Za-z0-9_]{0,39}$/.test(error.name) ? error.name : 'Error';
  const frames = String(error.stack || '').split(/\r?\n/).slice(1, 9)
    .map(line => safeDiagnosticText(line.trim(), 220)).filter(Boolean);
  return { name, frames };
}

function createDiagnostics({ logPath, appVersion, platform = process.platform, release = '' }) {
  if (!logPath || !path.isAbsolute(logPath)) throw new Error('Percorso log diagnostico non valido');
  const version = safeDiagnosticText(appVersion, 40) || 'sconosciuta';
  const osInfo = `${safeDiagnosticText(platform, 20)} ${safeDiagnosticText(release, 40)}`.trim();
  async function readEvents() {
    try {
      const raw = await fsp.readFile(logPath, 'utf8');
      return raw.split(/\r?\n/).filter(Boolean).slice(-MAX_DIAGNOSTIC_EVENTS).flatMap(line => {
        try { const event = JSON.parse(line); return ALLOWED_DIAGNOSTIC_EVENTS.has(event.event) ? [event] : []; }
        catch { return []; }
      });
    } catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  }
  async function writeEvents(events) {
    let rows = events.slice(-MAX_DIAGNOSTIC_EVENTS);
    while (rows.length && Buffer.byteLength(rows.map(row => JSON.stringify(row)).join('\n') + '\n', 'utf8') > MAX_DIAGNOSTIC_BYTES) rows.shift();
    await fsp.mkdir(path.dirname(logPath), { recursive: true });
    await fsp.writeFile(logPath, rows.map(row => JSON.stringify(row)).join('\n') + (rows.length ? '\n' : ''), { encoding: 'utf8', mode: 0o600 });
  }
  return Object.freeze({
    async record(event, details = {}) {
      if (!ALLOWED_DIAGNOSTIC_EVENTS.has(event)) return false;
      const row = { at: new Date().toISOString(), event };
      if (event === 'operation_failed' && ALLOWED_OPERATIONS.has(details.operation)) {
        row.operation = details.operation;
        const info = diagnosticError(details.error);
        row.error = info.name;
        row.frames = info.frames;
      }
      const events = await readEvents(); events.push(row); await writeEvents(events); return true;
    },
    async preview() {
      const events = await readEvents();
      const lines = ['# Segnalazione diagnostica Premontato', `Versione: ${version}`, `Sistema: ${osInfo || 'sconosciuto'}`, `Data report: ${new Date().toISOString()}`, '', 'Eventi tecnici recenti (nessun copione o media allegato):'];
      for (const item of events) {
        const operation = item.operation ? ` · ${item.operation}` : '';
        lines.push(`- ${safeDiagnosticText(item.at, 30)} · ${item.event}${operation}${item.error ? ` · ${safeDiagnosticText(item.error, 40)}` : ''}`);
        for (const frame of item.frames || []) lines.push(`  ${safeDiagnosticText(frame, 220)}`);
      }
      let body = lines.join('\n');
      if (Buffer.byteLength(body, 'utf8') > MAX_DIAGNOSTIC_BYTES) body = Buffer.from(body, 'utf8').subarray(0, MAX_DIAGNOSTIC_BYTES - 64).toString('utf8') + '\n[report troncato]';
      return { reportId: crypto.randomUUID(), title: `[Premontato debug] ${version} · ${new Date().toISOString().slice(0, 10)}`, body, createdAt: new Date().toISOString() };
    },
    async clear() { await fsp.rm(logPath, { force: true }); }
  });
}

function findGhExecutable({ platform = process.platform, env = process.env, existsSync = fs.existsSync } = {}) {
  if (platform === 'win32') {
    const candidate = path.join(env.ProgramFiles || 'C:\\Program Files', 'GitHub CLI', 'gh.exe');
    if (existsSync(candidate)) return candidate;
  }
  return 'gh';
}

function runGh(executable, args, { timeout = 60000 } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { windowsHide: true, shell: false, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, GH_PROMPT: 'disabled' } });
    let stdout = '', stderr = '', finished = false;
    const timer = setTimeout(() => { child.kill(); finish({ status: null, stdout, stderr }); }, timeout);
    function finish(value) { if (finished) return; finished = true; clearTimeout(timer); resolve(value); }
    child.stdout.setEncoding('utf8').on('data', chunk => { if (stdout.length < 200000) stdout += chunk; });
    child.stderr.setEncoding('utf8').on('data', chunk => { if (stderr.length < 200000) stderr += chunk; });
    child.once('error', error => { clearTimeout(timer); reject(error); });
    child.once('close', status => finish({ status, stdout, stderr }));
  });
}

async function checkGithubCli(options = {}) {
  const executable = options.executable || findGhExecutable(options);
  try {
    const result = await (options.run || runGh)(executable, ['auth', 'status', '--hostname', 'github.com'], { timeout: 15000 });
    if (result.status !== 0) return { ready: false, message: 'GitHub CLI non autenticata. Accedi con gh auth login e riprova.' };
    return { ready: true, executable };
  } catch { return { ready: false, message: 'GitHub CLI non trovata. Installa GitHub CLI e accedi con gh auth login.' }; }
}

function validateDiagnosticReport(report) {
  if (!report || typeof report !== 'object' || !/^[a-f0-9-]{20,}$/i.test(String(report.reportId || '')) ||
      typeof report.title !== 'string' || !report.title.startsWith('[Premontato debug] ') || /[\r\n]/.test(report.title) ||
      typeof report.body !== 'string' || !report.body.startsWith('# Segnalazione diagnostica Premontato') || Buffer.byteLength(report.body, 'utf8') > MAX_DIAGNOSTIC_BYTES) {
    throw new Error('Anteprima diagnostica non valida');
  }
}

async function createGithubIssue(report, options = {}) {
  if (options.confirmed !== true) throw new Error('Conferma l’invio dopo aver letto l’anteprima');
  validateDiagnosticReport(report);
  if (options.expectedReportId !== report.reportId) throw new Error('Anteprima scaduta: riaprila prima di inviare');
  const cli = await checkGithubCli(options);
  if (!cli.ready) throw new Error(cli.message);
  const dir = await fsp.mkdtemp(path.join(options.tempDir || os.tmpdir(), 'premontato-debug-'));
  const bodyPath = path.join(dir, 'report.md');
  try {
    await fsp.writeFile(bodyPath, report.body, { encoding: 'utf8', mode: 0o600, flag: 'wx' });
    let result;
    try {
      result = await (options.run || runGh)(cli.executable, ['issue', 'create', '--repo', 'azza0101/rambla-reel-director', '--title', report.title, '--body-file', bodyPath, '--label', 'bug'], { timeout: 60000 });
    } catch { throw new Error('Impossibile creare la segnalazione GitHub; la diagnostica locale è conservata.'); }
    if (result.status !== 0) throw new Error('GitHub non ha creato la segnalazione. Verifica i permessi repo di gh auth status.');
    const issueUrl = String(result.stdout || '').trim().split(/\s+/).find(value => /^https:\/\/github\.com\/azza0101\/rambla-reel-director\/issues\/\d+\/?$/.test(value));
    if (!issueUrl) throw new Error('GitHub ha risposto senza un URL di issue verificabile.');
    return issueUrl.replace(/\/$/, '');
  } finally { await fsp.rm(dir, { recursive: true, force: true }).catch(() => {}); }
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
  const release = releases.filter(item => !item.draft && /^premontato-v\d+\.\d+\.\d+$/.test(item.tag_name || ''))
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
  loadProtectedToken, findLatestUpdate, downloadVerifiedArchive, createDiagnostics, findGhExecutable,
  checkGithubCli, createGithubIssue, validateDiagnosticReport };
