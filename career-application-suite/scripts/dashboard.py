#!/usr/bin/env python3
"""Local, read-only application dashboard."""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from store import CareerStore


STYLE = """
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;background:#f6f7fb;color:#1d2433}
header{background:#172554;color:white;padding:20px 28px}nav a{color:#bfdbfe;margin-right:18px;text-decoration:none}
main{padding:24px;max-width:1200px;margin:auto}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card,table{background:white;border-radius:10px;box-shadow:0 1px 3px #d7dbe5}.card{padding:16px}.metric{font-size:28px;font-weight:700}
table{border-collapse:collapse;width:100%;overflow:hidden}th,td{text-align:left;padding:11px;border-bottom:1px solid #edf0f5}
th{background:#eef2ff}.tag{display:inline-block;background:#dbeafe;color:#1e40af;border-radius:999px;padding:3px 8px;font-size:12px}
.bar{height:8px;background:#e5e7eb;border-radius:99px}.fill{height:8px;background:#2563eb;border-radius:99px}
"""


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


class DashboardHandler(BaseHTTPRequestHandler):
    store: CareerStore

    def _send(self, content: str, content_type: str = "text/html; charset=utf-8"):
        body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _layout(self, title: str, body: str) -> str:
        return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<style>{STYLE}</style></head><body><header><h1>Career Application Suite</h1>
<nav><a href="/">总览</a><a href="/applications">投递记录</a>
<a href="/opportunities">岗位机会</a><a href="/weights">评分学习</a>
<a href="/notion">Notion 同步</a></nav></header>
<main><h2>{esc(title)}</h2>{body}</main></body></html>"""

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/applications":
            self._send(
                json.dumps(self.store.applications(), ensure_ascii=False),
                "application/json; charset=utf-8",
            )
            return
        if path == "/api/weights":
            self._send(
                json.dumps(self.store.active_profile(), ensure_ascii=False),
                "application/json; charset=utf-8",
            )
            return
        if path == "/api/notion":
            self._send(
                json.dumps(self.store.notion_sync_status(), ensure_ascii=False),
                "application/json; charset=utf-8",
            )
            return
        if path == "/applications":
            self._send(self._layout("投递记录", self._applications()))
        elif path == "/opportunities":
            self._send(self._layout("岗位机会", self._opportunities()))
        elif path == "/weights":
            self._send(self._layout("评分学习", self._weights()))
        elif path == "/notion":
            self._send(self._layout("Notion 同步", self._notion()))
        else:
            self._send(self._layout("投递总览", self._overview()))

    def _overview(self) -> str:
        apps = self.store.applications()
        opportunities = self.store.list_opportunities()
        counts = {
            "机会": len(opportunities),
            "已投递": len(apps),
            "有回复": sum(
                app["status"]
                in {
                    "VIEWED",
                    "CONTACTED",
                    "WRITTEN_TEST",
                    "INTERVIEW_1",
                    "INTERVIEW_2",
                    "FINAL_INTERVIEW",
                    "OFFER",
                }
                for app in apps
            ),
            "面试": sum(
                app["status"]
                in {"INTERVIEW_1", "INTERVIEW_2", "FINAL_INTERVIEW", "OFFER"}
                for app in apps
            ),
            "Offer": sum(app["status"] == "OFFER" for app in apps),
        }
        cards = "".join(
            f'<div class="card"><div>{esc(name)}</div><div class="metric">{value}</div></div>'
            for name, value in counts.items()
        )
        return f'<div class="cards">{cards}</div><h3>最近更新</h3>{self._app_table(apps[:10])}'

    def _app_table(self, apps) -> str:
        rows = "".join(
            "<tr>"
            f"<td>{app['id']}</td><td>{esc(app['company'])}</td>"
            f"<td>{esc(app['title'])}</td><td><span class='tag'>{esc(app['status'])}</span></td>"
            f"<td>{esc(app['applied_at'])}</td><td>{esc(app.get('resume_path') or '')}</td>"
            "</tr>"
            for app in apps
        )
        return (
            "<table><tr><th>ID</th><th>公司</th><th>岗位</th><th>阶段</th>"
            f"<th>投递时间</th><th>简历快照</th></tr>{rows}</table>"
        )

    def _applications(self) -> str:
        return self._app_table(self.store.applications())

    def _opportunities(self) -> str:
        rows = "".join(
            "<tr>"
            f"<td>{item['id']}</td><td>{esc(item['kind'])}</td>"
            f"<td>{esc(item['company'])}</td><td>{esc(item['title'])}</td>"
            f"<td>{esc(item['location'])}</td><td>{item['score']}</td>"
            f"<td>{esc(item.get('sources') or '')}</td>"
            "</tr>"
            for item in self.store.list_opportunities()
        )
        return (
            "<table><tr><th>ID</th><th>类型</th><th>公司</th><th>岗位/批次</th>"
            f"<th>地点</th><th>评分</th><th>来源</th></tr>{rows}</table>"
        )

    def _weights(self) -> str:
        profile = self.store.active_profile()
        rows = ""
        for name, weight in sorted(
            profile["weights"].items(), key=lambda item: item[1], reverse=True
        ):
            rows += (
                f"<tr><td>{esc(name)}</td><td>{weight:.2%}</td><td>"
                f'<div class="bar"><div class="fill" style="width:{weight*100:.2f}%"></div></div>'
                "</td></tr>"
            )
        return (
            f"<p>当前版本：v{profile['version']} · 学习样本：{profile['sample_count']} · "
            f"原因：{esc(profile['reason'])}</p>"
            f"<table><tr><th>特征</th><th>权重</th><th>分布</th></tr>{rows}</table>"
        )

    def _notion(self) -> str:
        status = self.store.notion_sync_status()
        queue = status["queue"]
        state = status["state"]
        target = status["target"].get("page_url") or ""
        target_html = (
            f'<p>目标：<a href="{esc(target)}">{esc(target)}</a></p>'
            if target
            else "<p>尚未配置 Notion 目标。</p>"
        )
        cards = "".join(
            (
                '<div class="card"><div>{}</div>'
                '<div class="metric">{}</div></div>'
            ).format(esc(label), value)
            for label, value in (
                ("待同步", queue.get("PENDING", 0)),
                ("已同步", queue.get("SYNCED", 0)),
                ("失败", queue.get("FAILED", 0)),
                ("映射记录", sum(state.values())),
            )
        )
        failures = status["failures"]
        if not failures:
            failure_table = "<p>当前没有同步失败。</p>"
        else:
            rows = "".join(
                "<tr>"
                f"<td>{esc(item['entity_type'])}</td>"
                f"<td>{item['local_id']}</td>"
                f"<td>{item['retry_count']}</td>"
                f"<td>{esc(item.get('last_error') or '')}</td>"
                "</tr>"
                for item in failures
            )
            failure_table = (
                "<table><tr><th>实体</th><th>本地 ID</th>"
                f"<th>重试</th><th>错误</th></tr>{rows}</table>"
            )
        return (
            f"{target_html}<div class='cards'>{cards}</div>"
            f"<h3>失败记录</h3>{failure_table}"
        )

    def log_message(self, format, *args):  # noqa: A003
        return


def serve(db_path: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    store = CareerStore(db_path)
    store.initialize()
    handler = type("ConfiguredDashboardHandler", (DashboardHandler,), {"store": store})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Dashboard: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
