# NutriSnap - Module 1 + Module 2

NutriSnap is a Flask application for meal logging, vendor discovery, and nutrition analytics.

## Implemented Features

### Module 1 - Feature 1: Meal Upload and Food Log Management
- Upload meal images to Cloudinary
- Save meal type/date/title/note
- View, edit, and delete meal logs

### Module 1 - Feature 2: Food & Vendor Directory with Search
- Browse vendors and menu items
- Search vendors by name and filter by category
- View vendor details and menu item details
- Seed command for demo vendors/menu data

### Module 2 - Feature 1: Nutrition Data Retrieval + Nutrition Analytics
- Manual nutrition search by food name (external API)
- Analyze nutrition for existing meal logs and save to database
- Nutrition analytics totals: calories/protein/carbs/fats + average calories
- Charts with Chart.js:
  - Calories per meal (bar)
  - Macro distribution (pie)
  - Meals over time (line)
- Insight badges: High Protein, Low Calorie, Balanced Meal

## Tech Stack

- Flask
- Flask-SQLAlchemy
- SQLite (default)
- Jinja2
- Bootstrap 5
- Chart.js
- Cloudinary
- Spoonacular Nutrition API

## Project Structure

- `app.py` - app factory, blueprint registration, schema safety update, CLI command
- `config.py` - environment/config loading
- `extensions.py` - SQLAlchemy initialization
- `models.py` - `MealLog`, `Vendor`, `MenuItem`
- `routes/meal_routes.py` - meal log routes
- `routes/vendor_routes.py` - vendor/menu routes
- `routes/nutrition_routes.py` - nutrition search, analyze meal, nutrition analytics, nutrition analytics API
- `services/cloudinary_service.py` - Cloudinary upload/delete
- `services/nutrition_service.py` - Spoonacular integration + insight logic
- `seed.py` - vendor/menu demo seeding
- `templates/` - Jinja templates
- `static/css/style.css` - UI styling
- `static/js/nutrition_analytics.js` - Chart.js rendering logic

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
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run Application

```bash
python app.py
```

Open in browser:
- `http://127.0.0.1:5000`

## Seed Demo Vendor Data

```bash
python -m flask --app app seed-vendors
```

Safe to run multiple times.

## Module 2 Feature Routes

- `GET /nutrition-search`
- `POST /nutrition-search`
- `POST /analyze-meal/<int:id>`
- `GET /nutrition-analytics`
- `GET /api/nutrition-analytics-data`

## Existing Core Routes

- `GET /` (landing page)
- `GET /home` (app home/control center)
- `GET /upload-meal`, `POST /upload-meal`
- `GET /meal-logs`
- `GET /meal-log/<int:meal_id>`
- `GET /edit-meal/<int:meal_id>`, `POST /edit-meal/<int:meal_id>`
- `POST /delete-meal/<int:meal_id>`
- `GET /vendors`
- `GET /vendor/<int:vendor_id>`
- `GET /menu-item/<int:item_id>`

## Notes About Database Safety

- `MealLog` now includes nullable nutrition fields:
  - `calories`, `protein`, `carbohydrates`, `fats`
- App startup includes safe schema update logic for existing SQLite DBs so old records continue working.

## Quick Test Checklist

1. Upload a new meal.
2. Open meal logs and click **Analyze Nutrition**.
3. Verify nutrition values appear on meal detail.
4. Open **Nutrition Search**, search a food (for example `chicken rice`).
5. Open **Nutrition Analytics** and verify totals/charts/recent meals update.
6. Call `GET /api/nutrition-analytics-data` and confirm JSON chart payload.
