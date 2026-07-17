import csv
import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from data.schedule import SLOTS
from data.topics import TOPICS

app = Flask(__name__)

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "submissions.csv")
CSV_LOCK = threading.Lock()

SLOT_IDS = [slot["id"] for slot in SLOTS]
SLOT_BY_ID = {slot["id"]: slot for slot in SLOTS}
TOPIC_BY_ID = {topic["id"]: topic for topic in TOPICS}

MAX_NAME_LENGTH = 80
# Leading characters that spreadsheet apps (Excel/Sheets) treat as the start
# of a formula. Prefixing with a quote stops a submitted name from being
# interpreted as one when the CSV is opened later.
FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@")


def sanitize_for_csv(value):
    if value.startswith(FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value


def ensure_csv_header():
    if os.path.exists(CSV_PATH):
        return
    header = ["timestamp_utc", "name"] + [slot["label"] for slot in SLOTS]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(header)


@app.route("/")
def index():
    days = []
    seen_days = []
    for slot in SLOTS:
        if slot["day"] not in seen_days:
            seen_days.append(slot["day"])

    for day in seen_days:
        day_slots = [s for s in SLOTS if s["day"] == day]
        time_blocks = []
        seen_times = []
        for slot in day_slots:
            if slot["time"] not in seen_times:
                seen_times.append(slot["time"])
        for time in seen_times:
            block_slots = [s for s in day_slots if s["time"] == time]
            time_blocks.append({"time": time, "slots": block_slots})
        days.append({"day": day, "blocks": time_blocks})

    return render_template("index.html", days=days, topics=TOPICS)


@app.route("/submit", methods=["POST"])
def submit():
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Expected a JSON body."}), 400

    name = str(payload.get("name", "")).strip()
    assignments = payload.get("assignments")

    if not name:
        return jsonify({"error": "Please enter a name."}), 400
    if len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"Name must be {MAX_NAME_LENGTH} characters or fewer."}), 400
    if not isinstance(assignments, dict):
        return jsonify({"error": "Missing schedule assignments."}), 400

    submitted_slot_ids = set(assignments.keys())
    if submitted_slot_ids != set(SLOT_IDS):
        return jsonify({"error": "Every slot must have exactly one topic before submitting."}), 400

    submitted_topic_ids = list(assignments.values())
    if set(submitted_topic_ids) != set(TOPIC_BY_ID.keys()) or len(submitted_topic_ids) != len(TOPIC_BY_ID):
        return jsonify({"error": "Each topic must be used exactly once."}), 400

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = [timestamp, sanitize_for_csv(name)]
    for slot_id in SLOT_IDS:
        topic = TOPIC_BY_ID[assignments[slot_id]]
        row.append(topic["short"])

    with CSV_LOCK:
        ensure_csv_header()
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)

    return jsonify({"ok": True})


if __name__ == "__main__":
    ensure_csv_header()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
