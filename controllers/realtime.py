from flask import Blueprint, request, jsonify
from db import get_db
from datetime import datetime

realtime_api = Blueprint("realtime_api", __name__)

THRESHOLD = 40
QUIET_SECONDS = 3


# ======================================================
# POST /api/realtime
# ======================================================
@realtime_api.route("/api/realtime", methods=["POST"])
def post_realtime():
    try:
        data = request.json or {}

        sensor_id = data.get("sensor_id", 1)
        intensity = int(data.get("intensity", 0))
        duration = float(data.get("duration", 0))
        shake = 1 if intensity >= THRESHOLD else 0
        now = datetime.now()

        db = get_db()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM realtime_status WHERE sensor_id = %s",
            (sensor_id,)
        )
        state = cursor.fetchone()

        if not state:
            return jsonify({"error": "Sensor not registered"}), 400

        event_active = state["event_active"]
        active_event_id = state["current_event_id"]

        # ==================================================
        # EVENT ACTIVE
        # ==================================================
        if event_active:
            # --- SIMPAN SEMUA SAMPLE ---
            cursor.execute("""
                INSERT INTO quake_event_samples
                (event_id, sensor_id, intensity, recorded_at)
                VALUES (%s, %s, %s, %s)
            """, (
                active_event_id,
                sensor_id,
                intensity,
                now
            ))

            # --- UPDATE AGREGAT ---
            cursor.execute("""
                UPDATE realtime_status
                SET max_intensity = GREATEST(max_intensity, %s),
                    sum_intensity = sum_intensity + %s,
                    sample_count = sample_count + 1
                WHERE sensor_id = %s
            """, (intensity, intensity, sensor_id))

            # --- CEK END EVENT ---
            if intensity < THRESHOLD:
                if state["last_below_threshold"] is None:
                    cursor.execute("""
                        UPDATE realtime_status
                        SET last_below_threshold = %s
                        WHERE sensor_id = %s
                    """, (now, sensor_id))
                else:
                    quiet = (now - state["last_below_threshold"]).total_seconds()
                    if quiet >= QUIET_SECONDS:
                        duration_sec = (now - state["event_start_time"]).total_seconds()
                        avg_intensity = (
                            state["sum_intensity"] / max(state["sample_count"], 1)
                        )

                        cursor.execute("""
                            UPDATE quake_logs
                            SET end_time = %s,
                                duration_sec = %s,
                                max_intensity = %s,
                                avg_intensity = %s
                            WHERE event_id = %s
                        """, (
                            now,
                            duration_sec,
                            state["max_intensity"],
                            avg_intensity,
                            active_event_id
                        ))

                        cursor.execute("""
                            UPDATE realtime_status
                            SET event_active = 0,
                                event_start_time = NULL,
                                current_event_id = NULL,
                                last_below_threshold = NULL,
                                max_intensity = 0,
                                sum_intensity = 0,
                                sample_count = 0
                            WHERE sensor_id = %s
                        """, (sensor_id,))

        # ==================================================
        # START EVENT
        # ==================================================
        elif intensity >= THRESHOLD:
            cursor.execute("""
                INSERT INTO quake_logs
                (sensor_id, start_time, end_time, duration_sec, max_intensity, avg_intensity)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                sensor_id,
                now,
                now,
                0,
                intensity,
                intensity
            ))

            active_event_id = cursor.lastrowid

            cursor.execute("""
                UPDATE realtime_status
                SET event_active = 1,
                    event_start_time = %s,
                    current_event_id = %s,
                    max_intensity = %s,
                    sum_intensity = %s,
                    sample_count = 1,
                    last_below_threshold = NULL
                WHERE sensor_id = %s
            """, (now, active_event_id, intensity, intensity, sensor_id))

            cursor.execute("""
                INSERT INTO quake_event_samples
                (event_id, sensor_id, intensity, recorded_at)
                VALUES (%s, %s, %s, %s)
            """, (
                active_event_id,
                sensor_id,
                intensity,
                now
            ))

        # ==================================================
        # REALTIME SNAPSHOT
        # ==================================================
        cursor.execute("""
            UPDATE realtime_status
            SET shake = %s,
                intensity = %s,
                duration = %s,
                timestamp = %s
            WHERE sensor_id = %s
        """, (shake, intensity, duration, now, sensor_id))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            "status": "ok",
            "sensor_id": sensor_id,
            "shake": shake,
            "intensity": intensity,
            "duration": duration,
            "timestamp": now.isoformat(),
            "event_active": bool(event_active or intensity >= THRESHOLD),
            "current_event_id": active_event_id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================
# GET /api/realtime
# ======================================================
@realtime_api.route("/api/realtime", methods=["GET"])
def get_realtime():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            sensor_id,
            shake,
            intensity,
            duration,
            timestamp,
            event_active,
            current_event_id
        FROM realtime_status
        WHERE sensor_id = 1
    """)

    data = cursor.fetchone()

    cursor.close()
    db.close()

    if data and data.get("timestamp"):
        data["timestamp"] = data["timestamp"].isoformat()

    return jsonify(data), 200


# ======================================================
# GET /api/event/<event_id>/timeline
# ======================================================
@realtime_api.route("/api/event/<int:event_id>/timeline", methods=["GET"])
def get_event_timeline(event_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT recorded_at, intensity
        FROM quake_event_samples
        WHERE event_id = %s
        ORDER BY recorded_at ASC
    """, (event_id,))

    rows = cursor.fetchall()

    samples = [
        {
            "recorded_at": r["recorded_at"].isoformat(),
            "intensity": r["intensity"]
        }
        for r in rows
    ]

    cursor.close()
    db.close()

    return jsonify({
        "event_id": event_id,
        "samples": samples
    }), 200
