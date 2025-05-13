from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import os
import json
import uuid
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key_here')

# Configuration
DATA_PATH = 'interview_data.json'
PASSED_CANDIDATES_FILE = 'passed_candidates.json'
UPLOAD_FOLDER = 'static/resumes'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Utility functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_config():
    if not os.path.exists(DATA_PATH):
        return {"hr_score": 7, "fields": {}}
    with open(DATA_PATH, 'r') as f:
        return json.load(f)

def save_config(data):
    with open(DATA_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def load_passed_candidates():
    if os.path.exists(PASSED_CANDIDATES_FILE):
        with open(PASSED_CANDIDATES_FILE, 'r') as f:
            return json.load(f)
    return []

def save_passed_candidates(data):
    with open(PASSED_CANDIDATES_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def analyze_answers(answers):
    score = 0
    for a in answers:
        q = a.get('question_obj', {})
        ans = a.get('answer', '')
        if q.get('type') == 'exact':
            if ans.strip() == q.get('answer', '').strip():
                score += 1
        elif q.get('type') == 'keyword':
            keyword = q.get('answer', '').lower()
            if keyword in ans.lower():
                score += 1
    max_score = len(answers)
    return round((score / max_score) * 10, 1) if max_score else 0

# Auth decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'status': 'unauthorized', 'role': 'hr'}), 401
        return f(*args, **kwargs)
    return decorated_function

def login1_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'status': 'unauthorized', 'role': 'admin'}), 401
        return f(*args, **kwargs)
    return decorated_function

# API Health Check
@app.route('/')
def health():
    return jsonify({'status': 'API is live'})

# Login endpoints
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    if data.get('username') == 'admin' and data.get('password') == 'admin@admin':
        session['logged_in'] = True
        return jsonify({'status': 'success', 'message': 'HR Logged in'})
    return jsonify({'status': 'fail', 'message': 'Invalid credentials'}), 401

@app.route('/login1', methods=['POST'])
def login1():
    data = request.json
    if data.get('username') == 'admin' and data.get('password') == 'admin@admin':
        session['logged_in'] = True
        return jsonify({'status': 'success', 'message': 'Admin Logged in'})
    return jsonify({'status': 'fail', 'message': 'Invalid credentials'}), 401

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return jsonify({'status': 'success', 'message': 'Logged out'})

@app.route('/logout1')
def logout1():
    session.pop('logged_in', None)
    return jsonify({'status': 'success', 'message': 'Logged out'})

# Interview flow
@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'resume' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'status': 'success', 'filename': filename})
    return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400

@app.route('/api/submit-interview', methods=['POST'])
def api_submit_interview():
    data = request.json
    candidate = data.get('candidate')
    answers = data.get('answers')
    resume_filename = data.get('resume_filename')

    if not candidate or not answers:
        return jsonify({'status': 'error', 'message': 'Missing candidate or answers'}), 400

    candidate['id'] = str(uuid.uuid4())
    config = load_config()
    score = analyze_answers(answers)
    passed = score >= config.get('hr_score', 7)

    candidate.update({
        'score': score,
        'status': 'passed' if passed else 'failed',
        'resume': resume_filename,
        'time_limit': config.get('hr_time_limit', 10),
        'time_taken': candidate.get('time_taken', 'N/A')
    })

    if passed:
        candidates = load_passed_candidates()
        if not any(c['email'] == candidate['email'] for c in candidates):
            candidates.append(candidate)
            save_passed_candidates(candidates)
        else:
            return jsonify({'status': 'duplicate', 'message': 'Candidate already exists'})

    return jsonify({'status': 'success', 'score': score, 'passed': passed})

# Admin config API
@app.route('/api/requirements', methods=['POST'])
@login1_required
def api_requirements():
    data = request.get_json()
    save_config(data)
    return jsonify({"status": "success"})

# HR candidate management
@app.route('/api/candidates', methods=['GET'])
@login_required
def api_get_candidates():
    return jsonify(load_passed_candidates())

@app.route('/api/candidates/<candidate_id>', methods=['DELETE'])
@login_required
def api_delete_candidate(candidate_id):
    candidates = load_passed_candidates()
    candidates = [c for c in candidates if c['id'] != candidate_id]
    save_passed_candidates(candidates)
    return jsonify({"status": "success"})

@app.route('/resumes/<filename>')
def serve_resume(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
