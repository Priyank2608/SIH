/* CDP preview: login → dashboard, collect console errors,
   verify computed typography + paper-grain texture, take screenshots. */
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import http from 'node:http';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE = 'http://localhost:3000';
const OUT = new URL('.', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function getJson(path, method = 'GET') {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: 9222, path, method }, (res) => {
      let d = '';
      res.on('data', c => (d += c));
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(new Error(d.slice(0, 200))); } });
    });
    req.on('error', reject);
    req.end();
  });
}

async function waitPort(port, tries = 40) {
  for (let i = 0; i < tries; i++) {
    try { await getJson('/json/version'); return; } catch { await sleep(500); }
  }
  throw new Error('Chrome debug port never came up');
}

class Page {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); this.console = []; this.exceptions = []; this.pageErrors = []; }
  static async connect(url) {
    const { WebSocket } = await import('ws').catch(() => ({}));
    let WSImpl;
    if (WebSocket) WSImpl = WebSocket;
    else WSImpl = (await import('node:ws')).default;
    const ws = new WSImpl(url, { perMessageDeflate: false, maxPayload: 256 * 1024 * 1024 });
    const page = new Page(ws);
    await new Promise((res, rej) => { ws.once('open', res); ws.once('error', rej); });
    ws.on('message', (raw) => {
      const msg = JSON.parse(raw.toString());
      if (msg.id && page.pending.has(msg.id)) {
        const { resolve, reject } = page.pending.get(msg.id);
        page.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      } else if (msg.method) {
        const { method, params } = msg;
        if (method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(params.type)) {
          page.console.push(params.type + ': ' + params.args.map(a => a.value ?? a.description ?? a.type).join(' ').slice(0, 300));
        } else if (method === 'Runtime.exceptionThrown') {
          page.exceptions.push((params.exceptionDetails.exception?.description || params.exceptionDetails.text || '').slice(0, 300));
        } else if (method === 'Log.entryAdded' && params.entry.level === 'error') {
          const t = params.entry.text || '';
          // Ignore favicon 404 noise
          if (!t.includes('favicon')) page.pageErrors.push((params.entry.source + ': ' + t).slice(0, 300));
        }
      }
    });
    for (const m of ['Page.enable', 'Runtime.enable', 'Log.enable', 'Network.enable']) await page.send(m);
    return page;
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); reject(new Error('CDP timeout: ' + method)); } }, 30000);
    });
  }
  async eval(expr) {
    const r = await this.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || 'eval failed');
    return r.result.value;
  }
  navigate(url) { return this.send('Page.navigate', { url }); }
  async waitFor(fnSrc, timeout = 15000, every = 400) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      try { if (await this.eval(`!!(${fnSrc})`)) return true; } catch { /* page navigating */ }
      await sleep(every);
    }
    return false;
  }
  screenshot(path, fullPage = false) {
    return this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: fullPage }).then(r => {
      writeFileSync(path, Buffer.from(r.data, 'base64'));
    });
  }
}

const report = { consoleErrors: [], exceptions: [], pageErrors: [], checks: {}, screenshots: [] };
let chrome;
try {
  chrome = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=9222',
    `--user-data-dir=${OUT}chrome-profile`, '--no-first-run', '--no-default-browser-check',
    '--window-size=1440,900', '--hide-scrollbars', 'about:blank',
  ], { stdio: 'ignore' });

  await waitPort(9222);

  // Create a new tab targeting the login page (newer Chrome requires PUT)
  let tab;
  try { tab = await getJson('/json/new?' + encodeURIComponent(BASE + '/login'), 'GET'); }
  catch { tab = await getJson('/json/new?' + encodeURIComponent(BASE + '/login'), 'PUT'); }
  const page = await Page.connect(tab.webSocketDebuggerUrl);

  /* ── 1. LOGIN PAGE ─────────────────────────────────────────── */
  await page.waitFor(`document.readyState === 'complete'`, 15000);
  await sleep(1200);
  report.checks.loginHeadline = await page.eval(`(() => {
    const el = document.querySelector('.login-headline');
    if (!el) return null;
    const cs = getComputedStyle(el);
    return { text: el.textContent.replace(/\\s+/g,' ').trim(), font: cs.fontFamily.split(',')[0], size: cs.fontSize, weight: cs.fontWeight, spacing: cs.letterSpacing, color: cs.color };
  })()`);
  report.checks.loginTexture = await page.eval(`(() => {
    const el = document.querySelector('.login-right');
    const cs = el ? getComputedStyle(el) : null;
    return cs ? { hasGrain: (cs.backgroundImage || '').includes('radial-gradient'), bg: cs.backgroundColor } : null;
  })()`);
  report.checks.fontsLoaded = await page.eval(`Promise.all([
    document.fonts.load("600 14px 'IBM Plex Sans'"),
    document.fonts.load("500 12px 'IBM Plex Mono'"),
  ]).then(() => ({
    plexSans: document.fonts.check("600 14px 'IBM Plex Sans'"),
    plexMono: document.fonts.check("500 12px 'IBM Plex Mono'"),
  }))`);
  await page.screenshot(OUT + '01-login.png');
  report.screenshots.push('01-login.png');

  /* ── 2. LOGIN FLOW ─────────────────────────────────────────── */
  const filled = await page.eval(`(() => {
    const u = document.getElementById('login-username');
    const p = document.getElementById('login-password');
    if (!u || !p) return false;
    // Use native setter so React's value tracker registers the change
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    const set = (el, v) => {
      setter.call(el, v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    };
    set(u, 'officer'); set(p, 'BidShield@123');
    return true;
  })()`);
  if (!filled) throw new Error('Login fields not found');
  await sleep(250);
  await page.eval(`document.querySelector('.login-submit-btn').click()`);
  const onDashboard = await page.waitFor(`window.location.pathname === '/' && !!document.querySelector('.metric-value')`, 20000);
  if (!onDashboard) {
    const alertText = await page.eval(`document.querySelector('.alert')?.textContent?.trim() || null`).catch(() => null);
    throw new Error('Did not reach dashboard. URL: ' + (await page.eval('location.href')) + ' · alert: ' + (alertText || 'none'));
  }

  /* ── 3. DASHBOARD ──────────────────────────────────────────── */
  // Wait until metrics actually resolve (not "…")
  await page.waitFor(`document.querySelector('.metric-value') && document.querySelector('.metric-value').textContent.trim() !== '…'`, 15000);
  await page.waitFor(`!!document.querySelector('.data-table tbody tr')`, 15000);
  await sleep(900);

  report.checks.pageTitle = await page.eval(`document.querySelector('.page-title')?.textContent`);
  report.checks.metrics = await page.eval(`Array.from(document.querySelectorAll('.metric-cell')).map(c => ({
    label: c.querySelector('.metric-label')?.textContent,
    value: c.querySelector('.metric-value')?.textContent,
  }))`);
  report.checks.tableRows = await page.eval(`document.querySelectorAll('.data-table tbody tr').length`);
  report.checks.typography = await page.eval(`(() => {
    const pick = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { font: cs.fontFamily.split(',')[0].replace(/"/g,''), size: parseFloat(cs.fontSize) + 'px', weight: cs.fontWeight, spacing: cs.letterSpacing };
    };
    return {
      body: pick('body'), pageTitle: pick('.page-title'), pageDesc: pick('.page-desc'),
      sectionTitle: pick('.section-title'), metricValue: pick('.metric-value'),
      metricLabel: pick('.metric-label'), th: pick('.data-table th'), td: pick('.data-table td'),
      btnPrimary: pick('.btn-primary'), brand: pick('.rail-brand-name'),
    };
  })()`);
  report.checks.texture = await page.eval(`(() => {
    const b = getComputedStyle(document.body);
    const card = document.querySelector('.card');
    return {
      bodyGrain: (b.backgroundImage || '').includes('radial-gradient'),
      bodyAttachment: b.backgroundAttachment,
      cardGrain: card ? (getComputedStyle(card).backgroundImage || '').includes('radial-gradient') : false,
    };
  })()`);
  await page.screenshot(OUT + '02-dashboard-viewport.png');
  report.screenshots.push('02-dashboard-viewport.png');
  await page.screenshot(OUT + '03-dashboard-full.png', true);
  report.screenshots.push('03-dashboard-full.png');

  /* ── 4. CONSOLE / ERROR COLLECTION ─────────────────────────── */
  report.consoleErrors = page.console;
  report.exceptions = page.exceptions;
  report.pageErrors = page.pageErrors;
} catch (e) {
  report.fatal = String(e.message || e);
} finally {
  try { chrome && chrome.kill(); } catch {}
}

writeFileSync(OUT + 'report.json', JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
process.exit(report.fatal ? 1 : 0);
