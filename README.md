# SmartAI – Personal AI Assistant

A modern, full-stack conversational AI assistant built with **Flask**, **Remote Cloud Ollama** (`qwen2.5:3b`), and **Neon PostgreSQL**. Designed for secure, zero-weight serverless deployment on **Vercel** with complete user authentication, session security, and conversation isolation.

---

## Architecture Overview

- **Frontend**: Responsive HTML5, CSS3 (Light/Dark themes), JavaScript, Markdown rendering, Code syntax highlighting.
- **Backend**: Python Flask REST API with HttpOnly secure sessions.
- **AI Engine**: Remote always-on **Cloud Ollama** server running `qwen2.5:3b`. Connects via Ollama's HTTP API (`/api/chat`) with secure Bearer authentication, request timeouts, real-time IST clock, and greeting handlers.
- **Database**:
  - **Production (Vercel)**: **Neon PostgreSQL** via `psycopg2` with serverless connection pooling (`ThreadedConnectionPool`) and auto-reconnect handling.
  - **Local Development**: Automatic fallback to local **SQLite** (`smartai.db`) when `DATABASE_URL` is omitted in non-production environments.

---

## Remote Ollama Cloud Server Setup

1. **Deploy Ollama on a Remote Cloud Instance** (e.g. AWS EC2, DigitalOcean, Hetzner, GCP):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull the Required Model (`qwen2.5:3b`)**:
   ```bash
   ollama pull qwen2.5:3b
   ```

3. **Secure the Endpoint Behind HTTPS & API Key**:
   - Use a reverse proxy such as Nginx, Caddy, or Cloudflare Tunnel to expose Ollama securely over HTTPS.
   - Configure API Key authentication in the reverse proxy (e.g. checking `Authorization: Bearer <OLLAMA_API_KEY>`).
   - Never expose Ollama port 11434 directly to the public internet without authentication.

---

## Production Deployment on Vercel

### 1. Create a Neon PostgreSQL Database
1. Go to [Neon Console](https://console.neon.tech/) and create a free project (e.g., `smartai-db`).
2. In the Neon Dashboard under **Connection Details**:
   - Ensure **Pooled connection** is checked (ends with `-pooler...`).
   - Copy the connection string (`postgresql://<user>:<password>@...-pooler...neon.tech/neondb?sslmode=require`).

### 2. Configure Vercel Project Environment Variables
In your Vercel Project Dashboard (**Settings > Environment Variables**), configure the following:

| Variable | Description | Example / Value |
| :--- | :--- | :--- |
| `DATABASE_URL` | Neon PostgreSQL pooled connection string | `postgresql://user:pass@ep-xyz-pooler.neon.tech/neondb?sslmode=require` |
| `OLLAMA_BASE_URL` | Remote Ollama Cloud Server URL (HTTPS) | `https://ollama.your-domain.com` |
| `OLLAMA_API_KEY` | Remote Ollama Secret Bearer Key | `your_secure_remote_ollama_api_key` |
| `OLLAMA_MODEL` | Ollama Model Name | `qwen2.5:3b` |
| `SECRET_KEY` | Flask session secret key | *Random 32-character string* |
| `FLASK_ENV` | Environment identifier | `production` |

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
   - Add your `OLLAMA_BASE_URL` and `OLLAMA_API_KEY` to connect to your remote cloud Ollama instance.

4. **Run Server**:
   ```powershell
   python app.py
   ```
   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Running Test Suites

- **Model Engine Verification**:
  ```powershell
  python test_model.py
  ```
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
