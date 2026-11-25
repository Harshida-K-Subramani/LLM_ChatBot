# 🤖 SmartAI – Personal AI Assistant

A full-stack, secure, production-ready AI chatbot platform built with **Python (Flask)**, **SQLite**, **Ollama / Hugging Face LLM models**, and a **ChatGPT-inspired modern interface** featuring a **complete user authentication and data privacy system**.

When users open SmartAI, they are greeted by a secure **Sign In / Create Account** page. Once authenticated, users access their personal chatbot workspace where their conversation histories are stored privately and isolated from other users.

---

## 🌟 Key Features

### 1. 🔐 Secure User Authentication & Data Privacy
- **Dedicated Auth UI (`/login` & `/signup`)**: Sleek, glassmorphic auth page supporting both **Dark and Light themes** with password visibility toggles, client-side validation, loading spinners, and clear error/success alerts.
- **Robust Password Hashing**: Passwords are securely hashed with salted algorithms via `werkzeug.security` (PBKDF2/SHA256). Plain-text passwords are never stored.
- **Duplicate Email Prevention**: Instant rejection of duplicate email registrations.
- **Session Security**: Uses Flask cryptographically signed sessions with `HttpOnly`, `SameSite=Lax`, and configurable lifetime cookies.
- **Strict Multi-User Privacy**: Every conversation belongs to an individual `user_id`. Users cannot list, access, modify, delete, or inject chat messages into another user's conversation sessions.
- **Protected APIs**: All chat and conversation endpoints return `401 Unauthorized` if accessed without an active session.

### 2. 🖥️ Modern ChatGPT-Style Interface
- **Left Collapsible Sidebar**: Lists previous conversations with titles, search filtering, deletion, and quick "+ New Chat" button (`Ctrl+K`).
- **User Profile Card**: Displays logged-in user name, email, avatar initial, and a one-click **Sign Out** button.
- **Dark & Light Themes**: Sleek styling with automatic `localStorage` preference persistence.
- **Markdown & Code Rendering**: Automatic syntax highlighting for code blocks with language badges and individual "Copy Code" buttons.
- **Interactive Actions**: Copy AI response to clipboard, regenerate responses, clear conversation messages.
- **Typing Animation**: Animated bouncing indicator showing real-time inference feedback.
- **Responsive Design**: Adapts seamlessly to desktop, tablets, and mobile devices.

### 3. 🧠 Smart AI Engine (Ollama / LLM)
- Context-aware responses with multi-turn memory.
- Real-time time & date questions answered accurately with Indian Standard Time (IST) clock logic.
- Natural greeting handling and deep conversational understanding.
- Markdown output for math, code, lists, and reasoning.

### 4. 🗄️ Robust SQLite Database
- Database file: `smartai.db`.
- **`users` table**: `id`, `name`, `email` (UNIQUE), `password` (hashed), `created_at`.
- **`conversations` table**: `id`, `title`, `created_at`, `updated_at`, `user_id` (FOREIGN KEY with cascading delete).
- **`messages` table**: `id`, `conversation_id`, `sender`, `content`, `created_at`.
- Write-Ahead Logging (WAL) and foreign keys enabled for concurrency and performance.

---

## 🏗️ Architecture Diagram

```
+-------------------------------------------------------------------------+
|                        Web Frontend (SPA)                               |
|  - Login & Sign Up Page (/login, /signup) with Password Toggle          |
|  - Modern Chat Interface with User Profile Card & Sign Out              |
|  - Responsive Drawer, Dark/Light Themes, Markdown & Code Highlighting   |
+------------------------------------+------------------------------------+
                                     |
                               REST API (JSON)
                                     |
+------------------------------------v------------------------------------+
|                         Flask Backend (app.py)                          |
|  - Session Security (HttpOnly, SameSite=Lax, Secret Key)                |
|  - Auth Routes: /api/auth/signup, /api/auth/login, /api/auth/logout     |
|  - Ownership Verification: @login_required on all conversation & chat   |
+------------------+----------------------------------+-------------------+
                   |                                  |
                   v                                  v
+------------------+---------------+ +----------------+------------------+
|    SQLite Database (database.py) | |     Model Engine (model_engine.py) |
|  - users (Hashed Passwords)      | |  - Ollama (qwen2.5:3b)             |
|  - conversations (user_id scoped)| |  - Real-time clock & greetings     |
|  - messages (Cascading deletes)  | |  - Multi-turn context memory       |
+----------------------------------+ +------------------------------------+
```

---

## 📁 Project Structure

```
SmartAI/
├── app.py                   # Main Flask application entrypoint, auth routes & API endpoints
├── config.py                # Configuration (Session security, secret key, DB path, model config)
├── database.py              # SQLite schema, user auth CRUD, conversation isolation queries
├── model_engine.py          # AI model integration & multi-turn memory
├── requirements.txt         # Python dependencies
├── .env.example             # Configuration template
├── .env                     # Local environment settings
├── README.md                # Documentation and setup guide
├── run.bat                  # One-click Windows launcher
├── run.ps1                  # One-click PowerShell launcher
├── test_auth.py             # User authentication and data privacy unit tests
├── test_app.py              # Backend & database integration tests
├── e2e_test.py              # End-to-end live server authentication workflow test
├── static/
│   ├── css/
│   │   └── style.css        # Modern ChatGPT-inspired dark/light theme CSS & auth styles
│   └── js/
│       ├── api.js           # REST API client with auth & 401 handling
│       ├── markdown.js      # Markdown renderer and copy code buttons
│       └── app.js           # Frontend controller, user profile & chat management
└── templates/
    ├── auth.html            # Sign In and Create Account page
    └── index.html           # Main authenticated Chat application template
```

---

## 🚀 Getting Started (Step-by-Step)

### Step 1: Open Terminal in Project Directory
Open PowerShell or VS Code terminal in the project folder:
```powershell
cd c:\Users\Harshida\new
```

### Step 2: Activate the Virtual Environment
Activate the pre-configured virtual environment:
```powershell
.\venv\Scripts\Activate.ps1
```

*(Or simply use `.\run.bat` or `.\run.ps1` to launch directly).*

### Step 3: Install Required Dependencies (If not already installed)
```powershell
pip install -r requirements.txt
```

### Step 4: Run the Application
Start the Flask application:
```powershell
python app.py
```

Output:
```text
 * Starting SmartAI server at http://127.0.0.1:5000
 * Running on http://127.0.0.1:5000
```

### Step 5: Open in Your Browser
Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

1. You will be automatically directed to the **Sign In / Create Account** page.
2. Click **Create Account** to register your name, email, and password.
3. Upon registration, you are securely logged in and taken directly to the **SmartAI Chatbot**.
4. In the sidebar footer, notice your **Name**, **Email**, and **Sign Out** button.

---

## 🧪 Running the Automated Test Suite

To verify user registration, login security, password hashing, session cookies, and multi-user data privacy:

### Run Authentication & Privacy Tests:
```powershell
.\venv\Scripts\python.exe test_auth.py
```
Expected output:
```text
✓ Test 1: User Registration & Validations passed.
✓ Test 2: Login, Password Verification & Logout passed.
✓ Test 3: Unauthenticated API and Page Route Protection passed.
✓ Test 4: Strict User Data Privacy & Isolation passed.
Ran 4 tests in 2.078s - OK
```

### Run Live End-to-End Workflow Test:
```powershell
.\venv\Scripts\python.exe e2e_test.py
```
Expected output:
```text
[1/7] Server Health Check: HTTP 200
[2/7] Unauthenticated '/' Redirect: HTTP 302 -> Location: /login
[3/7] User 1 Signup: HTTP 201 - Account created successfully!
[4/7] Authenticated User Profile: Sarah Connor
[5/7] Created Conversation: ID ...
[6/7] Chat Response Received: 'The current time is ...'
[7/7] Logout Response: HTTP 200
      Post-Logout Access Attempt: HTTP 401 (Expected 401)
🎉 ALL LIVE END-TO-END VERIFICATION CHECKS PASSED PERFECTLY!
```

---

## 📡 REST API Reference

### 🔐 Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|:---:|
| `POST` | `/api/auth/signup` | Registers new user (`name`, `email`, `password`, `confirm_password`) | No |
| `POST` | `/api/auth/login` | Authenticates user (`email`, `password`, `remember`) and sets session | No |
| `POST` | `/api/auth/logout` | Destroys current session cookie | No |
| `GET` | `/api/auth/me` | Returns current user profile (`id`, `name`, `email`) | **Yes** |

### 💬 Conversation & Chat Endpoints (All Protected)

| Method | Endpoint | Description | Auth Required |
|---|---|---|:---:|
| `GET` | `/` | Serves chatbot (redirects to `/login` if unauthenticated) | **Yes** |
| `GET` | `/login` | Serves authentication page | No |
| `GET` | `/signup` | Serves sign up page | No |
| `GET` | `/api/conversations` | Lists conversations owned by logged-in user | **Yes** |
| `POST` | `/api/conversations` | Creates conversation owned by logged-in user | **Yes** |
| `GET` | `/api/conversations/<id>` | Retrieves user conversation details and message history | **Yes** |
| `DELETE` | `/api/conversations/<id>` | Deletes user conversation session | **Yes** |
| `POST` | `/api/conversations/<id>/clear` | Clears messages in user conversation | **Yes** |
| `PUT` | `/api/conversations/<id>/title` | Renames user conversation | **Yes** |
| `POST` | `/api/chat` | Posts message and receives AI response (user scoped) | **Yes** |
| `POST` | `/api/chat/regenerate` | Regenerates last assistant response (user scoped) | **Yes** |
| `GET` | `/api/health` | Backend and model operational status | No |

---

## 🛡️ Security Details

1. **Password Protection**: Passwords are hashed using Werkzeug's secure PBKDF2 with SHA-256 and unique salts. No raw passwords ever touch the database.
2. **Session Security**:
   - `SESSION_COOKIE_HTTPONLY = True`: Blocks JavaScript `document.cookie` access against XSS.
   - `SESSION_COOKIE_SAMESITE = 'Lax'`: Protects against Cross-Site Request Forgery (CSRF).
   - `PERMANENT_SESSION_LIFETIME = 7 Days`: Controlled expiration.
3. **Multi-Tenant Isolation**: SQLite queries filter strictly on `user_id = session["user_id"]`. Attempting to load, delete, or inject into another user's conversation ID returns `404 Not Found`.
