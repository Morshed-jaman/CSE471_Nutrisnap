# NutriSnap

NutriSnap is a Flask web application for meal logging, vendor discovery, and nutrition analytics.

## Implemented Modules

- Module 1 Feature 1: Meal Upload & Food Log Management
- Module 1 Feature 2: Food & Vendor Directory with Search
- Module 2 Feature 3: Favorites / Saved Items  
- Module 2 Feature 1: Nutrition Data Retrieval + Nutrition Analytics
- Module 2 Feature 2: Weekly Nutrition Tracking
- Module 2 Feature 3: Healthy Food Indicator  

## Tech Stack

- Flask
- Flask-SQLAlchemy
- SQLite
- Jinja2 templates
- Bootstrap 5
- Chart.js
- Cloudinary
- Spoonacular API

## Refactored Project Structure 

```text
nutrisnap/
├── app/
│   ├── __init__.py                # App factory, extension init, blueprint registration, CLI commands
│   ├── config.py                  # Environment and Flask config
│   ├── extensions.py              # SQLAlchemy init
│   ├── seed.py                    # Vendor/menu demo seed data
│   │
│   ├── models/                    # Database models (backend)
│   │   ├── __init__.py
│   │   ├── meal_log.py
│   │   ├── vendor.py
│   │   └── menu_item.py
│   │
│   ├── routes/                    # Blueprints / HTTP flow (backend)
│   │   ├── __init__.py
│   │   ├── meal_routes.py
│   │   ├── vendor_routes.py
│   │   └── nutrition_routes.py
│   │
│   ├── services/                  # Business logic / integrations (backend)
│   │   ├── __init__.py
│   │   ├── cloudinary_service.py
│   │   ├── nutrition_service.py
│   │   └── analytics_service.py
│   │
│   ├── templates/                 # Frontend (Jinja)
│   │   ├── base.html
│   │   ├── landing.html
│   │   ├── home.html
│   │   ├── meals/
│   │   ├── vendors/
│   │   ├── nutrition/
│   │   └── errors/
│   │
│   └── static/                    # Frontend assets
│       ├── css/
│       ├── js/
│       └── images/
│
├── instance/
├── run.py                         # Clean app entry point
├── requirements.txt
├── .env.example
└── README.md
```

## Frontend vs Backend Separation

### Backend
- `app/__init__.py`: creates Flask app and registers everything
- `app/config.py`: all environment/config settings
- `app/extensions.py`: database object
- `app/models/`: DB schema
- `app/routes/`: endpoints + page flow
- `app/services/`: API calls, cloud upload, analytics helpers

### Frontend
- `app/templates/`: UI pages grouped by feature
- `app/static/css/`: global styles
- `app/static/js/`: page interactions and chart rendering

## Environment Variables

Create `.env` from `.env.example`:

```env
SECRET_KEY=your_secret_key
DATABASE_URL=sqlite:///meal_logs.db
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_cloudinary_api_key
CLOUDINARY_API_SECRET=your_cloudinary_api_secret
NUTRITION_API_KEY=your_spoonacular_api_key
```

## Setup

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the App

```bash
python run.py
```

Open:
- `http://127.0.0.1:5000`

## Seed Demo Vendor/Menu Data

```bash
flask --app run seed-vendors
```

Safe to run multiple times.

## Core Routes

- `GET /` (landing)
- `GET /home`
- `GET/POST /upload-meal`
- `GET /meal-logs`
- `GET /meal-log/<int:meal_id>`
- `GET/POST /edit-meal/<int:meal_id>`
- `POST /delete-meal/<int:meal_id>`
- `GET /vendors`
- `GET /vendor/<int:vendor_id>`
- `GET /menu-item/<int:item_id>`
- `GET/POST /nutrition-search`
- `POST /analyze-meal/<int:id>`
- `GET /nutrition-analytics`
- `GET /weekly-tracking`
- `GET /api/nutrition-analytics-data`
- `GET /api/weekly-tracking-data`

## 30-Second Viva Explanation

"I used Flask app factory architecture. `app/__init__.py` initializes config, database, and blueprints. Models are separated in `app/models`, routes are modularized in `app/routes`, and external/business logic is in `app/services`. Frontend is clearly separated into `app/templates` and `app/static`. This makes backend and frontend easy to navigate, scale, and explain." 
