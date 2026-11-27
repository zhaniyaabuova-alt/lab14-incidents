# Stand-in for Slack/Telegram/a pager: prints every notification it gets
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        for a in body["alerts"]:
            print(f'{self.path} [{a["status"].upper()}] {a["labels"]["alertname"]} '
                  f'{dict((k, v) for k, v in a["labels"].items() if k != "alertname")} '
                  f':: {a["annotations"].get("summary")}', flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


HTTPServer(("0.0.0.0", 8080), Hook).serve_forever()
