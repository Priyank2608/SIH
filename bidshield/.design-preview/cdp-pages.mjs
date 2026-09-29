/* CDP page sweep: login once, then verify /tenders, /verification, /reports —
   computed typography, texture, content, console errors, screenshots. */
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import http from 'node:http';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE = 'http://localhost:3000';
const OUT = decodeURIComponent(new URL('.', import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1');
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
    const { WebSocket } = await import('ws');
    const ws = new WebSocket(url, { perMessageDeflate: false, maxPayload: 256 * 1024 * 1024 });
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

/* Per-page wait conditions so each page gets past its skeletons */
const PAGE_CONFIG = [
  {
    name: 'tenders', path: '/tenders', shot: '04-tenders.png', full: true,
    ready: `document.querySelectorAll('.data-table tbody tr').length > 0 || !!document.querySelector('.state-wrapper')`,
    probe: {
      pageTitle: `document.querySelector('.page-title')?.textContent`,
      tableRows: `document.querySelectorAll('.data-table tbody tr').length`,
      filterPills: `Array.from(document.querySelectorAll('.filter-pill, .scenario-pill')).map(p => p.textContent.trim()).slice(0, 8)`,
    },
  },
  {
    name: 'verification', path: '/verification', shot: '05-verification.png', full: true,
    ready: `!!document.querySelector('.page-title') && (document.querySelectorAll('.data-table tbody tr').length > 0 || !!document.querySelector('.state-wrapper') || document.querySelectorAll('.workspace-tab').length > 0)`,
    probe: {
      pageTitle: `document.querySelector('.page-title')?.textContent`,
      tabs: `Array.from(document.querySelectorAll('.workspace-tab')).map(t => t.textContent.trim()).slice(0, 8)`,
      tableRows: `document.querySelectorAll('.data-table tbody tr').length`,
      badges: `Array.from(document.querySelectorAll('.status-badge')).slice(0, 6).map(b => b.textContent.trim())`,
    },
  },
  {
    name: 'reports', path: '/reports', shot: '06-reports.png', full: true,
    ready: `!!document.querySelector('.page-title') && (document.querySelectorAll('.report-row, .data-table tbody tr').length > 0 || !!document.querySelector('.state-wrapper') || !!document.querySelector('.radio-card'))`,
    probe: {
      pageTitle: `document.querySelector('.page-title')?.textContent`,
      reportRows: `document.querySelectorAll('.report-row').length`,
      tableRows: `document.querySelectorAll('.data-table tbody tr').length`,
      radioCards: `Array.from(document.querySelectorAll('.radio-card')).map(c => c.textContent.trim().slice(0, 60))`,
      buttons: `Array.from(document.querySelectorAll('.btn-primary, .btn-outline')).map(b => b.textContent.trim()).filter(Boolean).slice(0, 8)`,
    },
  },
];

const report = { pages: {}, consoleErrors: [], exceptions: [], pageErrors: [] };
let chrome;
try {
  chrome = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=9222',
    `--user-data-dir=${OUT}chrome-profile`, '--no-first-run', '--no-default-browser-check',
    '--window-size=1440,900', '--hide-scrollbars', 'about:blank',
  ], { stdio: 'ignore' });

  await waitPort(9222);

  let tab;
  try { tab = await getJson('/json/new?' + encodeURIComponent(BASE + '/login'), 'GET'); }
  catch { tab = await getJson('/json/new?' + encodeURIComponent(BASE + '/login'), 'PUT'); }
  const page = await Page.connect(tab.webSocketDebuggerUrl);

  await page.waitFor(`document.readyState === 'complete'`, 15000);
  await sleep(1000);

  /* Login once (native setter so React registers the values) */
  const filled = await page.eval(`(() => {
    const u = document.getElementById('login-username');
    const p = document.getElementById('login-password');
    if (!u || !p) return false;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    const set = (el, v) => { setter.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })); };
    set(u, 'officer'); set(p, 'BidShield@123');
    return true;
  })()`);
  if (!filled) throw new Error('Login fields not found');
  await sleep(250);
  await page.eval(`document.querySelector('.login-submit-btn').click()`);
  const authed = await page.waitFor(`window.location.pathname === '/' && !!document.querySelector('.metric-value')`, 20000);
  if (!authed) throw new Error('Login failed. URL: ' + (await page.eval('location.href')));
  console.log('login OK');

  /* Sweep each target page */
  for (const cfg of PAGE_CONFIG) {
    const entry = { url: BASE + cfg.path };
    await page.navigate(BASE + cfg.path);
    const ready = await page.waitFor(cfg.ready, 20000);
    entry.ready = ready;
    await sleep(1200); // fonts/data settle

    entry.pageTitle = await page.eval(`document.querySelector('.page-title')?.textContent || null`);
    entry.typography = await page.eval(`(() => {
      const pick = (sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const cs = getComputedStyle(el);
        return { font: cs.fontFamily.split(',')[0].replace(/"/g,''), size: parseFloat(cs.fontSize) + 'px', weight: cs.fontWeight, spacing: cs.letterSpacing };
      };
      return { pageTitle: pick('.page-title'), sectionTitle: pick('.section-title'), th: pick('.data-table th'), td: pick('.data-table td'), btn: pick('.btn') };
    })()`);
    entry.texture = await page.eval(`(() => {
      const b = getComputedStyle(document.body);
      return { bodyGrain: (b.backgroundImage || '').includes('radial-gradient'), bodyAttachment: b.backgroundAttachment };
    })()`);
    for (const [key, expr] of Object.entries(cfg.probe)) {
      entry[key] = await page.eval(expr).catch(() => null);
    }
    await page.screenshot(OUT + cfg.shot);
    await page.screenshot(OUT + cfg.shot.replace('.png', '-full.png'), true);
    entry.screenshots = [cfg.shot, cfg.shot.replace('.png', '-full.png')];
    report.pages[cfg.name] = entry;
    console.log('page OK:', cfg.name);
  }

  report.consoleErrors = page.console;
  report.exceptions = page.exceptions;
  report.pageErrors = page.pageErrors;
} catch (e) {
  report.fatal = String(e.message || e);
} finally {
  try { chrome && chrome.kill(); } catch {}
}

writeFileSync(OUT + 'report-pages.json', JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
process.exit(report.fatal ? 1 : 0);
