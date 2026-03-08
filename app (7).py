from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt
import datetime
import os
import json
import urllib.request
import pdfplumber
from functools import wraps

# ─── APP CONFIG ───────────────────────────────────────────────
# Tumhara actual flat structure:
# C:\Users\91639\AI JUNIOR JUDGE BY AI\
#   ├── app.py       ← yahan hai
#   ├── index.html   ← yahan hai
#   ├── uploads\
#   └── aijj.db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"[DEBUG] BASE_DIR = {BASE_DIR}")
print(f"[DEBUG] index.html exists = {os.path.exists(os.path.join(BASE_DIR, 'index.html'))}")

app = Flask(__name__,
            static_folder=BASE_DIR,
            template_folder=BASE_DIR)
CORS(app)

app.config['SECRET_KEY'] = 'aijj-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'aijj.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# ─── DATABASE MODELS ──────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(30), default='judge')
    court         = db.Column(db.String(120))
    created_at    = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    cases         = db.relationship('Case', backref='uploader', lazy=True)

    def set_password(self, pw):   self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)
    def to_dict(self):
        return dict(id=self.id, name=self.name, email=self.email,
                    role=self.role, court=self.court,
                    created_at=self.created_at.isoformat())


class Case(db.Model):
    __tablename__ = 'cases'
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    original_filename = db.Column(db.String(256))
    stored_filename   = db.Column(db.String(256))
    case_title        = db.Column(db.String(300))
    case_type         = db.Column(db.String(80))
    parties           = db.Column(db.String(300))
    court_name        = db.Column(db.String(150))
    urgency           = db.Column(db.String(20))
    merit_score       = db.Column(db.Integer)
    summary           = db.Column(db.Text)
    brief_json        = db.Column(db.Text)
    status            = db.Column(db.String(30), default='pending')
    uploaded_at       = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    processed_at      = db.Column(db.DateTime)

    def to_dict(self, include_brief=False):
        d = dict(
            id=self.id, case_title=self.case_title, case_type=self.case_type,
            parties=self.parties, court_name=self.court_name, urgency=self.urgency,
            merit_score=self.merit_score, summary=self.summary, status=self.status,
            original_filename=self.original_filename,
            uploaded_at=self.uploaded_at.isoformat(),
            processed_at=self.processed_at.isoformat() if self.processed_at else None,
        )
        if include_brief and self.brief_json:
            d['brief'] = json.loads(self.brief_json)
        return d


# ─── JWT HELPER ───────────────────────────────────────────────

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except Exception:
            return jsonify({'error': 'Invalid token'}), 401
        return f(current_user, *args, **kwargs)
    return decorated


# ─── AUTH ROUTES ──────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not all(data.get(k) for k in ['name', 'email', 'password']):
        return jsonify({'error': 'Name, email and password are required'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 409
    user = User(name=data['name'], email=data['email'],
                role=data.get('role', 'judge'), court=data.get('court', ''))
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    token = jwt.encode({'user_id': user.id,
                        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)},
                       app.config['SECRET_KEY'], algorithm='HS256')
    return jsonify({'token': token, 'user': user.to_dict()}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    if not user or not user.check_password(data.get('password', '')):
        return jsonify({'error': 'Invalid email or password'}), 401
    token = jwt.encode({'user_id': user.id,
                        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)},
                       app.config['SECRET_KEY'], algorithm='HS256')
    return jsonify({'token': token, 'user': user.to_dict()})


@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_me(current_user):
    return jsonify({'user': current_user.to_dict()})


# ─── CASE ROUTES ──────────────────────────────────────────────

@app.route('/api/cases', methods=['GET'])
@token_required
def get_cases(current_user):
    cases = Case.query.filter_by(user_id=current_user.id)\
                      .order_by(Case.uploaded_at.desc()).all()
    return jsonify({'cases': [c.to_dict() for c in cases]})


@app.route('/api/cases/<int:case_id>', methods=['GET'])
@token_required
def get_case(current_user, case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    return jsonify({'case': case.to_dict(include_brief=True)})


@app.route('/api/cases/<int:case_id>', methods=['DELETE'])
@token_required
def delete_case(current_user, case_id):
    case = Case.query.filter_by(id=case_id, user_id=current_user.id).first()
    if not case:
        return jsonify({'error': 'Case not found'}), 404
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], case.stored_filename or '')
    if os.path.exists(fpath):
        os.remove(fpath)
    db.session.delete(case)
    db.session.commit()
    return jsonify({'message': 'Case deleted'})


@app.route('/api/cases/upload', methods=['POST'])
@token_required
def upload_case(current_user):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('pdf', 'txt'):
        return jsonify({'error': 'Only PDF and TXT files allowed'}), 400

    safe_name   = secure_filename(file.filename)
    timestamp   = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    stored_name = f"{current_user.id}_{timestamp}_{safe_name}"
    filepath    = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
    file.save(filepath)

    case = Case(user_id=current_user.id, original_filename=file.filename,
                stored_filename=stored_name, status='pending')
    db.session.add(case)
    db.session.commit()

    try:
        text = extract_text(filepath, ext)
        if not text or len(text) < 50:
            raise ValueError("Could not extract readable text from file")
    except Exception as e:
        case.status = 'error'
        db.session.commit()
        return jsonify({'error': str(e)}), 422

    try:
        brief = call_claude(text)
        case.case_title   = brief.get('case_title', 'Untitled Case')
        case.case_type    = brief.get('case_type', '')
        case.parties      = brief.get('parties', '')
        case.court_name   = brief.get('court', '')
        case.urgency      = brief.get('urgency', 'MEDIUM')
        case.merit_score  = int(brief.get('merit_score', 50))
        case.summary      = brief.get('summary', '')
        case.brief_json   = json.dumps(brief)
        case.status       = 'processed'
        case.processed_at = datetime.datetime.utcnow()
        db.session.commit()
        return jsonify({'case': case.to_dict(include_brief=True)}), 201
    except Exception as e:
        case.status = 'error'
        db.session.commit()
        return jsonify({'error': f'AI processing failed: {str(e)}'}), 500


# ─── STATS ROUTE ──────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
@token_required
def get_stats(current_user):
    cases     = Case.query.filter_by(user_id=current_user.id).all()
    processed = [c for c in cases if c.status == 'processed']
    avg_merit = round(sum(c.merit_score for c in processed if c.merit_score) / len(processed), 1) if processed else 0
    high_urgency = sum(1 for c in processed if c.urgency == 'HIGH')
    return jsonify({'total_cases': len(cases), 'processed': len(processed),
                    'avg_merit_score': avg_merit, 'high_urgency': high_urgency})


# ─── HELPERS ──────────────────────────────────────────────────

def extract_text(filepath, ext):
    if ext == 'pdf':
        text = ''
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:30]:
                t = page.extract_text()
                if t:
                    text += t + '\n'
        return text.strip()
    else:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()


def call_claude(text):
    api_key = os.environ.get('GROQ_API_KEY', '') or 'REPLACE_WITH_YOUR_KEY'

    prompt = f"""You are AI JuniorJudge, a legal AI assistant for Indian courts. Analyse this legal document and produce a structured case brief.

Return ONLY a valid JSON object with NO markdown, NO code blocks, NO backticks. Use this exact structure:
{{
  "case_title": "Short case title",
  "case_type": "Civil/Criminal/Constitutional/etc",
  "parties": "Petitioner vs Respondent",
  "court": "Court name if found",
  "key_facts": ["fact 1", "fact 2", "fact 3", "fact 4", "fact 5"],
  "legal_issues": ["issue 1", "issue 2", "issue 3"],
  "arguments_petitioner": ["arg 1", "arg 2", "arg 3"],
  "arguments_respondent": ["arg 1", "arg 2", "arg 3"],
  "relevant_sections": ["IPC section / Act name"],
  "precedents": ["relevant past case if any"],
  "summary": "2-3 sentence crisp summary",
  "merit_score": 65,
  "merit_reasoning": "One line explaining score",
  "urgency": "HIGH or MEDIUM or LOW",
  "recommended_action": "One line next step for judge"
}}

Merit score: 0-100. Above 50 favors petitioner, below 50 favors respondent.
Return ONLY the JSON. No explanation, no markdown, no extra text.

DOCUMENT:
{text[:6000]}"""

    body = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2048
    }
    payload = json.dumps(body).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers=headers
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise Exception(f"Groq Error {e.code}: {err_body}")
    raw = result["choices"][0]["message"]["content"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)



# ─── SERVE FRONTEND ───────────────────────────────────────────

@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    full_path = os.path.join(BASE_DIR, path)
    if os.path.exists(full_path):
        return send_from_directory(BASE_DIR, path)
    return send_from_directory(BASE_DIR, 'index.html')


# ─── INIT ─────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("\n" + "="*50)
        print("✅ Database ready")
        print(f"📁 Folder     : {BASE_DIR}")
        print(f"🔑 API Key   : {'SET ✅' if os.environ.get('GROQ_API_KEY') else 'NOT SET ❌'}")
        print("="*50)
        print("🚀 Open http://localhost:5000")
        print("="*50 + "\n")
    app.run(debug=True, port=5001, host='0.0.0.0')
