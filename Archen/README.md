# PATH: /Archen/README.md
# Archen — Django Project
Archen is a modular **Django** application tailored for a Persian (fa) locale and the **Asia/Tehran** timezone.  
The codebase follows **PEP 8**, the standard Django project layout, and modern frontend conventions (RTL-friendly).
> **Architecture note:** The **`jobs`** app is now a fully **standalone** application exposed on the dashboard.  
---
## 1) Tech Stack & Requirements
- Python 3.10+
- Django (see requirements.txt)
- Database: SQLite by default (switchable to Postgres/MySQL)
- Node.js (optional, if you manage frontend assets)
---
## 2) Configuration
```bash
# 1) Create & activate a virtual environment
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Configure environment variables (optional)
cp .env.example .env  # if available; otherwise create your own

# 4) Apply database migrations
python manage.py migrate

# 5) Create an admin user
python manage.py createsuperuser

# 6) Run the development server
python manage.py runserver
```
---
## 3) Quick Start

Key settings to double‑check in `settings.py`:

- `LANGUAGE_CODE = "fa"`
- `TIME_ZONE = "Asia/Tehran"`
- Database (`DATABASES`)
- Static/Media roots if you deploy behind a web server
- `ALLOWED_HOSTS` and security settings for production

If you use a `.env`, ensure the file is **not** committed and is loaded early (via `python-dotenv` or similar).
---
## 4) Project Structure & Apps

Discovered Django apps:

- `accounting`
- `inventory`
- `jobs`
- `maintenance`
- `orders`
- `production_line`
- `reports`
- `users`

---
## 5) Development Tasks

```bash
# Collect static files (if configured)
python manage.py collectstatic --noinput

# Run tests
python manage.py test

# Run linting/formatting (configure to your liking)
# e.g., ruff / flake8 / black
```

**Coding conventions**
- Keep comments **in English** and focused on _what/why_, not on historical change logs.
- Prefer small, well‑named functions and clear separation of concerns inside each app.
---
## 6) Internationalization & RTL

- Default language is Persian (`fa`), templates/components should be **RTL‑friendly**.
- Use Django’s i18n utilities where applicable (`ugettext_lazy`, template `{{% trans %}}`) if you plan for multi‑language.
---
## 7) Deployment Notes (Checklist)

- Set a strong `SECRET_KEY` and never commit it.
- Configure `DEBUG = False` and `ALLOWED_HOSTS`.
- Set proper `STATIC_ROOT`/`MEDIA_ROOT` and serve them via a web server/CDN.
- Use a robust database (e.g., PostgreSQL) and run migrations on deploy.
- Put reverse proxy / HTTPS termination in front (Nginx/Traefik/…).

### Production (Gunicorn + WhiteNoise)

```bash
# Install dependencies
pip install -r requirements.txt

# Migrate and collect static
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Run Gunicorn (WSGI)
bash scripts/serve_gunicorn.sh 0.0.0.0 8000 3
# Or with Cloudflare Quick Tunnel (no public IP/port needed)
bash scripts/serve_gunicorn_with_tunnel.sh 8000
```

Environment variables for production:
- `DEBUG=0`
- `SECRET_KEY=<strong-secret>`
- `ALLOWED_HOSTS="your.domain another.domain"`

### Offline (PWA)
- First online visit installs the Service Worker and precaches essential assets.
- Navigations are network‑first with offline fallback page `/offline/`.
- Local static files are cache‑first; chart assets use network‑first with cached fallback.
- A minimal CSS fallback exists at `static/css/fallback.css` if Tailwind CDN is unavailable.
---
## 8) License

If a `LICENSE` file is present at the repository root, follow its terms.

---

**Maintainers’ note:**  
This README intentionally omits historical change logs; keep future comments succinct and purpose‑driven.
