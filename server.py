#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
  JIRVIRAL.XYZ / OLYMPUS — RENDER WEB SERVER API
=====================================================================
"""

import os
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

DEFAULT_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")

class Http:
    def __init__(self, ua=DEFAULT_UA):
        self.ua = ua
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPRedirectHandler(),
        )

    def request(self, method, url, data=None, referer=None):
        headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            o = urllib.parse.urlparse(url)
            headers["Origin"] = o.scheme + "://" + o.netloc
            headers["Referer"] = referer or url
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            resp = self.op.open(req, timeout=30)
            return resp.getcode(), resp.geturl(), resp.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            return e.code, e.geturl(), e.read().decode("utf-8", "ignore")

def get_unlock_token(html):
    m = re.search(r'name=["\']unlock_token["\'][^>]*value=["\']([^"\']+)["\']', html, re.I)
    return m.group(1) if m else None

def get_k(html):
    m = re.search(r'name=["\']k["\']\s+value=["\']([^"\']+)["\']', html, re.I)
    return m.group(1) if m else None

def title(html):
    m = re.search(r'<title>(.*?)</title>', html, re.S | re.I)
    return m.group(1) if m else None

def get_key(html):
    m = re.search(r'id=["\']keyText["\'][^>]*>\s*([^<\s]+)', html, re.I)
    return m.group(1).strip() if m else None

def parse_gate_form(html):
    for fm in re.finditer(r'<form([^>]*)>(.*?)</form>', html, re.S | re.I):
        inner = fm.group(2)
        if 'id="download"' not in inner and "id='download'" not in inner:
            continue
        attrs = fm.group(1)
        action = re.search(r'action=["\']([^"\']*)["\']', attrs, re.I)
        action = action.group(1) if action else ""
        method = re.search(r'method=["\']([^"\']*)["\']', attrs, re.I)
        method = (method.group(1) or "get").lower()
        fields = {}
        for m2 in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']', inner, re.I):
            fields[m2.group(1)] = m2.group(2)
        for m2 in re.finditer(r'<input[^>]*value=["\']([^"\']*)["\'][^>]*name=["\']([^"\']+)["\']', inner, re.I):
            fields[m2.group(2)] = m2.group(1)
        return action, method, fields
    return None, None, None

def parse_post_redirect(html):
    m = re.search(r'<form[^>]*id=["\']fc-post-redirect["\'][^>]*action=["\']([^"\']+)["\'][^>]*>(.*?)</form>', html, re.S | re.I)
    if not m:
        return None, None
    action = m.group(1)
    fields = {}
    for fm in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']', m.group(2), re.I):
        fields[fm.group(1)] = fm.group(2)
    return action, fields

def bypass(gate_url, gate_wait=15, unlock_wait=6):
    http = Http()
    cur = gate_url
    html = None
    actions = 0
    MAX_ACTIONS = 80

    while actions < MAX_ACTIONS:
        actions += 1

        if html is None:
            code, fu, html = http.request("GET", cur)
            cur = fu

        action, fields = parse_post_redirect(html)
        if action and fields:
            code, fu, html = http.request("POST", action, fields, referer=cur)
            cur = fu
            if not parse_gate_form(html)[2] and not get_unlock_token(html) and not get_key(html) and not parse_post_redirect(html)[0]:
                time.sleep(3)
                code, fu, html = http.request("POST", action, fields, referer=cur)
                cur = fu
            continue

        gaction, gmethod, gfields = parse_gate_form(html)
        if gfields is not None:
            target = gaction or cur
            if gate_wait > 0 and "cad=" not in cur:
                time.sleep(gate_wait)
            if gmethod == "post":
                code, fu, html = http.request("POST", target, gfields, referer=cur)
            else:
                qs = urllib.parse.urlencode(gfields)
                full = target + ("&" if "?" in target else "?") + qs
                code, fu, html = http.request("GET", full, referer=cur)
            cur = fu
            continue

        if get_unlock_token(html):
            tok = get_unlock_token(html)
            k = get_k(html)
            code, fu, html = http.request("POST", cur, {
                "unl": "1", "unlock_src": "blur_iframe", "unlock_token": tok,
            }, referer=cur)
            cur = fu
            k2 = get_k(html)
            if k2:
                time.sleep(unlock_wait)
                u3 = fu + ("&" if "?" in fu else "?") + "fc_go=1&k=" + urllib.parse.quote(k2)
                code, fu, html = http.request("GET", u3, referer=fu)
                cur = fu
            continue

        key = get_key(html)
        if key:
            return key

        t = (title(html) or "").lower()
        if "tempo expirado" in t or "acesso bloqueado" in t:
            return None

        if html is not None:
            return None

    return None

# --- HTML Giao diện trang chủ ---
HTML_HOME = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Jirviral Bypass API</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }
        .container { max-width: 600px; margin: auto; background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        input[type="text"] { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #475569; border-radius: 6px; background: #0f172a; color: #fff; box-sizing: border-box; }
        button { background: #3b82f6; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; }
        button:hover { background: #2563eb; }
        pre { background: #0f172a; padding: 15px; border-radius: 6px; overflow-x: auto; color: #38bdf8; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Jirviral Bypass API</h2>
        <p>Nhập link Gate chứa <code>?cad=</code> để lấy key:</p>
        <input type="text" id="urlInput" placeholder="https://jirviral.xyz/.../?cad=...">
        <button onclick="bypassKey()">Lấy Key</button>
        <h3>Kết quả:</h3>
        <pre id="result">Chưa có kết quả...</pre>
    </div>
<script>
async function bypassKey() {
    const url = document.getElementById('urlInput').value;
    const resBox = document.getElementById('result');
    resBox.innerText = "Đang xử lý (quá trình này có thể mất từ 30s đến 1 phút)...";
    try {
        const response = await fetch('/api/bypass', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url})
        });
        const data = await response.json();
        resBox.innerText = JSON.stringify(data, null, 2);
    } catch (err) {
        resBox.innerText = "Lỗi kết nối: " + err;
    }
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_HOME)

@app.route("/api/bypass", methods=["POST"])
def api_bypass():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    
    if not url:
        return jsonify({"success": False, "error": "Thiếu tham số url"}), 400
        
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url

    try:
        # Chạy bypass (mặc định gate_wait=15, unlock_wait=6)
        key = bypass(url, gate_wait=15, unlock_wait=6)
        if key:
            return jsonify({"success": True, "key": key})
        else:
            return jsonify({"success": False, "error": "Không lấy được key, link có thể đã hết hạn hoặc sai định dạng."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
