# NutriSnap

NutriSnap is a Flask web application for meal logging, vendor discovery, nutrition retrieval, and analytics workflows.

## Implemented Modules

- Module 1 Feature 1: Meal Upload and Food Log Management
- Module 1 Feature 2: Food and Vendor Directory with Search
- Module 2 Feature 1: Nutrition Data Retrieval and Nutrition Analytics
- Module 2 Feature 2: Weekly Nutrition Tracking
- Module 2 Feature 3: AI-Based Nutrition Explanation (OpenAI API)
- Module 3 Feature 1: Vendor Menu Listing Management
- Common Workflows: Registration, Login, Multi-Role Access, Vendor Approval, Admin Moderation

## Tech Stack

- Flask
- Flask-SQLAlchemy
- Flask-Login
- SQLite (default)
- Jinja2 templates
- Bootstrap 5
- Chart.js
- Cloudinary
- Spoonacular API
- OpenAI API (or OpenRouter using OpenAI-compatible endpoint)

## Project Structure

```text
nutrisnap/
  app/
    __init__.py
    config.py
    extensions.py
    seed.py
    models/
      meal_log.py
      menu_item.py
      user.py
      vendor.py
      vendor_profile.py
    routes/
      auth_routes.py
      admin_routes.py
      meal_routes.py
      nutrition_routes.py
      vendor_routes.py
    services/
      analytics_service.py
      auth_service.py
      cloudinary_service.py
      nutrition_service.py
    templates/
      auth/
      admin/
      vendor/
      meals/
      vendors/
      nutrition/
      errors/
    static/
      css/style.css
      js/
  run.py
  requirements.txt
  .env.example
```

## Roles and Access

### User

- Register and login
- Access user home dashboard (`/home`)
- Upload meals to personal logs
- View/edit/delete only own meals in `My Meal Logs`
- Browse central/shared meal feed
- Save/copy meals from central feed into personal logs
- Use nutrition search
- Use personal nutrition analytics (own meals only)
- Use personal weekly tracking (own meals only)
- Manage personal profile from `/user/profile`

### Food Vendor

- Register with business details
- Status starts as `pending`
- Pending vendor sees approval status page
- Approved vendor can access `/vendor/dashboard`
- Manage only own menu items (create/edit/delete/toggle availability)
- Manage vendor profile from `/vendor/profile`

### Admin

- Login from `/admin/login`
- Access admin dashboard `/admin`
- Review pending vendors
- Approve/reject vendor accounts
- Monitor all meal logs in admin meal pages
- Delete any meal log as moderation action
- Monitor all vendor menu items in admin pages
- Delete any vendor menu item as moderation action
- Manage admin profile from `/admin/profile`

## Environment Variables

Create `.env` from `.env.example`:

```env
SECRET_KEY=change-me
DATABASE_URL=sqlite:///meal_logs.db
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
NUTRITION_API_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1/chat/completions
OPENROUTER_API_KEY=
OPENROUTER_SITE_URL=
OPENROUTER_SITE_NAME=
DEFAULT_ADMIN_EMAIL=admin@nutrisnap.local
DEFAULT_ADMIN_PASSWORD=admin12345
DEFAULT_ADMIN_NAME=NutriSnap Admin
DEFAULT_ADMIN_PHONE=01000000000
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=yourgmail@gmail.com
MAIL_PASSWORD=your-google-app-password
MAIL_USE_TLS=true
MAIL_DEFAULT_SENDER=yourgmail@gmail.com
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

## Default Admin Account

A default admin is auto-created at startup (if not already present) using:

- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_PASSWORD`

Default values from `.env.example`:

- Email: `admin@nutrisnap.local`
- Password: `admin12345`

Change these in `.env` for real use.

## Route Summary

### Authentication

- `GET/POST /login`
- `GET/POST /register`
- `GET/POST /vendor/register`
- `GET/POST /logout`
- `GET /vendor/pending`

### User Meal Flow

- `GET /home`
- `GET/POST /upload-meal`
- `GET /my-meal-logs`
- `GET /meal-logs` (central feed)
- `GET /meal-log/<int:meal_id>`
- `POST /meal-log/<int:meal_id>/save-to-my-meals`
- `GET/POST /edit-meal/<int:meal_id>`
- `POST /delete-meal/<int:meal_id>`

### Nutrition

- `GET/POST /nutrition-search` (Nutrition API retrieval)
- `GET/POST /nutrition-explanation` (AI explanation from provided nutrition values)
- `POST /analyze-meal/<int:id>`
- `GET /nutrition-analytics`
- `GET /weekly-tracking`
- `GET /api/nutrition-analytics-data`
- `GET /api/weekly-tracking-data`

### Vendors

- `GET /vendors`
- `GET /vendor/<int:vendor_id>`
- `GET /menu-item/<int:item_id>`
- `GET /vendor/dashboard` (approved vendors)
- `GET /vendor/menu-items`
- `GET/POST /vendor/menu-item/new`
- `GET/POST /vendor/menu-item/create`
- `GET/POST /vendor/menu-item/<int:item_id>/edit`
- `POST /vendor/menu-item/<int:item_id>/delete`
- `POST /vendor/menu-item/<int:item_id>/toggle-availability`

### Admin

- `GET/POST /admin/login`
- `GET /admin`
- `GET /admin/vendors/pending`
- `GET /admin/vendor/<int:user_id>`
- `POST /admin/vendor/<int:user_id>/approve`
- `POST /admin/vendor/<int:user_id>/reject`
- `GET /admin/meal-logs`
- `GET /admin/meal-log/<int:meal_id>`
- `POST /admin/meal-log/<int:meal_id>/delete`
- `GET /admin/menu-items`
- `GET /admin/menu-item/<int:item_id>`
- `POST /admin/menu-item/<int:item_id>/delete`

### Profile

- `GET/POST /profile` (role-aware redirect)
- `GET/POST /user/profile`
- `GET/POST /vendor/profile`
- `GET/POST /admin/profile`

## Notes on Existing Data

`MealLog.user_id` is now used for ownership. Older legacy rows with `NULL user_id` remain visible in central feed and admin views, but are not treated as personal user data.
