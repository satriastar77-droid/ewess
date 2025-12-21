from flask import Blueprint, jsonify
from db import get_db
from datetime import datetime

logs_api = Blueprint("logs_api", __name__)

# ===============================
# HELPER: SAFE DATETIME SERIALIZER
# ===============================
def serialize_dt(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    return dt.replace(" ", "T")

@logs_api.route("/api/logs", methods=["GET"])
def get_logs():
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                event_id,
                sensor_id,
                start_time,
                end_time,
                duration_sec,
                max_intensity,
                avg_intensity,
                created_at
            FROM quake_logs
            ORDER BY event_id DESC
            LIMIT 50
        """)

        rows = cursor.fetchall()

        cursor.close()
        db.close()

        return jsonify([
            {
                "event_id": r["event_id"],
                "sensor_id": r["sensor_id"],
                "start_time": serialize_dt(r["start_time"]),
                "end_time": serialize_dt(r["end_time"]),
                "duration_sec": r["duration_sec"],
                "max_intensity": r["max_intensity"],
                "avg_intensity": r["avg_intensity"]
            }
            for r in rows
        ]), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
