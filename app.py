from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from pathlib import Path
import traceback
import pandas as pd
from io import BytesIO

from timetabling import run_scheduler  # اتصال به الگوریتم

# ======================================================
# App config
# ======================================================
app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"


# ======================================================
# Frontend Routes
# ======================================================

@app.route("/")
def index():
    # صفحه اصلی (بعد از لاگین)
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/login")
def login_page():
    # صفحه لاگین
    return send_from_directory(FRONTEND_DIR, "login.html")


@app.route("/script.js")
def script_js():
    return send_from_directory(FRONTEND_DIR, "script.js")


@app.route("/auth.js")
def auth_js():
    return send_from_directory(FRONTEND_DIR, "auth.js")


# (اختیاری) برای فونت‌ها یا فایل‌های دیگر
@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ======================================================
# API
# ======================================================

@app.route("/api/schedule", methods=["POST"])
def api_schedule():
    try:
        file = request.files.get("file_excel")
        if not file:
            return jsonify({"error": "فایل اکسل ارسال نشده"}), 400

        input_bytes = file.read()
        result = run_scheduler(input_bytes)

        schedule_df = pd.read_excel(
            BytesIO(result["output_bytes"]),
            sheet_name="schedule"
        )

        # ---------- جدول 1: تایم‌های یک کلاس ----------
        df_class = schedule_df.sort_values(
            by=["course_id", "day", "start"]
        )
        one_class = df_class[
            df_class["course_id"] == df_class["course_id"].iloc[0]
        ]

        # ---------- جدول 2: تایم‌های همه کلاس‌ها ----------
        all_classes = schedule_df.sort_values(
            by=["day", "start"]
        )

        # ---------- جدول 3: تایم‌های یک استاد ----------
        df_teacher = schedule_df.sort_values(
            by=["instructor_id", "day", "start"],
            ascending=[False, True, True]
        )
        one_teacher = df_teacher[
            df_teacher["instructor_id"] == df_teacher["instructor_id"].iloc[0]
        ]

        # ---------- جدول 4: تایم‌های همه اساتید ----------
        all_teachers = schedule_df.sort_values(
            by=["session_index"],
            ascending=False
        )

        return jsonify({
            "one_class": one_class.to_dict(orient="records"),
            "all_classes": all_classes.to_dict(orient="records"),
            "one_teacher": one_teacher.to_dict(orient="records"),
            "all_teachers": all_teachers.to_dict(orient="records"),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ======================================================
# Run server
# ======================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
