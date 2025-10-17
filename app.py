from __future__ import annotations

from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import secrets
import time
import os

from timetabling import run_scheduler  # unchanged, external dependency

# ----------------------------
# Config
# ----------------------------

class Config:
    # 25MB max upload to avoid abuse; adjust if needed.
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    # Enable/disable debug via env var if you want
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"


# ----------------------------
# Simple in-memory store
# ----------------------------
# Maps token -> (bytes, created_at)
SCHEDULE_STORE: Dict[str, Tuple[bytes, float]] = {}

# Directory for static frontend assets (same as before)
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)

    # ----------------------------
    # Helpers
    # ----------------------------

    def _cache_static(resp: Response) -> Response:
        # 1 day cache for static assets if they exist
        resp.cache_control.public = True
        resp.cache_control.max_age = 86400
        return resp

    def _json_error(message: str, status: int = 400) -> Tuple[Response, int]:
        return jsonify({"error": message}), status

    # Basic store cleanup: remove very old items (e.g., > 12h)
    def _gc_store(now: Optional[float] = None) -> None:
        cutoff = (now or time.time()) - 12 * 3600
        expired = [k for k, (_, ts) in SCHEDULE_STORE.items() if ts < cutoff]
        for k in expired:
            SCHEDULE_STORE.pop(k, None)

    # ----------------------------
    # Error Handlers
    # ----------------------------

    @app.errorhandler(HTTPException)
    def _handle_http_exception(err: HTTPException):
        # Unified JSON errors
        return _json_error(err.description or err.name, err.code or 500)

    @app.errorhandler(Exception)
    def _handle_uncaught(err: Exception):
        # Avoid leaking internals; keep message succinct
        return _json_error("Internal server error"), 500

    # ----------------------------
    # Frontend routes (same paths)
    # ----------------------------

    @app.route("/")
    def index():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            resp = send_from_directory(FRONTEND_DIR, "index.html")
            return resp  # no cache for HTML
        return jsonify({"message": "Backend running. Frontend not found."}), 200

    @app.route("/styles.css")
    def styles():
        path = FRONTEND_DIR / "styles.css"
        if path.exists():
            return _cache_static(send_from_directory(FRONTEND_DIR, "styles.css"))
        return ("", 404)

    @app.route("/script.js")
    def script():
        path = FRONTEND_DIR / "script.js"
        if path.exists():
            return _cache_static(send_from_directory(FRONTEND_DIR, "script.js"))
        return ("", 404)

    # ----------------------------
    # API
    # ----------------------------

    @app.route("/api/health", methods=["GET"])
    def health():
        # Same response as before
        return jsonify({"status": "ok"})

    @app.route("/api/schedule", methods=["POST"])
    def schedule():
        # Garbage-collect occasionally
        _gc_store()

        if "file" not in request.files:
            return _json_error("No file uploaded (field name: file)", 400)

        file = request.files["file"]
        try:
            data = file.read()
        except Exception:
            return _json_error("Failed to read uploaded file", 400)

        if not data:
            return _json_error("Uploaded file is empty", 400)

        # Call the original scheduler exactly as before
        try:
            result: Dict[str, Any] = run_scheduler(data)
        except Exception as e:
            # Keep behavior: return the error string from scheduler
            return _json_error(str(e), 400)

        # Generate a short, URL-safe token
        token = secrets.token_hex(8)
        output_bytes = result.get("output_bytes", b"")
        if not isinstance(output_bytes, (bytes, bytearray)) or not output_bytes:
            return _json_error("Scheduler produced no output", 400)

        # Store in memory
        SCHEDULE_STORE[token] = (bytes(output_bytes), time.time())

        # Return the same JSON contract as before
        return jsonify({
            "token": token,
            "soft_score": result.get("soft_score"),
            "counts": result.get("counts"),
            "preview": result.get("preview"),
        })

    @app.route("/api/download/<token>", methods=["GET"])
    def download(token: str):
        blob = SCHEDULE_STORE.get(token)
        if blob is None:
            return _json_error("Invalid or expired token", 404)

        buf, _created_at = blob
        return send_file(
            BytesIO(buf),
            as_attachment=True,
            download_name="schedule_output.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_age=0,  # force fresh download
            etag=False,
            conditional=False,
            last_modified=None,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    # Bind and run just like before; debug controlled by env
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
