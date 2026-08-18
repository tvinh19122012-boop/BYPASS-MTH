from flask import Flask, request, jsonify
from flask_cors import CORS
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
import ssl

app = Flask(__name__)
CORS(app)

# ==================== CẤU HÌNH CHUNG ====================
DEFAULT_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")

# ==================== TÍNH NĂNG 1: KeyCheater (/run-tool) ====================
BASE_KC = "https://keycheater.site"
API_KC = f"{BASE_KC}/getkey"

@app.route('/run-tool', methods=['POST'])
def run_tool():
    try:
        data = request.json or {}
        seller = data.get('seller', 'zennymod1')
        game = data.get('game', 'noroot')

        import requests
        s = requests.Session()
        s.headers.update({"User-Agent": DEFAULT_UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})

        r = s.get(f"{API_KC}/{seller}", timeout=15)
        r.raise_for_status()
        html = r.text

        csrf_m = re.search(r'csrf_test_name" value="([^"]+)"', html)
        if not csrf_m: return jsonify({"status": "error", "message": "FAIL: No CSRF"}), 400
        csrf = csrf_m.group(1)

        wait = 100
        wm = re.search(r'wait_time["\:]\s*(\d+)', html)
        if wm: wait = int(wm.group(1))

        r2 = s.post(f"{BASE_KC}/getkey-process", data={"csrf_test_name": csrf, "seller": seller, "game": game}, allow_redirects=False, timeout=15)
        if r2.status_code not in (302, 303): return jsonify({"status": "error", "message": "FAIL: HTTP status"}), 400

        token = None
        for k, v in r2.headers.items():
            if k.lower() == "set-cookie":
                mt = re.search(r'getkey_token=([^;]+)', v)
                if mt: token = mt.group(1)
        if not token: return jsonify({"status": "error", "message": "FAIL: No token"}), 400

        s.cookies.set("getkey_token", token, domain="keycheater.site", path="/")
        s.cookies.set("getkey_game", game, domain="keycheater.site", path="/")

        time.sleep(wait)

        r3 = s.get(f"{BASE_KC}/getkey-callback/{seller}", timeout=15)
        text = r3.text

        key = None
        m = re.search(r'class="[^"]*key[-_]?box[^"]*"[^>]*>([^<]+)<', text, re.I)
        if m: key = m.group(1).strip()
        if not key:
            m = re.search(r'>([Vv]ip[A-Za-z0-9_-]+)<', text)
            if m: key = m.group(1)

        if key:
            return jsonify({"status": "success", "key": key, "message": "Thành công KeyCheater"})
        else:
            return jsonify({"status": "error", "message": "Không tìm thấy key"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==================== TÍNH NĂNG 2: MTH / Jirviral Bypass (/run-tool-mth) ====================
class HttpMTH:
    def __init__(self, ua=DEFAULT_UA):
        self.ua = ua
        self.cj = http.cookiejar.CookieJar()
        ctx = ssl._create_unverified_context()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=ctx),
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
        except Exception:
            return 0, url, ""

def get_unlock_token(html):
    m = re.search(r'name=["\']unlock_token["\'][^>]*value=["\']([^"\']+)["\']', html, re.I)
    return m.group(1) if m else None

def get_k(html):
    m = re.search(r'name=["\']k["\']\s+value=["\']([^"\']+)["\']', html, re.I)
    return m.group(1) if m else None

def get_key_mth(html):
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
    if not m: return None, None
    action = m.group(1)
    fields = {}
    for fm in re.finditer(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']', m.group(2), re.I):
        fields[fm.group(1)] = fm.group(2)
    return action, fields

def run_mth_bypass(gate_url):
    http = HttpMTH()
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
            if not parse_gate_form(html)[2] and not get_unlock_token(html) and not get_key_mth(html) and not parse_post_redirect(html)[0]:
                time.sleep(2)
                code, fu, html = http.request("POST", action, fields, referer=cur)
                cur = fu
            continue

        gaction, gmethod, gfields = parse_gate_form(html)
        if gfields is not None:
            target = gaction or cur
            if "cad=" not in cur:
                time.sleep(5) # Chờ rút gọn an toàn trên server
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
            code, fu, html = http.request("POST", cur, {
                "unl": "1", "unlock_src": "blur_iframe", "unlock_token": tok,
            }, referer=cur)
            cur = fu
            k2 = get_k(html)
            if k2:
                time.sleep(3)
                u3 = fu + ("&" if "?" in fu else "?") + "fc_go=1&k=" + urllib.parse.quote(k2)
                code, fu, html = http.request("GET", u3, referer=fu)
                cur = fu
            continue

        key = get_key_mth(html)
        if key:
            return key

        t = (html or "").lower()
        if "tempo expirado" in t or "acesso bloqueado" in t:
            return None
        if html is not None and actions >= MAX_ACTIONS:
            break
    return None

@app.route('/run-tool-mth', methods=['POST'])
def api_run_mth():
    try:
        data = request.json or {}
        url = data.get('url', '').strip()
        if not url:
            # Tự động fetch tầng 1 từ mthteam nếu không truyền url trực tiếp
            http = HttpMTH()
            http.request("GET", "https://mthteam.com/getkey")
            _, fu, html = http.request("GET", "https://monteolympus.com/s/andremods-mthgetkey", referer="https://mthteam.com/")
            m = re.search(r'href="([^"]+cad=[^"]+)"', html)
            if m:
                url = urllib.parse.urljoin(fu, m.group(1))
            else:
                return jsonify({"status": "error", "message": "Không tự động lấy được link cad từ MTH Team."}), 400

        key = run_mth_bypass(url)
        if key:
            return jsonify({"status": "success", "key": key, "message": "Thành công MTH Team"})
        else:
            return jsonify({"status": "error", "message": "Không bóc được key, link có thể đã hết hạn."}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
