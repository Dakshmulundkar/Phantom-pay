# app.py (Updated to restore the user's preferred detailed prompt)

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pandas as pd
import io
import google.generativeai as genai
import re
import time
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ghostpayroll.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.urandom(24)

db = SQLAlchemy(app)

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please set it in your .env file.")
genai.configure(api_key=GEMINI_API_KEY)

model_name = "models/gemini-1.5-flash"
model = genai.GenerativeModel(model_name)

PROCESSED_DATA_DIR = 'processed_data'
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)


# --- Database Models (Unchanged) ---
class Employee(db.Model):
    emp_id = db.Column(db.String, primary_key=True)
    employee_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100))
    designation = db.Column(db.String(100))
    joining_date = db.Column(db.Date)
    employment_status = db.Column(db.String(50))
    base_salary = db.Column(db.Float)
    cost_center = db.Column(db.String(100))
    reporting_manager = db.Column(db.String(100))
    employee_type = db.Column(db.String(50))
    location = db.Column(db.String(100))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String, db.ForeignKey('employee.emp_id'))
    attendance_date = db.Column(db.Date)
    check_in_time = db.Column(db.Time)
    check_out_time = db.Column(db.Time)
    work_mode = db.Column(db.String(50))
    attendance_status = db.Column(db.String(50))
    location = db.Column(db.String(100))
    device_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(100))
    break_duration = db.Column(db.Float)
    overtime_hours = db.Column(db.Float)
    shift_type = db.Column(db.String(50))

class WifiUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String, db.ForeignKey('employee.emp_id'))
    connection_date = db.Column(db.Date)
    device_mac = db.Column(db.String(100))
    connection_time = db.Column(db.Time)
    disconnection_time = db.Column(db.Time)
    access_point = db.Column(db.String(100))
    signal_strength = db.Column(db.Float)
    data_usage = db.Column(db.Float)
    connection_type = db.Column(db.String(50))
    location = db.Column(db.String(100))

class Salary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String, db.ForeignKey('employee.emp_id'))
    payroll_month = db.Column(db.String(7))  # Format YYYY-MM
    basic_salary = db.Column(db.Float)
    allowances = db.Column(db.Float)
    deductions = db.Column(db.Float)
    net_salary = db.Column(db.Float)
    payment_date = db.Column(db.Date)
    bank_account = db.Column(db.String(100))
    payment_status = db.Column(db.String(50))
    tax_deduction = db.Column(db.Float)
    bonus = db.Column(db.Float)
    incentives = db.Column(db.Float)

class Anomaly(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String, db.ForeignKey('employee.emp_id'))
    type = db.Column(db.String(50), nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FileUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='uploaded')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Helper Functions (Unchanged) ---
REQUIRED_FILES = ['employee', 'attendance', 'salary', 'wifi']
current_files = {}

def all_files_uploaded():
    return all(file_type in current_files for file_type in REQUIRED_FILES)

last_request_time = 0
MIN_REQUEST_INTERVAL = 10  # seconds

# --- THIS IS THE RESTORED ANALYSIS FUNCTION WITH YOUR ORIGINAL DETAILED PROMPT ---
def analyze_all():
    global last_request_time
    if not all_files_uploaded():
        return {'anomalies': [], 'summary': 'All required files not uploaded', 'risk_distribution': {}, 'trends': []}

    try:
        # Step 1: Read and process dataframes
        df_emp = pd.read_csv(io.StringIO(current_files['employee']))
        df_att = pd.read_csv(io.StringIO(current_files['attendance']))
        df_sal = pd.read_csv(io.StringIO(current_files['salary']))
        df_wifi = pd.read_csv(io.StringIO(current_files['wifi']))

        # Data cleaning and type conversion
        df_att['attendance_date'] = pd.to_datetime(df_att['attendance_date'], errors='coerce')
        df_att['check_in_time'] = pd.to_datetime(df_att['check_in_time'], errors='coerce', format='%H:%M:%S', exact=False).dt.time
        df_att['check_out_time'] = pd.to_datetime(df_att['check_out_time'], errors='coerce', format='%H:%M:%S', exact=False).dt.time
        df_sal['payment_date'] = pd.to_datetime(df_sal['payment_date'], errors='coerce')
        df_wifi['connection_date'] = pd.to_datetime(df_wifi['connection_date'], errors='coerce')
        
        # Step 2: Create merged dataframe for context
        merged = pd.merge(df_att, df_wifi, left_on=['emp_id', 'attendance_date'], right_on=['emp_id', 'connection_date'], how='outer', suffixes=('_att', '_wifi'))
        merged['month'] = merged['attendance_date'].dt.strftime('%Y-%m')
        df_sal.rename(columns={'payroll_month': 'month'}, inplace=True)
        merged = pd.merge(merged, df_sal, on=['emp_id', 'month'], how='outer')
        merged = pd.merge(merged, df_emp, on='emp_id', how='left')

        # Step 3: Calculate metrics for the prompt
        total_employees = len(df_emp)
        avg_salary = df_sal['net_salary'].mean()
        
        avg_attendance_hours = 0
        try:
            df_att_copy = df_att.dropna(subset=['attendance_date', 'check_in_time', 'check_out_time']).copy()
            df_att_copy['check_in_datetime'] = df_att_copy.apply(lambda row: datetime.combine(row['attendance_date'], row['check_in_time']), axis=1)
            df_att_copy['check_out_datetime'] = df_att_copy.apply(lambda row: datetime.combine(row['attendance_date'], row['check_out_time']), axis=1)
            avg_attendance_hours = (df_att_copy['check_out_datetime'] - df_att_copy['check_in_datetime']).mean().total_seconds() / 3600
        except Exception:
            # If calculation fails, just proceed with 0
            pass

        # Step 4: Create data samples for the prompt
        sample_text = ''
        for name, df in zip([
            'Employee Master Data', 'Attendance Records', 'Salary Payout Data', 'Wi-Fi Session Logs'],
            [df_emp, df_att, df_sal, df_wifi]):
            sample_text += f"\n{name}:\n" + df.head(5).to_csv(index=False)

        merged_sample = merged.head(10).to_csv(index=False)
        
        # Step 5: Define the restored detailed prompt
        prompt = f'''
        You are a payroll fraud detection expert. Analyze the following data for potential ghost employees, payroll fraud, and suspicious activity.

        Key metrics for context:
        - Total employees: {total_employees}
        - Average salary: {avg_salary:.2f}
        - Average attendance hours: {avg_attendance_hours:.2f}

        Look for these specific types of anomalies:
        1. Ghost Employees:
           - Employees with no attendance records but receiving salary
           - Employees with no Wi-Fi activity but marked present
           - Employees with inconsistent attendance patterns

        2. Payroll Fraud:
           - Unusual salary payments (significantly above/below average)
           - Multiple salary payments in the same month
           - Payments to inactive/terminated employees

        3. Attendance Fraud:
           - Impossible work hours (e.g., >24 hours in a day)
           - Inconsistent login/logout times
           - No Wi-Fi activity during work hours
           - Multiple login locations on the same day

        4. Suspicious Patterns:
           - Employees with identical attendance patterns
           - Unusual department distributions
           - Suspicious timing of payments

        Respond with a JSON object containing:
        {{
            "anomalies": [
                {{
                    "emp_id": "string",
                    "name": "string",
                    "type": "string (ghost_employee|payroll_fraud|attendance_fraud|suspicious_pattern)",
                    "risk_level": "string (high|medium|low)",
                    "status": "string (pending|investigating|resolved)",
                    "description": "string (detailed explanation)",
                    "evidence": "string (specific data points supporting the anomaly)",
                    "recommendation": "string (suggested action)"
                }}
            ],
            "summary": "string (overall analysis summary)",
            "risk_distribution": {{
                "high": number,
                "medium": number,
                "low": number
            }},
            "trends": [
                {{
                    "year": "string (YYYY)",
                    "count": number
                }}
            ]
        }}

        Data samples:
        {sample_text}

        Merged data sample:
        {merged_sample}

        Focus on concrete evidence and specific patterns. Rate risk levels based on:
        - High: Clear evidence of fraud or multiple suspicious patterns
        - Medium: Suspicious patterns requiring investigation
        - Low: Minor inconsistencies or unusual but explainable patterns
        '''
        
        # Step 6: Call API and process response
        current_time = time.time()
        time_since_last_request = current_time - last_request_time
        if time_since_last_request < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - time_since_last_request)

        try:
            print("Sending detailed prompt to Gemini...")
            response = model.generate_content(prompt)
            last_request_time = time.time()
            print("Gemini raw output:", response.text)
            match = re.search(r'\{[\s\S]*\}', response.text)
            if match:
                ai_json = json.loads(match.group(0))
                trends = []
                if 'joining_date' in df_emp.columns and not df_emp['joining_date'].isna().all():
                    df_emp['joining_year'] = pd.to_datetime(df_emp['joining_date'], errors='coerce').dt.year
                    current_year = pd.Timestamp.now().year
                    years = list(range(current_year - 4, current_year + 1))
                    year_counts = {year: 0 for year in years}
                    if 'anomalies' in ai_json and ai_json['anomalies']:
                        for anomaly in ai_json['anomalies']:
                            emp_id = anomaly.get('emp_id')
                            if emp_id:
                                join_year_series = df_emp.loc[df_emp['emp_id'] == emp_id, 'joining_year']
                                if not join_year_series.empty and pd.notna(join_year_series.iloc[0]):
                                    join_year = join_year_series.iloc[0]
                                    if join_year in year_counts:
                                        year_counts[join_year] += 1
                    trends = [{'year': str(year), 'count': count} for year, count in year_counts.items()]

                return {
                    'anomalies': ai_json.get('anomalies', []),
                    'summary': ai_json.get('summary', 'No summary available.'),
                    'risk_distribution': ai_json.get('risk_distribution', {}),
                    'trends': trends
                }
            else:
                return {
                    'anomalies': [], 'summary': 'Gemini did not return valid JSON. Raw output: ' + response.text,
                    'risk_distribution': {}, 'trends': []
                }
        except Exception as e:
            return {
                'anomalies': [], 'summary': f'Gemini error: {str(e)}',
                'risk_distribution': {}, 'trends': []
            }
    except Exception as e:
        return {'anomalies': [], 'summary': str(e), 'risk_distribution': {}, 'trends': []}


# --- Routes and Main block (Unchanged) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/signin')
def signin():
    return render_template('signin.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/upload/<file_type>', methods=['POST'])
def upload_file(file_type):
    if file_type not in REQUIRED_FILES:
        return jsonify({'error': 'Invalid file type'}), 400
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        content = file.read().decode('utf-8')
        current_files[file_type] = content
        
        upload = FileUpload(filename=file.filename, file_type=file_type, status='uploaded')
        db.session.add(upload)
        db.session.commit()
        
        return jsonify({'message': f'{file_type.capitalize()} file uploaded successfully'})
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 400

@app.route('/api/analyze', methods=['POST'])
def analyze():
    if not all_files_uploaded():
        return jsonify({'error': 'All required files not uploaded'}), 400
    result = analyze_all()
    current_files.clear()
    return jsonify(result)

@app.route('/api/dashboard/stats')
def dashboard_stats():
    # This is a placeholder, as the actual data isn't being committed to the DB in this flow
    return jsonify({
        'totalEmployees': 0,
        'flaggedAnomalies': 0,
        'potentialSavings': 0,
        'dataAccuracy': 99.8,
        'pendingAnomalies': 0
    })

@app.route('/api/anomalies')
def get_anomalies():
    # This returns from the DB, which may not match the live analysis
    anomalies = Anomaly.query.all()
    return jsonify([{
        'id': a.id, 'employee_id': a.employee_id, 'type': a.type,
        'risk_level': a.risk_level, 'status': a.status, 'description': a.description,
        'created_at': a.created_at.isoformat()
    } for a in anomalies])

@app.route('/api/file-uploads')
def get_file_uploads():
    uploads = FileUpload.query.order_by(FileUpload.created_at.desc()).limit(5).all()
    return jsonify([{
        'id': u.id, 'filename': u.filename, 'file_type': u.file_type,
        'status': u.status, 'created_at': u.created_at.isoformat()
    } for u in uploads])

@app.route('/api/login')
def login():
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)