"""Mock Global Token Revocation (GTR) receiver for the FBM Universal Logout test.

Listens on :8098 and logs any POST to /gtr-A (App1, explicitly assigned) or
/gtr-B (App2, Federation Broker Mode). Always answers 200 so Okta records success.

Usage: python3 -I mock_gtr_server.py [port]
"""
import base64
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8098
ROUTES = {"/gtr-A": "App1 (assigned)", "/gtr-B": "App2 (FBM)"}


def decode_jwt_payload(token):
    # Display only; the signature is deliberately not verified in this mock.
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return None


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        label = ROUTES.get(self.path, "UNKNOWN PATH")
        print(f"\n[{datetime.now():%H:%M:%S}] GTR received -> {self.path} [{label}]")
        print(f"  Content-Type: {self.headers.get('Content-Type')}")
        claims = decode_jwt_payload(body.strip())
        if claims is None:
            try:
                claims = json.loads(body)
            except Exception:
                claims = None
        print("  Body:", json.dumps(claims, indent=2) if claims else body)
        self.send_response(200 if self.path in ROUTES else 404)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"mock GTR server up\n")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Listening on :{PORT}  routes: {', '.join(ROUTES)}")
    HTTPServer(("", PORT), Handler).serve_forever()
