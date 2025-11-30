from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# ---------------- MongoDB Config ---------------- #
MONGODB_URI = "mongodb+srv://singhdeepankarpost:deep123@cluster0.mpvpv.mongodb.net/?appName=Cluster0"
MONGODB_DBNAME ="hostelapp"

# Initialize MongoDB connection with better error handling
client = None
db = None
students_col = None
movements_col = None
watchmen_col = None
settings_col = None

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    # Test connection
    client.server_info()
    db = client[MONGODB_DBNAME]
    students_col = db["students"]
    movements_col = db["movements"]
    watchmen_col = db["watchmen"]
    settings_col = db["settings"]
    
    # Create indexes
    students_col.create_index("register_no", unique=True)
    students_col.create_index("id", unique=True)
    movements_col.create_index([("student_id", 1), ("timestamp", -1)])
    
    print("✓ Connected to MongoDB Atlas successfully!")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"✗ MongoDB connection failed: {e}")
    print("⚠️  Application will not function without database connection")
    # Don't raise - let the app start but endpoints will fail gracefully
except Exception as e:
    print(f"✗ Unexpected error during MongoDB setup: {e}")
    raise

# ---------------- Constants ---------------- #
MOVEMENT_TYPES = ["IN", "OUT"]
STUDENT_STATUS = ["IN_HOSTEL", "OUTSIDE"]
STATUS_OPTIONS = ["On Time", "Late", "Emergency", "Manual Entry"]

ADMIN_ACCOUNT = {
    "username": "admin",
    "password": "1234",
    "name": "Hostel Administrator"
}

WATCHMEN = [
    {
        "id": 1,
        "username": "watchman",
        "password": "1234",
        "name": "Main Gate Watchman",
        "location": "Main Gate",
        "shift": "Day"
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
    "emergency_contact": "",
    "profile_picture": None,
    "current_status": "IN_HOSTEL",
    "last_movement_id": None
}

# ---------------- Helper Functions ---------------- #
def check_db_connection():
    """Check if database is available"""
    if db is None or students_col is None:
        return False
    try:
        client.server_info()
        return True
    except:
        return False

def get_next_student_id():
    if not check_db_connection():
        raise ConnectionError("Database not available")
    last_student = students_col.find_one(sort=[("id", -1)])
    return 1 if not last_student else last_student.get("id", 0) + 1

def get_next_movement_id():
    if not check_db_connection():
        raise ConnectionError("Database not available")
    last_movement = movements_col.find_one(sort=[("id", -1)])
    return 1 if not last_movement else last_movement.get("id", 0) + 1

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

def serialize_document(doc):
    """Recursively serialize MongoDB documents, removing ObjectId"""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_document(item) for item in doc]
    if isinstance(doc, dict):
        doc = dict(doc)
        if '_id' in doc:
            del doc['_id']
        return {k: serialize_document(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc

def normalize_dob(value):
    if value in (None, "", "null", "None"):
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned or cleaned.lower() in {"null", "none"}:
            return None
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return cleaned
    return str(value)

def coerce_student_field(field, value):
    default = STUDENT_FIELD_DEFAULTS.get(field, "")
    if field == "dob":
        return normalize_dob(value)
    if value is None:
        return default
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned and cleaned.lower() not in {"null", "none"} else default
    return value

def create_student_record(data):
    record = {
        "name": (data.get("name") or "").strip(),
        "register_no": str(data.get("register_no", "")).strip(),
    }
    for field, default in STUDENT_FIELD_DEFAULTS.items():
        record[field] = coerce_student_field(field, data.get(field))
    return record

# ---------------- ADMIN APIs ---------------- #
@app.route('/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    username = (data.get('username') or "").strip()
    password = data.get('password')
    
    if username == ADMIN_ACCOUNT["username"] and password == ADMIN_ACCOUNT["password"]:
        return success_response(
            "Admin logged in",
            role="admin",
            token="admin-token",
            admin={"username": ADMIN_ACCOUNT["username"], "name": ADMIN_ACCOUNT["name"]}
        )
    return error_response("Invalid credentials", 401)

@app.route('/logout', methods=['GET'])
def admin_logout():
    return success_response("Admin logged out")

@app.route('/add_student', methods=['POST'])
def add_student():
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        data = get_request_data()
        name = (data.get("name") or "").strip()
        register_no = str(data.get("register_no", "")).strip()

        if not name or not register_no:
            return error_response("Name and register number are required")

        # Check for duplicate register number
        if students_col.find_one({"register_no": register_no}):
            return error_response("Student with this register number already exists", 409)

        new_student = create_student_record(data)
        new_student["id"] = get_next_student_id()
        new_student["created_at"] = datetime.now().isoformat()
        
        students_col.insert_one(new_student)
        return success_response("Student added", student=serialize_document(new_student), status_code=201)
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/edit_student/<int:id>', methods=['POST'])
def edit_student(id):
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        data = get_request_data()
        student = students_col.find_one({"id": id})
        
        if not student:
            return error_response("Student not found", 404)
        
        update_fields = {}
        if "name" in data:
            update_fields["name"] = (data.get("name") or "").strip()
        if "register_no" in data:
            new_reg_no = str(data.get("register_no", "")).strip()
            # Check if register_no is being changed and if new one exists
            if new_reg_no != student.get("register_no"):
                if students_col.find_one({"register_no": new_reg_no}):
                    return error_response("Student with this register number already exists", 409)
            update_fields["register_no"] = new_reg_no
        
        for field in STUDENT_FIELD_DEFAULTS:
            if field in data:
                update_fields[field] = coerce_student_field(field, data.get(field))
        
        update_fields["updated_at"] = datetime.now().isoformat()
        students_col.update_one({"id": id}, {"$set": update_fields})
        
        updated_student = students_col.find_one({"id": id})
        return success_response("Student updated", student=serialize_document(updated_student))
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/delete_student/<int:id>', methods=['DELETE'])
def delete_student(id):
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        result = students_col.delete_one({"id": id})
        if result.deleted_count == 0:
            return error_response("Student not found", 404)
        
        # Also delete associated movements (optional - you might want to keep them for history)
        # movements_col.delete_many({"student_id": id})
        
        return success_response("Student deleted")
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/students', methods=['GET'])
def get_students():
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        students = list(students_col.find({}))
        return success_response("Students fetched", students=serialize_document(students))
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

# ---------------- WATCHMAN APIs ---------------- #
@app.route('/watchman/login', methods=['POST'])
def watchman_login():
    data = request.get_json() or {}
    username = (data.get('username') or "").strip()
    password = data.get('password')

    for watchman in WATCHMEN:
        if watchman["username"] == username and watchman["password"] == password:
            return success_response(
                "Watchman logged in",
                role="watchman",
                token=f"watchman-{watchman['username']}",
                watchman={
                    "id": watchman["id"],
                    "username": watchman["username"],
                    "name": watchman["name"],
                    "location": watchman["location"]
                }
            )
    return error_response("Invalid credentials", 401)

@app.route('/watchman/logout', methods=['GET'])
def watchman_logout():
    return success_response("Watchman logged out")

@app.route('/watchman/record', methods=['POST'])
def record_student_movement():
    """Legacy endpoint for frontend compatibility - maps to record-movement"""
    data = request.get_json() or {}
    # Map old format to new format
    movement_type = data.get("movement_type", "").lower()
    if movement_type == "entry":
        data["movement_type"] = "IN"
    elif movement_type == "exit":
        data["movement_type"] = "OUT"
    
    # Call the main record_movement function
    return record_movement()

@app.route('/watchman/record-movement', methods=['POST'])
def record_movement():
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        data = request.get_json() or {}
        student_id = to_int(data.get("student_id"))
        movement_type = (data.get("movement_type") or "").upper()
        status = data.get("status", "On Time")
        remarks = data.get("remarks", "")
        watchman_id = data.get("watchman_id", 1)

        if student_id is None:
            return error_response("student_id is required")

        if movement_type not in MOVEMENT_TYPES:
            return error_response("movement_type must be 'IN' or 'OUT'")

        student = students_col.find_one({"id": student_id})
        if not student:
            return error_response("Student not found", 404)

        current_status = student.get("current_status", "IN_HOSTEL")

        # Validation
        if movement_type == "OUT" and current_status == "OUTSIDE":
            return error_response("Student is already outside! Cannot record exit again.", 400)
        
        if movement_type == "IN" and current_status == "IN_HOSTEL":
            return error_response("Student is already in hostel! Cannot record entry again.", 400)

        # Record movement
        movement = {
            "id": get_next_movement_id(),
            "student_id": student_id,
            "student_name": student["name"],
            "register_no": student["register_no"],
            "movement_type": movement_type,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "watchman_id": watchman_id,
            "gate": "Main Gate",
            "remarks": remarks
        }

        movements_col.insert_one(movement)

        # Update student status
        new_status = "OUTSIDE" if movement_type == "OUT" else "IN_HOSTEL"
        students_col.update_one(
            {"id": student_id},
            {"$set": {
                "current_status": new_status,
                "last_movement_id": movement["id"],
                "last_updated": datetime.now().isoformat()
            }}
        )

        action_text = "left hostel (going OUT)" if movement_type == "OUT" else "returned to hostel (came IN)"
        return success_response(
            f"Movement recorded: {student['name']} {action_text}",
            movement=serialize_document(movement),
            new_status=new_status
        )
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/watchman/dashboard', methods=['GET'])
def watchman_dashboard():
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        total_students = students_col.count_documents({})
        students_in_hostel = students_col.count_documents({"current_status": "IN_HOSTEL"})
        students_outside = students_col.count_documents({"current_status": "OUTSIDE"})
        
        # Get today's date range for proper querying
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Query movements for today using proper date range
        today_movements = list(movements_col.find({
            "timestamp": {
                "$gte": today_start.isoformat(),
                "$lt": today_end.isoformat()
            }
        }))
        
        today_went_out = sum(1 for m in today_movements if m.get("movement_type") == "OUT")
        today_returned = sum(1 for m in today_movements if m.get("movement_type") == "IN")
        
        return success_response("Dashboard data fetched",
            total_students=total_students,
            students_in_hostel=students_in_hostel,
            students_outside=students_outside,
            today_went_out=today_went_out,
            today_returned=today_returned
        )
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/admin/dashboard', methods=['GET'])
def admin_dashboard():
    """Admin dashboard endpoint - same data as watchman dashboard"""
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        total_students = students_col.count_documents({})
        students_in_hostel = students_col.count_documents({"current_status": "IN_HOSTEL"})
        students_outside = students_col.count_documents({"current_status": "OUTSIDE"})
        
        # Get today's date range for proper querying
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Query movements for today using proper date range
        today_movements = list(movements_col.find({
            "timestamp": {
                "$gte": today_start.isoformat(),
                "$lt": today_end.isoformat()
            }
        }))
        
        today_went_out = sum(1 for m in today_movements if m.get("movement_type") == "OUT")
        today_returned = sum(1 for m in today_movements if m.get("movement_type") == "IN")
        
        return success_response("Dashboard data fetched",
            total_students=total_students,
            students_in_hostel=students_in_hostel,
            students_outside=students_outside,
            today_went_out=today_went_out,
            today_returned=today_returned
        )
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/student/dashboard', methods=['GET'])
def student_dashboard():
    """Student dashboard endpoint - same data as admin/watchman dashboard"""
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        total_students = students_col.count_documents({})
        students_in_hostel = students_col.count_documents({"current_status": "IN_HOSTEL"})
        students_outside = students_col.count_documents({"current_status": "OUTSIDE"})
        
        # Get today's date range for proper querying
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Query movements for today using proper date range
        today_movements = list(movements_col.find({
            "timestamp": {
                "$gte": today_start.isoformat(),
                "$lt": today_end.isoformat()
            }
        }))
        
        today_went_out = sum(1 for m in today_movements if m.get("movement_type") == "OUT")
        today_returned = sum(1 for m in today_movements if m.get("movement_type") == "IN")
        
        return success_response("Dashboard data fetched",
            total_students=total_students,
            students_in_hostel=students_in_hostel,
            students_outside=students_outside,
            today_went_out=today_went_out,
            today_returned=today_returned
        )
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/watchman/movements', methods=['GET'])
def get_all_movements():
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        limit = to_int(request.args.get('limit', 50))
        movements = list(movements_col.find({}).sort("id", -1).limit(limit))
        return success_response("Movements fetched", movements=serialize_document(movements))
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/watchman/students-outside', methods=['GET'])
def get_students_outside():
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        students_outside = list(students_col.find({"current_status": "OUTSIDE"}))
        
        # Get their last movement details
        for student in students_outside:
            last_movement = movements_col.find_one({"id": student.get("last_movement_id")})
            if last_movement:
                student["went_out_at"] = last_movement.get("timestamp")
                student["remarks"] = last_movement.get("remarks")
        
        return success_response(
            "Students currently outside",
            students=serialize_document(students_outside),
            count=len(students_outside)
        )
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/view_logs', methods=['GET'])
def view_logs():
    """Legacy endpoint - converts movements to old log format for frontend compatibility"""
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        # Get all movements sorted by timestamp
        movements = list(movements_col.find({}).sort("timestamp", -1))
        
        # Convert movements to old log format (entry_time/exit_time pairs)
        logs = []
        student_pending_entries = {}  # Track pending entries by student_id
        
        for movement in movements:
            student_id = movement.get("student_id")
            movement_type = movement.get("movement_type")
            timestamp = movement.get("timestamp")
            
            if movement_type == "OUT":
                # Create a log entry with entry_time and exit_time
                # Try to find matching entry or create new
                if student_id in student_pending_entries:
                    # Update existing pending entry with exit
                    log_entry = student_pending_entries[student_id]
                    log_entry["exit_time"] = timestamp
                    log_entry["exit_status"] = movement.get("status", "Exited")
                    logs.append(log_entry)
                    del student_pending_entries[student_id]
                else:
                    # Create new log with only exit (orphaned exit)
                    log_entry = {
                        "id": movement.get("id"),
                        "name": movement.get("student_name", ""),
                        "register_no": movement.get("register_no", ""),
                        "student_id": student_id,
                        "entry_time": None,
                        "exit_time": timestamp,
                        "entry_status": "Pending",
                        "exit_status": movement.get("status", "Exited"),
                        "remarks": movement.get("remarks", "")
                    }
                    logs.append(log_entry)
            elif movement_type == "IN":
                # Create pending entry
                log_entry = {
                    "id": movement.get("id"),
                    "name": movement.get("student_name", ""),
                    "register_no": movement.get("register_no", ""),
                    "student_id": student_id,
                    "entry_time": timestamp,
                    "exit_time": None,
                    "entry_status": movement.get("status", "Entered"),
                    "exit_status": "Pending",
                    "remarks": movement.get("remarks", "")
                }
                student_pending_entries[student_id] = log_entry
        
        # Add any remaining pending entries (entries without exits)
        for pending_entry in student_pending_entries.values():
            logs.append(pending_entry)
        
        # Sort by entry_time or exit_time (most recent first)
        logs.sort(key=lambda x: x.get("exit_time") or x.get("entry_time") or "", reverse=True)
        
        return success_response("Logs fetched", logs=serialize_document(logs))
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

# ---------------- STUDENT APIs ---------------- #
@app.route('/student/login', methods=['POST'])
def student_login():
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        data = request.get_json() or {}
        name = (data.get('name') or "").strip()
        reg_no = str(data.get('register_no', "")).strip()
        
        if not name or not reg_no:
            return error_response("Name and register number are required")

        student = students_col.find_one({
            "name": {"$regex": f"^{name}$", "$options": "i"},
            "register_no": reg_no
        })

        if student:
            return success_response(
                "Student logged in",
                role="student",
                token=f"student-{student['id']}",
                student=serialize_document(student)
            )
        return error_response("Student not found", 404)
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/student/logout', methods=['GET'])
def student_logout():
    return success_response("Student logged out")

@app.route('/student/my-movements', methods=['GET'])
def my_movements():
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        student_id = to_int(request.args.get('student_id'))
        if student_id is None:
            return error_response("Valid student_id query parameter is required")

        movements = list(movements_col.find({"student_id": student_id}).sort("id", -1))
        return success_response("Student movements fetched", movements=serialize_document(movements))
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/my_logs', methods=['GET'])
def my_logs():
    """Get logs for a specific student in the format expected by frontend"""
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        student_id = to_int(request.args.get('student_id'))
        if student_id is None:
            return error_response("Valid student_id query parameter is required", 400)

        # Verify student exists
        student = students_col.find_one({"id": student_id})
        if not student:
            return error_response("Student not found", 404)

        # Get all movements for this student sorted by timestamp
        movements = list(movements_col.find({"student_id": student_id}).sort("timestamp", -1))
        
        # Convert movements to log format (entry_time/exit_time pairs)
        logs = []
        student_pending_entries = {}  # Track pending entries by student_id
        
        for movement in movements:
            movement_type = movement.get("movement_type")
            timestamp = movement.get("timestamp")
            
            if movement_type == "OUT":
                # Create a log entry with entry_time and exit_time
                # Try to find matching entry or create new
                if student_id in student_pending_entries:
                    # Update existing pending entry with exit
                    log_entry = student_pending_entries[student_id]
                    log_entry["exit_time"] = timestamp
                    log_entry["exit_status"] = movement.get("status", "Exited")
                    logs.append(log_entry)
                    del student_pending_entries[student_id]
                else:
                    # Create new log with only exit (orphaned exit)
                    log_entry = {
                        "id": movement.get("id"),
                        "name": movement.get("student_name", ""),
                        "register_no": movement.get("register_no", ""),
                        "student_id": student_id,
                        "entry_time": None,
                        "exit_time": timestamp,
                        "entry_status": "Pending",
                        "exit_status": movement.get("status", "Exited"),
                        "remarks": movement.get("remarks", "")
                    }
                    logs.append(log_entry)
            elif movement_type == "IN":
                # Create pending entry
                log_entry = {
                    "id": movement.get("id"),
                    "name": movement.get("student_name", ""),
                    "register_no": movement.get("register_no", ""),
                    "student_id": student_id,
                    "entry_time": timestamp,
                    "exit_time": None,
                    "entry_status": movement.get("status", "Entered"),
                    "exit_status": "Pending",
                    "remarks": movement.get("remarks", "")
                }
                student_pending_entries[student_id] = log_entry
        
        # Add any remaining pending entries (entries without exits)
        for pending_entry in student_pending_entries.values():
            logs.append(pending_entry)
        
        # Sort by entry_time or exit_time (most recent first)
        logs.sort(key=lambda x: x.get("exit_time") or x.get("entry_time") or "", reverse=True)
        
        return success_response("Student logs fetched", logs=serialize_document(logs))
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

@app.route('/student/current-status/<int:student_id>', methods=['GET'])
def get_student_status(student_id):
    if not check_db_connection():
        return error_response("Database connection unavailable", 503)
    
    try:
        student = students_col.find_one({"id": student_id})
        if not student:
            return error_response("Student not found", 404)
        
        last_movement = movements_col.find_one({"id": student.get("last_movement_id")})
        
        return success_response(
            "Student status fetched",
            current_status=student.get("current_status", "IN_HOSTEL"),
            last_movement=serialize_document(last_movement)
        )
    
    except PyMongoError as e:
        return error_response(f"Database error: {str(e)}", 500)
    except Exception as e:
        return error_response(f"Unexpected error: {str(e)}", 500)

# ---------------- Health Check ---------------- #
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify database connection"""
    if check_db_connection():
        return success_response("Service is healthy", database="connected")
    return error_response("Service unhealthy - database not connected", 503)

# ---------------- Run App ---------------- #
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
