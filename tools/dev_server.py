"""开发用：在浏览器里预览界面。静态文件来自 web/，/api/<方法名> 转发给 PlannerApi。

python tools/dev_server.py --home <数据目录> [--port 8765] [--today 2026-11-12]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from planner_core.plan_spec import parse_date  # noqa: E402
from planner_ui import PlannerApi  # noqa: E402

WEB_DIR = os.path.join(ROOT, "web")
ALLOWED = {
    "state", "poll", "reload", "set_done", "save_profile", "add_task", "update_task", "delete_task",
    "archive_plan", "restore_plan", "delete_archived", "save_settings", "test_notification",
    "pomodoro_start", "pomodoro_pause", "pomodoro_resume", "pomodoro_stop", "pomodoro_skip", "pomodoro_tick",
    "open_plans_dir", "open_data_dir", "open_file", "open_url", "open_notification_settings",
}


class Handler(SimpleHTTPRequestHandler):
    api: PlannerApi

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/index.html?dev=1")
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self) -> None:
        name = self.path.removeprefix("/api/")
        if name not in ALLOWED:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        args = json.loads(self.rfile.read(length) or b"[]")
        result = getattr(self.api, name)(*args)
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--today")
    args = parser.parse_args()
    Handler.api = PlannerApi(args.home, parse_date(args.today) if args.today else None)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=WEB_DIR))
    print(f"http://127.0.0.1:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
