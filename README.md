# NutriSnap - Module 1 Features 1 & 2

NutriSnap is a Flask web application for meal logging and healthier food discovery.

- **Feature 1:** Meal Upload and Food Log Management
- **Feature 2:** Food & Vendor Directory with Search

The app uses Flask, Flask-SQLAlchemy, Jinja templates, Bootstrap 5, Cloudinary (for meal image hosting), and SQLite by default.

## Feature Overview

### Module 1 - Feature 1 (Completed)
- Upload meal image and log metadata (meal type, date, title, note)
- View, edit, and delete meal logs
- Cloudinary image upload/replacement/deletion

### Module 1 - Feature 2 (Implemented)
- Browse vendor directory in a responsive card grid
- Search vendors by name
- Filter vendors by category
- Combined search + category filtering through shareable GET query params
- View vendor details including contact/location info
- Browse vendor menu items with nutrition values
- Optional menu item detail page (`/menu-item/<id>`)
- Seed/demo data command for vendors and menu items

## Tech Stack

- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- Jinja2
- Bootstrap 5
- Cloudinary Python SDK
- SQLite (default)
- python-dotenv

## Project Structure

- `app.py` - App factory, extension setup, blueprint registration, 404 handler, seed CLI command
- `config.py` - Environment loading and app/database configuration
- `extensions.py` - SQLAlchemy extension
- `models.py` - `MealLog`, `Vendor`, `MenuItem` models and relationships
- `routes/meal_routes.py` - Feature 1 routes
- `routes/vendor_routes.py` - Feature 2 routes
- `services/cloudinary_service.py` - Cloudinary helper functions
- `seed.py` - Idempotent vendor/menu demo seeding logic
- `templates/` - Jinja templates
- `static/css/style.css` - Shared styling
- `static/js/confirm_delete.js` - Delete confirmation

## Setup

1. Create and activate virtual environment:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `.env` from `.env.example` and set values:

```env
SECRET_KEY=your_secret_key
DATABASE_URL=sqlite:///meal_logs.db
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

## Environment Variables

Required:
- `SECRET_KEY`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

Optional:
- `DATABASE_URL` (if omitted, app falls back to SQLite file in project root)

## Database Notes

- Default SQLite file is `meal_logs.db` in the project root.
- `db.create_all()` runs at app startup and creates required tables automatically.
- New tables for Feature 2:
  - `vendors`
  - `menu_items`

## Seed Demo Vendor/Menu Data

Run this command after dependencies are installed:

```bash
python -m flask --app app seed-vendors
```

What it does:
- Inserts/updates at least 5 vendors across categories
- Inserts/updates at least 3 menu items per vendor
- Safe to run multiple times (no duplicate vendor-item pairs)

## Run the App

```bash
python app.py
```

Open:
- [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Route Summary

### Core
- `GET /` - Home dashboard

### Feature 1 (Meal Logs)
- `GET /upload-meal`
- `POST /upload-meal`
- `GET /meal-logs`
- `GET /meal-log/<int:meal_id>`
- `GET /edit-meal/<int:meal_id>`
- `POST /edit-meal/<int:meal_id>`
- `POST /delete-meal/<int:meal_id>`

### Feature 2 (Vendors)
- `GET /vendors`
- `GET /vendor/<int:vendor_id>`
- `GET /menu-item/<int:item_id>`

## Vendor Search & Filter Behavior

- Uses GET query params:
  - `/vendors?search=fit`
  - `/vendors?category=Healthy`
  - `/vendors?search=green&category=Healthy`
- Search performs partial match on vendor name
- Category filter is exact match
- Only active vendors are returned
- Vendors are sorted alphabetically
- Selected filter values are preserved in form inputs

## Notes

- Meal image upload requires valid Cloudinary credentials.
- 404 page is shared and used for missing meals/vendors/menu items.
- The codebase keeps Feature 1 and Feature 2 integrated in the same Flask app structure.
