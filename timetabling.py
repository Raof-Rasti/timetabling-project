from io import BytesIO
from datetime import time, timedelta, datetime
from collections import defaultdict
import itertools
import json
import math
import pandas as pd
from typing import List, Dict, Any, Optional


# ----------------------------
# Utility functions
# ----------------------------

def parse_time(value) -> Optional[time]:
    """Parse a string or Excel time value into a time object."""
    if pd.isna(value) or value == "":
        return None
    if isinstance(value, time):
        return value
    return pd.to_datetime(str(value)).time()


def parse_list(value) -> List[str]:
    """Parse comma-separated or JSON-style lists into Python lists."""
    if pd.isna(value) or value == "":
        return []
    if isinstance(value, list):
        return value
    s = str(value).strip()
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return [x.strip() for x in s.split(",") if x.strip()]


def t(h: int, m: int = 0) -> time:
    return time(hour=h, minute=m)


def minutes_between(a: time, b: time) -> int:
    return (datetime.combine(datetime.min, b) - datetime.combine(datetime.min, a)).seconds // 60


def overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def time_to_str(x: time) -> str:
    return f"{x.hour:02d}:{x.minute:02d}"


# ----------------------------
# Core timetable helpers
# ----------------------------

def build_timeslots(days: List[str], start: time, end: time, block_min: int) -> pd.DataFrame:
    """Generate timeslot blocks per day."""
    slots = []
    current = start
    while minutes_between(current, end) >= block_min:
        next_t = (datetime.combine(datetime.min, current) + timedelta(minutes=block_min)).time()
        label = f"{time_to_str(current)}-{time_to_str(next_t)}"
        slots.append((current, next_t, label))
        current = next_t

    all_slots = []
    slot_id = 1
    for d in days:
        for s, e, label in slots:
            all_slots.append((f"TS{slot_id:03d}", d, s, e, label, block_min))
            slot_id += 1
    return pd.DataFrame(all_slots, columns=["slot_id", "day", "start", "end", "label", "duration_min"])


def expand_course_sessions(courses_df: pd.DataFrame) -> pd.DataFrame:
    """Expand each course into individual weekly sessions."""
    records = []
    for _, row in courses_df.iterrows():
        for k in range(int(row["sessions_per_week"])):
            records.append((row["course_id"], k + 1, int(row["session_duration_min"]), row["instructor_id"]))
    return pd.DataFrame(records, columns=["course_id", "session_index", "duration_min", "instructor_id"])


def slots_matching_duration(timeslots_df: pd.DataFrame, duration_min: int) -> pd.DataFrame:
    """Return all consecutive timeslot chains matching the given duration."""
    block = int(timeslots_df["duration_min"].iloc[0])
    blocks_needed = math.ceil(duration_min / block)
    results = []
    for day, grp in timeslots_df.groupby("day"):
        ordered = grp.sort_values("start")
        records = ordered.to_dict("records")
        for i in range(len(records) - blocks_needed + 1):
            ok = all(records[i + j]["end"] == records[i + j + 1]["start"] for j in range(blocks_needed - 1))
            if ok:
                start = records[i]["start"]
                end = records[i + blocks_needed - 1]["end"]
                results.append({
                    "day": day,
                    "slot_ids": [records[i + x]["slot_id"] for x in range(blocks_needed)],
                    "start": start,
                    "end": end,
                    "label": f"{day} {time_to_str(start)}-{time_to_str(end)}",
                    "duration_min": blocks_needed * block,
                })
    return pd.DataFrame(results)


# ----------------------------
# Main scheduling pipeline
# ----------------------------

def run_scheduler(input_xlsx_bytes: bytes) -> Dict[str, Any]:
    """Core scheduling function — same API, cleaner structure."""
    xl = pd.ExcelFile(BytesIO(input_xlsx_bytes))

    # Read sheets
    sheets = {
        name: pd.read_excel(xl, name)
        for name in xl.sheet_names
    }

    courses = sheets["courses"]
    instructors = sheets["instructors"]
    availability = sheets["availability"]
    rooms = sheets["rooms"]
    enrollments = sheets["enrollments"]
    settings_kv = sheets["settings"]

    # Optional sheets
    students = sheets.get("students", pd.DataFrame())
    building_travel = sheets.get("building_travel", pd.DataFrame())

    # Settings
    settings = {
        str(k).strip(): str(v).strip()
        for k, v in settings_kv[["key", "value"]].itertuples(index=False)
    }

    DAYS = [d.strip() for d in settings.get("DAYS", "Sat,Sun,Mon,Tue,Wed,Thu").split(",")]
    START_DAY = parse_time(settings.get("START_DAY", "08:00"))
    END_DAY = parse_time(settings.get("END_DAY", "19:00"))
    BLOCK_MIN = int(float(settings.get("BLOCK_MIN", 90)))

    # Normalize course/instructor columns
    courses["equipment_required"] = courses.get("equipment_required", "").apply(parse_list)
    instructors["preferred_days"] = instructors.get("preferred_days", "").apply(parse_list)
    instructors["preferred_start"] = instructors.get("preferred_start", START_DAY).apply(parse_time)
    instructors["preferred_end"] = instructors.get("preferred_end", END_DAY).apply(parse_time)

    availability["available_start"] = availability["available_start"].apply(parse_time)
    availability["available_end"] = availability["available_end"].apply(parse_time)
    rooms["equipment"] = rooms["equipment"].apply(parse_list)

    # Building travel times
    if not building_travel.empty:
        building_travel_min = {
            (str(f), str(t)): int(m)
            for f, t, m in building_travel[["from", "to", "minutes"]].itertuples(index=False)
        }
    else:
        uniq_b = sorted(rooms["building"].dropna().astype(str).unique())
        building_travel_min = {(a, b): 0 for a in uniq_b for b in uniq_b}

    # ----------------------------
    # Scheduling logic (greedy)
    # ----------------------------
    def instructor_available(instr_id, day, start, end):
        av = availability[(availability.instructor_id == instr_id) & (availability.day == day)]
        return any(r.available_start <= start and r.available_end >= end for _, r in av.iterrows())

    def room_ok(room_row, required: List[str]) -> bool:
        return set(required).issubset(set(room_row.equipment))

    timeslots = build_timeslots(DAYS, START_DAY, END_DAY, BLOCK_MIN)
    sessions = expand_course_sessions(courses)

    # --- core greedy loop ---
    assigned = []
    room_busy, instr_busy, student_busy = defaultdict(list), defaultdict(list), defaultdict(list)

    def free_in(intervals, s, e):
        return not any(overlap(s, e, a, b) for (a, b) in intervals)

    chains_cache: Dict[int, pd.DataFrame] = {}

    def chains_for(dur):
        if dur not in chains_cache:
            df = slots_matching_duration(timeslots, dur)
            chains_cache[dur] = df if not df.empty else pd.DataFrame(columns=["day", "slot_ids", "start", "end"])
        return chains_cache[dur]

    course_students = enrollments.groupby("course_id")["student_id"].apply(list).to_dict()

    for _, sess in sessions.iterrows():
        cid, instr, dur = sess.course_id, sess.instructor_id, int(sess.duration_min)
        req = courses.loc[courses.course_id == cid, "equipment_required"].iloc[0]
        chains = chains_for(dur)
        placed = False

        instr_row = instructors[instructors.instructor_id == instr].iloc[0]
        pref_days = set(instr_row.preferred_days)
        ps, pe = instr_row.preferred_start or START_DAY, instr_row.preferred_end or END_DAY

        if not chains.empty:
            def score(ch):
                sc = 0
                if ch.day in pref_days:
                    sc += 2
                if ch.start >= ps and ch.end <= pe:
                    sc += 1
                sc -= 0.001 * (minutes_between(START_DAY, ch.start) + minutes_between(ch.end, END_DAY))
                return sc

            chains["__score"] = chains.apply(score, axis=1)
            chains = chains.sort_values("__score", ascending=False)

        for _, ch in chains.iterrows():
            day, start, end = ch.day, ch.start, ch.end
            if not instructor_available(instr, day, start, end):
                continue
            for _, room in rooms.iterrows():
                if not room_ok(room, req):
                    continue
                n_enrolled = len(course_students.get(cid, []))
                if room.capacity < n_enrolled:
                    continue
                if not (free_in(room_busy[(room.room_id, day)], start, end)
                        and free_in(instr_busy[(instr, day)], start, end)
                        and all(free_in(student_busy[(sid, day)], start, end)
                                for sid in course_students.get(cid, []))):
                    continue

                assigned.append({
                    "course_id": cid,
                    "session_index": int(sess.session_index),
                    "instructor_id": instr,
                    "room_id": room.room_id,
                    "building": room.building,
                    "day": day,
                    "start": start,
                    "end": end,
                    "slot_ids": ",".join(ch.slot_ids),
                })
                room_busy[(room.room_id, day)].append((start, end))
                instr_busy[(instr, day)].append((start, end))
                for sid in course_students.get(cid, []):
                    student_busy[(sid, day)].append((start, end))
                placed = True
                break
            if placed:
                break
        if not placed:
            assigned.append({
                "course_id": cid,
                "session_index": int(sess.session_index),
                "instructor_id": instr,
                "room_id": None,
                "building": None,
                "day": None,
                "start": None,
                "end": None,
                "slot_ids": "",
            })

    schedule = pd.DataFrame(assigned)

    # ----------------------------
    # Simple scoring & output
    # ----------------------------
    soft_score = float(len(schedule.dropna(subset=["day"])) * 0.1)  # placeholder soft score

    # Convert time columns to strings
    def stringify_times(df: pd.DataFrame, cols=("start", "end")) -> pd.DataFrame:
        df = df.copy()
        for c in cols:
            if c in df.columns:
                df[c] = df[c].apply(lambda x: time_to_str(x) if isinstance(x, time) else "")
        return df

    schedule_xls = stringify_times(schedule)

    out_buf = BytesIO()
    with pd.ExcelWriter(out_buf, engine="openpyxl") as writer:
        schedule_xls.to_excel(writer, index=False, sheet_name="schedule")
    out_buf.seek(0)

    preview = schedule_xls.head(20).to_dict(orient="records")

    return {
        "output_bytes": out_buf.getvalue(),
        "soft_score": soft_score,
        "preview": preview,
        "counts": {
            "sessions": len(schedule),
            "hard_errors": 0,
            "soft_details": 0,
        },
    }
