from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import re
import time
import http.cookiejar

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


class BypassServer(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
        except Exception:
            self._set_headers(400)
            self.wfile.write(json.dumps({"status": "error", "message": "Invalid JSON"}).encode('utf-8'))
            return

        target_url = data.get('url')
        if not target_url:
            self._set_headers(400)
            self.wfile.write(json.dumps({"status": "error", "message": "Thiếu link cần bypass"}).encode('utf-8'))
            return

        try:
            key = bypass(target_url, gate_wait=10, unlock_wait=4)
            if key:
                response = {"status": "success", "key": key}
                self._set_headers(200)
            else:
                response = {"status": "error", "message": "Không bóc được key, link có thể đã hết hạn."}
                self._set_headers(400)
        except Exception as e:
            response = {"status": "error", "message": str(e)}
            self._set_headers(500)

        self.wfile.write(json.dumps(response).encode('utf-8'))

def run(server_class=HTTPServer, handler_class=BypassServer, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Server đang chạy tại cổng {port}...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()

