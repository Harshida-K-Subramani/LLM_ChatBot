# SmartAI – Personal AI Assistant

A modern, full-stack conversational AI assistant built with **Flask**, **Groq Cloud API**, and **Neon PostgreSQL**. Designed for seamless, zero-weight serverless deployment on **Vercel** with full user authentication, session security, and conversation isolation.

---

## Architecture Overview

- **Frontend**: Responsive HTML5, CSS3 (Light/Dark themes), JavaScript, Markdown rendering, Code syntax highlighting.
- **Backend**: Python Flask REST API with HttpOnly secure sessions.
- **AI Engine**: Groq Cloud API (`llama-3.3-70b-versatile`) with multi-turn context retention, real-time IST clock, and greeting handlers.
- **Database**:
  - **Production (Vercel)**: **Neon PostgreSQL** via `psycopg2` with serverless connection pooling (`ThreadedConnectionPool`) and auto-reconnect handling.
  - **Local Development**: Automatic fallback to local **SQLite** (`smartai.db`) when `DATABASE_URL` is omitted in non-production environments.

---

## Production Deployment on Vercel & Neon

### 1. Create a Neon PostgreSQL Database
1. Go to [Neon Console](https://console.neon.tech/) and create a free project (e.g., `smartai-db`).
2. In the Neon Dashboard under **Connection Details**:
   - Ensure **Pooled connection** is checked (ends with `-pooler...`).
   - Copy the connection string. It will look like:
     ```text
     postgresql://<user>:<password>@ep-cool-fog-123456-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
     ```

### 2. Configure Vercel Project Environment Variables
In your Vercel Project Dashboard (**Settings > Environment Variables**), configure the following:

| Variable | Description | Example / Value |
| :--- | :--- | :--- |
| `DATABASE_URL` | Neon PostgreSQL pooled connection string | `postgresql://user:pass@ep-xyz-pooler.neon.tech/neondb?sslmode=require` |
| `GROQ_API_KEY` | Groq Cloud API Key | `gsk_...` |
| `GROQ_MODEL` | Groq Model Name | `llama-3.3-70b-versatile` |
| `SECRET_KEY` | Flask session secret key | *Random 32-character string* |
| `FLASK_ENV` | Environment identifier | `production` |

> [!IMPORTANT]
> In production on Vercel, SQLite is strictly disabled to prevent file errors on serverless read-only filesystems. Setting `DATABASE_URL` connects your deployment to Neon PostgreSQL, where tables and indexes are automatically created on first run.

---

## Local Development

1. **Activate Virtual Environment**:
   ```powershell
   .\venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables** (Optional):
   Copy `.env.example` to `.env`:
   - If `DATABASE_URL` is left empty, SmartAI will automatically use local SQLite (`smartai.db`).
   - Add your `GROQ_API_KEY` for LLM responses.

4. **Run Server**:
   ```powershell
   python app.py
   ```
   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Running Test Suites

- **Production Compliance & Database CRUD**:
  ```powershell
  python -m unittest test_production_db.py -v
  ```
- **Authentication & User Privacy**:
  ```powershell
  python -m unittest test_auth.py -v
  ```
- **API & Health Endpoints**:
  ```powershell
  python -m unittest test_app.py -v
  ```
- **End-to-End Live Workflow**:
  ```powershell
  python e2e_test.py
  ```

