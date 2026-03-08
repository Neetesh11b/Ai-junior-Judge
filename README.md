# ⚖️ AI JuniorJudge — Full Stack Legal Case Brief System

A complete LegalTech web application for Indian courts.
Judges upload case PDFs → AI generates a one-page structured brief.

---

## 🗂️ PROJECT STRUCTURE

```
ai-junior-judge/
├── backend/
│   ├── app.py              ← Flask app (API + DB logic)
│   ├── requirements.txt    ← Python dependencies
│   └── uploads/            ← Uploaded files stored here (auto-created)
│   └── aijj.db             ← SQLite database (auto-created on first run)
│
└── frontend/
        └── index.html      ← Full single-page frontend app
```

---

## 🗄️ DATABASE SCHEMA

### `users` table
| Column        | Type    | Description                  |
|---------------|---------|------------------------------|
| id            | Integer | Primary key                  |
| name          | String  | Full name of judge/clerk     |
| email         | String  | Unique login email           |
| password_hash | String  | Bcrypt hashed password       |
| role          | String  | judge / clerk / admin        |
| court         | String  | Court name                   |
| created_at    | DateTime| Registration timestamp       |

### `cases` table
| Column           | Type    | Description                       |
|------------------|---------|-----------------------------------|
| id               | Integer | Primary key                       |
| user_id          | Integer | FK → users.id                     |
| original_filename| String  | Original PDF name                 |
| stored_filename  | String  | Hashed filename on disk           |
| case_title       | String  | AI-extracted case title           |
| case_type        | String  | Civil / Criminal / Constitutional |
| parties          | String  | Petitioner vs Respondent          |
| court_name       | String  | Court name from document          |
| urgency          | String  | HIGH / MEDIUM / LOW               |
| merit_score      | Integer | 0-100 AI merit score              |
| summary          | Text    | 2-3 sentence crisp summary        |
| brief_json       | Text    | Full AI brief stored as JSON      |
| status           | String  | pending / processed / error       |
| uploaded_at      | DateTime| Upload timestamp                  |
| processed_at     | DateTime| Processing completion time        |

---

## 🚀 SETUP & RUN

### Step 1 — Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2 — Set your Groq API key
```bash
# Windows
set Groq_API_KEY=sk-ant-your-key-here

# Mac / Linux
export Groq_API_KEY=sk-ant-your-key-here
```

### Step 3 — Run Flask backend
```bash
python app.py
```
Backend starts at: http://localhost:5000

### Step 4 — Open the frontend
Open `frontend/templates/index.html` in your browser.
OR visit http://localhost:5000 (Flask serves it automatically).

---

## 🔌 API ENDPOINTS

| Method | Endpoint              | Description              | Auth     |
|--------|-----------------------|--------------------------|----------|
| POST   | /api/auth/register    | Register new user        | No       |
| POST   | /api/auth/login       | Login, get JWT token     | No       |
| GET    | /api/auth/me          | Get current user info    | JWT      |
| GET    | /api/cases            | List all my cases        | JWT      |
| GET    | /api/cases/:id        | Get single case + brief  | JWT      |
| POST   | /api/cases/upload     | Upload PDF + generate brief | JWT   |
| DELETE | /api/cases/:id        | Delete a case            | JWT      |
| GET    | /api/stats            | Dashboard stats          | JWT      |

---

## 🛠️ TECHNOLOGY STACK

| Layer      | Technology        | Purpose                              |
|------------|-------------------|--------------------------------------|
| Frontend   | HTML/CSS/JS       | Single-page app, no framework needed |
| Backend    | Flask (Python)    | REST API, file handling              |
| Database   | SQLite            | Local relational storage             |
| ORM        | SQLAlchemy        | Python ↔ Database bridge             |
| Auth       | JWT (PyJWT)       | Secure stateless authentication      |
| PDF Extract| pdfplumber        | Text extraction from PDFs            |
| AI Engine  | Groq API          | NLP summarisation + merit scoring    |
| Passwords  | Werkzeug (bcrypt) | Secure password hashing              |

---

## 🔒 SECURITY FEATURES
- Passwords hashed with bcrypt (never stored as plain text)
- JWT tokens expire after 7 days
- Each user can only see their own cases
- Uploaded files stored with randomised names
- File type + size validation

---
📈 VERSION ROADMAP
✅ v1.0 — MVP (Current)

-JWT Authentication (Register / Login)
-PDF & TXT file upload + text extraction
-Groq AI (LLaMA 3.3 70B) case brief generation
-Merit Score (0–100) with reasoning
-Urgency classification (HIGH / MEDIUM / LOW)
-Key facts, legal issues, arguments extraction
-Relevant sections & precedents
-Case history dashboard
-SQLite local database


🔜 v2.0 — Enhanced AI (Planned)

-Multi-language support (Hindi, Marathi, Tamil etc.)
-Better precedent matching using vector search (FAISS / Pinecone)
-Case similarity comparison
-Batch upload (multiple PDFs at once)
-Export brief as PDF / Word document

🔜 v3.0 — Production Ready (Planned UPGRADING TO PRODUCTION)

Replace SQLite with PostgreSQL:
python   app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost/aijj'

-Will Use Gunicorn instead of Flask dev server
-Store files in AWS S3 instead of local disk
-Add HTTPS with nginx reverse proxy
-Change SECRET_KEY to a strong random string
-Role-based access control (Judge vs Clerk vs Admin)
-Audit logs for every case action

---
