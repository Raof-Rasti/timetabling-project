from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from pathlib import Path
import traceback

app = Flask(__name__)
CORS(app)

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

# ---------- Serve Frontend (explicit, no catch-all) ----------
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/styles.css")
def styles():
    return send_from_directory(FRONTEND_DIR, "styles.css")

@app.route("/script.js")
def script():
    return send_from_directory(FRONTEND_DIR, "script.js")

# ---------- API ----------
@app.route("/api/schedule", methods=["POST"])
def api_schedule():
    try:
        # 4 files from form-data (exact field names must match input ids/names)
        files = {
            "teacher_schedule": request.files.get("file_teacher"),
            "all_teachers": request.files.get("file_all_teachers"),
            "class_schedule": request.files.get("file_class"),
            "all_classes": request.files.get("file_all_classes"),
        }

        # Validate presence
        missing = [k for k, f in files.items() if f is None]
        if missing:
            return jsonify({"error": f"فایل‌های زیر ارسال نشده‌اند: {', '.join(missing)}"}), 400

        # Helper: read excel into list[dict] (top 50 rows)
        def read_excel(f):
            try:
                df = pd.read_excel(f)
                return df.head(50).to_dict(orient="records")
            except Exception as e:
                traceback.print_exc()
                return [{"error": f"خطا در خواندن اکسل: {str(e)}"}]

        data = {k: read_excel(v) for k, v in files.items()}
        return jsonify(data)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Run: python app.py  ->  http://localhost:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
