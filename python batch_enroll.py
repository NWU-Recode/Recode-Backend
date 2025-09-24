import csv
import requests

# ----------------- CONFIG -----------------
API_URL = "http://127.0.0.1:8000/admin_panel/students/batch"
TOKEN = "<YOUR_TOKEN>"  # Replace with your Bearer token
CSV_FILE = "Book1.csv"  # Path to your CSV file
# ------------------------------------------

def read_csv_as_json(csv_file):
    """Convert CSV rows to JSON array for API"""
    students = []
    with open(csv_file, newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=1):
            student_id = row.get("student_id")
            module_id = row.get("module_id")
            semester_id = row.get("semester_id")
            if not all([student_id, module_id, semester_id]):
                print(f"Skipping row {i}: missing data")
                continue
            students.append({
                "student_id": int(student_id),
                "module_id": module_id,
                "semester_id": semester_id
            })
    return students

def enroll_students_batch():
    students_json = read_csv_as_json(CSV_FILE)
    if not students_json:
        print("No valid student data found in CSV.")
        return

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(API_URL, headers=headers, json=students_json)
    print(f"Status code: {response.status_code}")

    try:
        data = response.json()
        if isinstance(data, list):
            for student in data:
                print(f"Enrolled student_id={student.get('student_id')} status={student.get('status')}")
        else:
            print(data)
    except Exception:
        print(response.text)

if __name__ == "__main__":
    enroll_students_batch()
