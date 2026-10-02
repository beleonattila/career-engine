#!/usr/bin/env python3
"""serve.py — the dashboard with a save button: the only way to edit the Timeline and To-do.

A page opened from disk (file://) cannot write files, so the dashboard opened directly shows the
plan read-only. This serves user/workspace/ on 127.0.0.1, regenerates the dashboard on every
load of it (so it is never stale after /track or /inbox), and accepts saves of the plan:

    GET  /                          → /artifacts/dashboard.html
    GET  /artifacts/dashboard.html  → runs dashboard.py, then serves the fresh file
    GET  /api/plan                  → {"plan": <plan.json>}
    PUT  /api/plan                  → validate + write (plan.py); 409 + the current plan on a stale rev

It does NOT run expire_sweep.py: serving a page never moves a record. /dashboard still does.

Local only, by construction: it binds 127.0.0.1, refuses any Host header but its own (DNS
rebinding), and takes a write only as a same-origin JSON PUT. A cross-site page cannot send one —
the JSON content type forces a CORS preflight this server never answers.

Run:  python engine/tools/serve.py [--port 8765] [--no-open]      Ctrl+C to stop.
"""
import argparse, json, subprocess, sys, threading, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import plan
from paths import TOOLS, WORKSPACE

DASHBOARD = "/artifacts/dashboard.html"
MAX_BODY = 2_000_000
_lock = threading.Lock()  # one regenerate or save at a time


def regenerate():
    r = subprocess.run([sys.executable, str(TOOLS / "dashboard.py")], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(f"[serve] dashboard.py failed — serving the previous file:\n{r.stderr.strip()}", flush=True)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(WORKSPACE), **k)

    def _origin(self):
        return f"http://{self.headers.get('Host', '')}"

    def _host_ok(self):
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # The dashboard is regenerated per load; never let the browser show yesterday's.
        if urlsplit(self.path).path == DASHBOARD:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if not self._host_ok():
            return self.send_error(403, "unexpected Host header")
        path = urlsplit(self.path).path
        if path == "/":
            self.send_response(302)
            self.send_header("Location", DASHBOARD)
            return self.end_headers()
        if path == "/api/plan":
            with _lock:
                try:
                    return self._json(200, {"plan": plan.load()})
                except (plan.PlanError, ValueError) as e:
                    return self._json(500, {"error": f"plan.json is unreadable: {e}"})
        if path == DASHBOARD:
            with _lock:
                regenerate()
        return super().do_GET()

    def do_HEAD(self):
        if not self._host_ok():
            return self.send_error(403, "unexpected Host header")
        return super().do_HEAD()

    def do_PUT(self):
        if not self._host_ok():
            return self.send_error(403, "unexpected Host header")
        if urlsplit(self.path).path != "/api/plan":
            return self.send_error(404)
        if self.headers.get("Origin") != self._origin():
            return self._json(403, {"error": "cross-origin write refused"})
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._json(415, {"error": "send application/json"})
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= MAX_BODY:
            return self._json(413, {"error": "empty or oversized body"})
        try:
            doc = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            return self._json(400, {"error": f"not JSON: {e}"})
        with _lock:
            try:
                saved = plan.save(doc, doc.get("rev") if isinstance(doc, dict) else None)
            except plan.Conflict as c:
                return self._json(409, {"error": "plan.json changed since this page read it",
                                        "plan": c.current})
            except plan.PlanError as e:
                return self._json(400, {"error": str(e)})
        return self._json(200, {"plan": saved})

    def log_message(self, fmt, *args):  # quiet: only failures reach the console
        if len(args) > 1 and str(args[1])[:1] in ("4", "5"):
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser(description="Serve the dashboard locally so the plan can be edited")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="do not open a browser tab")
    args = ap.parse_args()
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as e:
        raise SystemExit(f"port {args.port} is taken ({e}) — try --port {args.port + 1}")
    url = f"http://127.0.0.1:{args.port}{DASHBOARD}"
    print(f"Dashboard at {url}  (plan: {plan.PLAN_FILE})\nCtrl+C to stop.", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
