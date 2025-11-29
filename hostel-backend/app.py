from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import json
import os

app = Flask(__name__)
CORS(app)

# ---------------- Files ---------------- #
STUDENTS_FILE = "students.json"
LOGS_FILE = "logs.json"

# ---------------- In-memory Auth Data ---------------- #
ADMIN_ACCOUNT = {
    "username": "admin",
    "password": "1234",
    "name": "Hostel Administrator"
}

WATCHMEN = [
    {
        "username": "watchman",
        "password": "1234",
        "name": "Main Gate Watchman",
        "location": "Main Gate"
    }
]

STUDENT_FIELD_DEFAULTS = {
    "room": "",
    "year": "",
    "student_class": "",
    "gender": "Male",
    "dob": None,
    "address": "",
    "email": "",
    "phone": "",
    "profile_picture": None
}
LEGACY_STUDENT_FIELD_MAP = {
    "room_no": "room",
    "course": "student_class"
}
STRING_STUDENT_FIELDS = {"room", "year", "student_class", "gender", "address", "email", "phone"}

# Initialize files if they don't exist
for file in [STUDENTS_FILE, LOGS_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f, indent=2)

# ---------------- Helper Functions ---------------- #
def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

def next_id(records):
    if not records:
        return 1
    return max(record.get("id", 0) for record in records) + 1

def get_request_data():
    if request.is_json:
        return request.get_json() or {}
    return request.form

def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def success_response(message, status_code=200, **payload):
    body = {"status": "success", "message": message}
    body.update(payload)
    response = jsonify(body)
    response.status_code = status_code
    return response

def error_response(message, code=400):
    return jsonify({"status": "error", "message": message}), code

def normalize_dob(value):
    if value in (None, "", "null", "None"):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10**12 else value
        try:
            return datetime.fromtimestamp(timestamp).date().isoformat()
        except (OSError, ValueError):
            return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {"null", "none"}:
            return None
        normalized_input = cleaned.replace("Z", "+00:00") if cleaned.endswith("Z") else cleaned
        try:
            return datetime.fromisoformat(normalized_input).date().isoformat()
        except ValueError:
            return cleaned
    return str(value)

def coerce_student_field(field, value):
    default = STUDENT_FIELD_DEFAULTS[field]
    if field == "profile_picture":
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        return value
    if field == "dob":
        return normalize_dob(value)
    if value is None:
        return default
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {"null", "none"}:
            return default
        return cleaned if field in STRING_STUDENT_FIELDS else cleaned
    if field in STRING_STUDENT_FIELDS:
        return str(value).strip()
    return value

def normalize_student_record(student):
    updated = False
    for legacy_field, new_field in LEGACY_STUDENT_FIELD_MAP.items():
        if legacy_field in student and new_field not in student:
            student[new_field] = student.pop(legacy_field)
            updated = True

    if "register_no" in student and student["register_no"] is not None:
        normalized_reg = str(student["register_no"]).strip()
        if normalized_reg != student["register_no"]:
            student["register_no"] = normalized_reg
            updated = True

    if "name" in student and isinstance(student["name"], str):
        normalized_name = student["name"].strip()
        if normalized_name != student["name"]:
            student["name"] = normalized_name
            updated = True

    for field, default in STUDENT_FIELD_DEFAULTS.items():
        if field not in student:
            student[field] = default
            updated = True
        elif field == "dob":
            normalized = normalize_dob(student[field])
            if normalized != student[field]:
                student[field] = normalized
                updated = True
        elif field in STRING_STUDENT_FIELDS and student[field] is None:
            student[field] = default
            updated = True
    return updated

def load_students():
    students = load_json(STUDENTS_FILE)
    updated = False
    for student in students:
        if normalize_student_record(student):
            updated = True
    if updated:
        save_json(STUDENTS_FILE, students)
    return students

def create_student_record(data):
    record = {
        "name": (data.get("name") or "").strip(),
    }
    register_no = data.get("register_no")
    record["register_no"] = str(register_no).strip() if register_no is not None else None
    for field in STUDENT_FIELD_DEFAULTS:
        record[field] = coerce_student_field(field, data.get(field))
    return record

def update_student_record(student, data):
    if "name" in data:
        name = (data.get("name") or "").strip()
        if name:
            student["name"] = name
    if "register_no" in data:
        register_no = data.get("register_no")
        if register_no not in (None, ""):
            student["register_no"] = str(register_no).strip()
    for field in STUDENT_FIELD_DEFAULTS:
        if field in data:
            student[field] = coerce_student_field(field, data.get(field))
    return student

# ---------------- ADMIN APIs ---------------- #
@app.route('/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    username = (data.get('username') or "").strip()
    password = data.get('password')
    print(f"[ADMIN LOGIN ATTEMPT] Username: {username}, Password: {password}")

    if username == ADMIN_ACCOUNT["username"] and password == ADMIN_ACCOUNT["password"]:
        return success_response(
            "Admin logged in",
            role="admin",
            token="admin-token",
            admin={
                "username": ADMIN_ACCOUNT["username"],
                "name": ADMIN_ACCOUNT["name"]
            }
        )
    return error_response("Invalid credentials", 401)

@app.route('/logout', methods=['GET'])
def admin_logout():
    return success_response("Admin logged out")

@app.route('/add_student', methods=['POST'])
def add_student():
    students = load_students()
    data = get_request_data()

    name = (data.get("name") or "").strip()
    raw_register_no = data.get("register_no")
    register_no = str(raw_register_no).strip() if raw_register_no is not None else None

    if not name or not register_no:
        return error_response("Name and register number are required")

    new_student = create_student_record(data)
    new_student["id"] = next_id(students)
    new_student["name"] = name
    new_student["register_no"] = register_no

    students.append(new_student)
    save_json(STUDENTS_FILE, students)

    return success_response("Student added", student=new_student, status_code=201)

@app.route('/edit_student/<int:id>', methods=['POST'])
def edit_student(id):
    students = load_students()
    data = get_request_data()
    for s in students:
        if s["id"] == id:
            update_student_record(s, data)
            if not s["name"] or not s["register_no"]:
                return error_response("Name and register number are required")
            save_json(STUDENTS_FILE, students)
            return success_response("Student updated", student=s)
    return error_response("Student not found", 404)

@app.route('/delete_student/<int:id>', methods=['DELETE'])
def delete_student(id):
    students = load_students()
    updated_students = [s for s in students if s["id"] != id]
    if len(updated_students) == len(students):
        return error_response("Student not found", 404)
    save_json(STUDENTS_FILE, updated_students)
    return success_response("Student deleted")

@app.route('/students', methods=['GET'])
def get_students():
    students = load_students()
    return success_response("Students fetched", students=students)

@app.route('/view_logs', methods=['GET'])
def view_logs():
    logs = load_json(LOGS_FILE)
    return success_response("Logs fetched", logs=logs)

# ---------------- WATCHMAN APIs ---------------- #
@app.route('/watchman/login', methods=['POST'])
def watchman_login():
    data = request.get_json() or {}
    username = (data.get('username') or "").strip()
    password = data.get('password')

    for watchman in WATCHMEN:
        if watchman["username"] == username and watchman["password"] == password:
            payload = {
                "username": watchman["username"],
                "name": watchman["name"],
                "location": watchman["location"]
            }
            return success_response(
                "Watchman logged in",
                role="watchman",
                token=f"watchman-{watchman['username']}",
                watchman=payload
            )
    return error_response("Invalid credentials", 401)

@app.route('/watchman/logout', methods=['GET'])
def watchman_logout():
    return success_response("Watchman logged out")

@app.route('/watchman/record', methods=['POST'])
def record_student_movement():
    data = request.get_json() or {}
    raw_student_id = data.get("student_id")
    movement_type = (data.get("movement_type") or "").lower()
    status = data.get("status") or ("Entered" if movement_type == "entry" else "Exited")
    remarks = data.get("remarks")

    student_id = to_int(raw_student_id) if raw_student_id is not None else None
    if student_id is None:
        return error_response("student_id is required")

    if movement_type not in {"entry", "exit"}:
        return error_response("movement_type must be 'entry' or 'exit'")

    students = load_students()
    student = next((s for s in students if s["id"] == student_id), None)
    if not student:
        return error_response("Student not found", 404)

    logs = load_json(LOGS_FILE)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    if movement_type == "entry":
        log_entry = {
            "id": next_id(logs),
            "name": student["name"],
            "register_no": student["register_no"],
            "student_id": student["id"],
            "entry_time": timestamp,
            "exit_time": None,
            "entry_status": status or "Entered",
            "exit_status": "Pending",
            "remarks": remarks
        }
        logs.append(log_entry)
        save_json(LOGS_FILE, logs)
        return success_response("Entry recorded", log=log_entry)

    pending_log = next(
        (log for log in reversed(logs)
         if log.get("student_id") == student_id and (log.get("exit_time") is None or log.get("exit_status") == "Pending")),
        None
    )

    if not pending_log:
        return error_response("No pending entry found for the student", 404)

    pending_log["exit_time"] = timestamp
    pending_log["exit_status"] = status or "Exited"
    if remarks:
        pending_log["remarks"] = remarks
    save_json(LOGS_FILE, logs)
    return success_response("Exit recorded", log=pending_log)

# ---------------- STUDENT APIs ---------------- #
@app.route('/student/login', methods=['POST'])
def student_login():
    data = request.get_json() or {}
    name = (data.get('name') or "").strip()
    reg_no = data.get('register_no')
    if not name or reg_no is None:
        return error_response("Name and register number are required")

    students = load_students()
    for s in students:
        if s["name"].lower() == name.lower() and str(s["register_no"]) == str(reg_no):
            return success_response(
                "Student logged in",
                role="student",
                token=f"student-{s['id']}",
                student=s
            )
    return error_response("Student not found", 404)

@app.route('/student/logout', methods=['GET'])
def student_logout():
    return success_response("Student logged out")

@app.route('/my_logs', methods=['GET'])
def my_logs():
    student_id_param = request.args.get('student_id')
    student_id = to_int(student_id_param)
    if student_id is None:
        return error_response("Valid student_id query parameter is required")

    logs = load_json(LOGS_FILE)
    student_logs = [log for log in logs if log["student_id"] == student_id]
    return success_response("Student logs fetched", logs=student_logs)

# ---------------- Run App ---------------- #
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
