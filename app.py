from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, session,send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pandas as pd
import io
import google.generativeai as genai
import re
import time
import requests


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ghostpayroll.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.urandom(24) # Add a strong secret key for session management

# Initialize SQLAlchemy
db = SQLAlchemy(app)


# reCAPTCHA verification
def verify_recaptcha(token):
    secret_key = "6Lfqz1grAAAAAJVszTEMo79zPR78AbBu4y_kkfEa"
    payload = {'secret': secret_key, 'response': token}
    response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=payload)
    return response.json().get('success', False)

@app.route('/verify-recaptcha', methods=['POST'])
def verify_recaptcha_route():
    token = request.json.get('token')
    if not token:
        return jsonify({'success': False, 'error': 'No token provided'}), 400
    if verify_recaptcha(token):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid reCAPTCHA'}), 400


# Models based on updated schema
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

# Helper functions for analysis
REQUIRED_FILES = ['employee', 'attendance', 'salary', 'wifi']

# In-memory storage for current analysis session
current_files = {}
last_analysis_result = None

def all_files_uploaded():
    return all(file_type in current_files for file_type in REQUIRED_FILES)

def get_uploaded_file_data(file_type):
    return current_files.get(file_type)

genai.configure(api_key="AIzaSyAdYNj3eUf0_-W3yO25_Yag-23rIIUOzLQ")

model_name = "models/gemini-1.5-flash"
model = genai.GenerativeModel(model_name)

last_request_time = 0
MIN_REQUEST_INTERVAL = 10  # seconds

def analyze_all():
    global last_request_time
    if not all_files_uploaded():
        return {'anomalies': [], 'summary': 'All required files not uploaded', 'risk_distribution': {}, 'trends': []}

    try:
        df_emp = pd.read_csv(io.StringIO(current_files['employee']))
        df_att = pd.read_csv(io.StringIO(current_files['attendance']))
        df_sal = pd.read_csv(io.StringIO(current_files['salary']))
        df_wifi = pd.read_csv(io.StringIO(current_files['wifi']))

        # Convert date/time fields
        df_att['attendance_date'] = pd.to_datetime(df_att['attendance_date'], errors='coerce')
        df_att['check_in_time'] = pd.to_datetime(df_att['check_in_time'], errors='coerce')
        df_att['check_out_time'] = pd.to_datetime(df_att['check_out_time'], errors='coerce')
        df_sal['payment_date'] = pd.to_datetime(df_sal['payment_date'], errors='coerce')
        df_wifi['connection_date'] = pd.to_datetime(df_wifi['connection_date'], errors='coerce')
        df_wifi['connection_time'] = pd.to_datetime(df_wifi['connection_time'], errors='coerce')
        df_wifi['disconnection_time'] = pd.to_datetime(df_wifi['disconnection_time'], errors='coerce')

        required_emp = ['emp_id', 'employee_name', 'department', 'employment_status']
        required_att = ['emp_id', 'attendance_date', 'check_in_time', 'check_out_time']
        required_sal = ['emp_id', 'payroll_month', 'net_salary', 'payment_date']
        required_wifi = ['emp_id', 'connection_date', 'device_mac', 'connection_time', 'disconnection_time']

        for col in required_emp:
            if col not in df_emp.columns:
                return {'anomalies': [], 'summary': f"Missing column '{col}' in Employee Master Data", 'risk_distribution': {}, 'trends': []}
        for col in required_att:
            if col not in df_att.columns:
                return {'anomalies': [], 'summary': f"Missing column '{col}' in Attendance Records", 'risk_distribution': {}, 'trends': []}
        for col in required_sal:
            if col not in df_sal.columns:
                return {'anomalies': [], 'summary': f"Missing column '{col}' in Salary Payout Data", 'risk_distribution': {}, 'trends': []}
        for col in required_wifi:
            if col not in df_wifi.columns:
                return {'anomalies': [], 'summary': f"Missing column '{col}' in Wi-Fi Session Logs", 'risk_distribution': {}, 'trends': []}

        merged = pd.merge(df_att, df_wifi, left_on=['emp_id', 'attendance_date'], right_on=['emp_id', 'connection_date'], how='outer', suffixes=('_att', '_wifi'))
        merged['month'] = merged['attendance_date'].dt.strftime('%Y-%m')
        df_sal.rename(columns={'payroll_month': 'month'}, inplace=True)
        merged = pd.merge(merged, df_sal, on=['emp_id', 'month'], how='outer')
        merged = pd.merge(merged, df_emp, on='emp_id', how='left')

        total_employees = len(df_emp)
        avg_salary = df_sal['net_salary'].mean()
        avg_attendance_hours = (df_att['check_out_time'] - df_att['check_in_time']).mean().total_seconds() / 3600

        sample_text = ''
        for name, df in zip([
            'Employee Master Data (emp_id, employee_name, department, employment_status)',
            'Attendance Records (emp_id, attendance_date, check_in_time, check_out_time)',
            'Salary Payout Data (emp_id, payroll_month, net_salary, payment_date)',
            'Wi-Fi Session Logs (emp_id, connection_date, device_mac, connection_time, disconnection_time)'],
            [df_emp, df_att, df_sal, df_wifi]):
            sample_text += f"\n{name}:\n" + df.head(5).to_csv(index=False)

        merged_sample = merged.head(10).to_csv(index=False)

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

        current_time = time.time()
        time_since_last_request = current_time - last_request_time
        if time_since_last_request < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - time_since_last_request)

        try:
            response = model.generate_content(prompt)
            last_request_time = time.time()
            print("Gemini raw output:", response.text)
            import json as pyjson
            match = re.search(r'\{[\s\S]*\}', response.text)
            if match:
                ai_json = pyjson.loads(match.group(0))
                # Map anomalies to joining year trends
                trends = []
                if 'joining_date' in df_emp.columns and not df_emp['joining_date'].isna().all():
                    df_emp['joining_year'] = pd.to_datetime(df_emp['joining_date'], errors='coerce').dt.year
                    current_year = pd.Timestamp.now().year
                    years = list(range(current_year - 10 + 1, current_year + 1))
                    year_counts = {year: 0 for year in years}
                    anomaly_join_years = []
                    for anomaly in ai_json.get('anomalies', []):
                        emp_id = anomaly.get('emp_id')
                        join_year = df_emp.loc[df_emp['emp_id'] == emp_id, 'joining_year']
                        if not join_year.empty and join_year.iloc[0] in year_counts:
                            anomaly_join_years.append(join_year.iloc[0])
                    for year in years:
                        year_counts[year] = anomaly_join_years.count(year)
                    trends = [{'year': str(year), 'count': year_counts[year]} for year in years]
                return {
                    'anomalies': ai_json.get('anomalies', []),
                    'summary': ai_json.get('summary', 'No summary available.'),
                    'risk_distribution': ai_json.get('risk_distribution', {}),
                    'trends': trends
                }
            else:
                return {
                    'anomalies': [],
                    'summary': 'Gemini did not return valid JSON. Raw output: ' + response.text,
                    'risk_distribution': {},
                    'trends': []
                }
        except Exception as e:
            return {
                'anomalies': [],
                'summary': f'Gemini error: {str(e)}',
                'risk_distribution': {},
                'trends': []
            }
    except Exception as e:
        return {'anomalies': [], 'summary': str(e), 'risk_distribution': {}, 'trends': []}

# Routes
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
        # Read file content into memory
        content = file.read().decode('utf-8')
        current_files[file_type] = content
        
        # Log upload in database (without storing the file)
        upload = FileUpload(
            filename=file.filename,
            file_type=file_type,
            status='uploaded'
        )
        db.session.add(upload)
        db.session.commit()
        
        return jsonify({'message': f'{file_type.capitalize()} file uploaded successfully'})
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 400

@app.route('/api/analyze', methods=['POST'])
def analyze():
    global last_analysis_result  # ✅ allow us to assign to the global variable
    if not all_files_uploaded():
        return jsonify({'error': 'All required files not uploaded'}), 400
    result = analyze_all()
    last_analysis_result = result  # ✅ store the result for reuse in PDF
    current_files.clear()
    return jsonify(result)


@app.route('/api/dashboard/stats')
def dashboard_stats():
    total_employees = Employee.query.count()
    flagged_anomalies = Anomaly.query.filter_by(status='pending').count()
    potential_savings = db.session.query(db.func.sum(Employee.salary)).filter(
        Employee.id.in_(
            db.session.query(Anomaly.employee_id).filter_by(status='pending')
        )
    ).scalar() or 0
    return jsonify({
        'totalEmployees': total_employees,
        'flaggedAnomalies': flagged_anomalies,
        'potentialSavings': potential_savings,
        'dataAccuracy': 99.8,
        'pendingAnomalies': flagged_anomalies
    })

@app.route('/api/anomalies')
def get_anomalies():
    anomalies = Anomaly.query.all()
    return jsonify([{
        'id': a.id,
        'employee_id': a.employee_id,
        'type': a.type,
        'risk_level': a.risk_level,
        'status': a.status,
        'description': a.description,
        'created_at': a.created_at.isoformat()
    } for a in anomalies])

@app.route('/analyze', methods=['POST'])
def analyze_form():
    # Get the reCAPTCHA response token from the form POST
    recaptcha_response = request.form.get('g-recaptcha-response')

    # Verify with Google
    secret_key = "6Lfqz1grAAAAAJVszTEMo79zPR78AbBu4y_kkfEa"
    payload = {
        'secret': secret_key,
        'response': recaptcha_response
    }
    r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=payload)
    result = r.json()

    if not result.get('success'):
        return jsonify({'error': 'Invalid reCAPTCHA. Please try again.'}), 400

    # Proceed with your existing analyze logic:
    # e.g. use analyze_all(), process files, etc.
    analysis_result = analyze_all()

    return jsonify(analysis_result)

@app.route('/api/file-uploads')
def get_file_uploads():
    uploads = FileUpload.query.order_by(FileUpload.created_at.desc()).limit(5).all()
    return jsonify([{
        'id': u.id,
        'filename': u.filename,
        'file_type': u.file_type,
        'status': u.status,
        'created_at': u.created_at.isoformat()
    } for u in uploads])

@app.route('/api/download-report', methods=['GET'])
def download_report():
    global last_analysis_result
    result = last_analysis_result
    if not result or 'summary' not in result:
        return jsonify({'error': 'No analysis data available'}), 400

    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=40)
    elements = []

    styles = getSampleStyleSheet()
    normal = styles['Normal']
    title = styles['Title']
    heading = ParagraphStyle(name='Heading', parent=styles['Heading2'], spaceAfter=10, fontSize=14, leftIndent=0)

    # Title
    elements.append(Paragraph("Phantom pay Report", title))
    elements.append(Spacer(1, 12))

    # Summary
    elements.append(Paragraph("Executive Summary", heading))
    elements.append(Paragraph(result['summary'], normal))
    elements.append(Spacer(1, 12))

    # Risk Distribution
    elements.append(Paragraph("Risk Distribution", heading))
    rd_table = Table([
        ["Risk Level", "Count"]
    ] + [[k.title(), str(v)] for k, v in result['risk_distribution'].items()])
    rd_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
    ]))
    elements.append(rd_table)
    elements.append(Spacer(1, 12))

    # Anomalies Table
    elements.append(Paragraph("Detected Anomalies", heading))
    anomalies = result['anomalies']
    if anomalies:
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle

        desc_style = ParagraphStyle(name="DescStyle", fontSize=8, leading=10)
        table_data = [["Emp ID", "Name", "Type", "Risk", "Status", "Description"]]
        for a in anomalies:
            desc = a.get('description', '')
            short_desc = Paragraph(desc[:180] + ('...' if len(desc) > 180 else ''), desc_style)
            table_data.append([
                a.get('emp_id', ''),
                a.get('name', ''),
                a.get('type', ''),
                a.get('risk_level', '').capitalize(),
                a.get('status', '').capitalize(),
                short_desc
            ])
        table = Table(table_data, repeatRows=1, colWidths=[60, 80, 80, 50, 60, 220])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No anomalies detected.", normal))


    # Trends
    trends = result.get('trends', [])
    if trends:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Trends by Year", heading))
        trend_table = Table([
            ["Year", "Anomaly Count"]
        ] + [[t["year"], str(t["count"])] for t in trends])
        trend_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.beige),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
        ]))
        elements.append(trend_table)

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="PhantompayReport.pdf", mimetype='application/pdf')

@app.route('/api/login')
def login():
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
