from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

# ---------------- Files ---------------- #
STUDENTS_FILE = "students.json"
LOGS_FILE = "logs.json"

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

# ---------------- ADMIN APIs ---------------- #
@app.route('/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    print(f"[ADMIN LOGIN ATTEMPT] Username: {username}, Password: {password}")

    if username == "admin" and password == "1234":
        return jsonify({
            "status": "success",
            "message": "Admin logged in",
            "admin": {"username": username}
        })
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route('/logout', methods=['GET'])
def admin_logout():
    return jsonify({"status": "success", "message": "Admin logged out"})

@app.route('/add_student', methods=['POST'])
def add_student():
    students = load_json(STUDENTS_FILE)
    form = request.form

    new_student = {
        "id": len(students) + 1,
        "name": form.get("name"),
        "register_no": form.get("register_no"),
        "room_no": form.get("room_no"),
        "course": form.get("course"),
    }
    students.append(new_student)
    save_json(STUDENTS_FILE, students)

    return jsonify({"status": "success", "message": "Student added", "student": new_student}), 201

@app.route('/edit_student/<int:id>', methods=['POST'])
def edit_student(id):
    students = load_json(STUDENTS_FILE)
    form = request.form
    for s in students:
        if s["id"] == id:
            s["name"] = form.get("name", s["name"])
            s["register_no"] = form.get("register_no", s["register_no"])
            s["room_no"] = form.get("room_no", s["room_no"])
            s["course"] = form.get("course", s["course"])
            save_json(STUDENTS_FILE, students)
            return jsonify({"status": "success", "message": "Student updated", "student": s})
    return jsonify({"status": "error", "message": "Student not found"}), 404

@app.route('/delete_student/<int:id>', methods=['DELETE'])
def delete_student(id):
    students = load_json(STUDENTS_FILE)
    students = [s for s in students if s["id"] != id]
    save_json(STUDENTS_FILE, students)
    return jsonify({"status": "success", "message": "Student deleted"})

@app.route('/students', methods=['GET'])
def get_students():
    students = load_json(STUDENTS_FILE)
    return jsonify({"status": "success", "students": students})

@app.route('/view_logs', methods=['GET'])
def view_logs():
    logs = load_json(LOGS_FILE)
    return jsonify({"status": "success", "logs": logs})

# ---------------- STUDENT APIs ---------------- #
@app.route('/student/login', methods=['POST'])
def student_login():
    data = request.json
    name = data.get('name')
    reg_no = data.get('register_no')
    students = load_json(STUDENTS_FILE)
    for s in students:
        if s["name"] == name and str(s["register_no"]) == str(reg_no):
            return jsonify({"status": "success", "message": "Student logged in", "student": s})
    return jsonify({"status": "error", "message": "Student not found"}), 404

@app.route('/student/logout', methods=['GET'])
def student_logout():
    return jsonify({"status": "success", "message": "Student logged out"})

@app.route('/my_logs', methods=['GET'])
def my_logs():
    student_id = int(request.args.get('student_id'))
    logs = load_json(LOGS_FILE)
    student_logs = [log for log in logs if log["student_id"] == student_id]
    return jsonify({"status": "success", "logs": student_logs})

# ---------------- Run App ---------------- #
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
