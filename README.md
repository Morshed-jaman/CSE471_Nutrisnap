# NutriSnap

NutriSnap is a multi-role Flask application for meal logging, nutrition analytics, vendor discovery, food ordering, and paid nutrition subscriptions.

## Implemented Modules

- Module 1 Feature 1: Meal Upload and Food Log Management
- Module 1 Feature 2: Food and Vendor Directory with Search
- Module 1 Feature 3: Favorites / Saved Items  
- Module 2 Feature 1: Nutrition Data Retrieval and Nutrition Analytics
- Module 2 Feature 2: Weekly Nutrition Tracking
- Module 2 Feature 3: Healthy Food Indicator   
- Module 3 Feature 1: Vendor Menu Listing Management
- Module 3 Feature 2: Review & Rating System  
- Module 3 Feature 3: Water Intake Tracker  
- Module 3 Feature 4: Subscribecribe / Unsubscribe to Vendors with Email Notification  
- Module 3 Feature 5: AI Based Nutrition Explanation (OpenAI API)
- Module 3 Feature 6: Nutritionist Advisor (Subscriber Feature)  
- Commerce: persistent cart, single-vendor checkout, order history, fulfilment status, and BDT delivery fees
- Payments: SSLCOMMERZ Sandbox checkout, IPN, server-side validation, risk checks, and idempotent fulfilment
- Premium: monthly, quarterly, and annual paid nutrition subscriptions
- Common Workflows: Registration & Login of Vendors, Advisor, Users a Multi-Role Access, Vendor Approval, Admin Moderation

## Tech Stack

- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-Migrate / Alembic
- Flask-WTF CSRF protection
- SQLite 
- Jinja2 templates
- Bootstrap 5
- Chart.js
- Cloudinary
- Spoonacular API
- OpenAI API (or OpenRouter using OpenAI-compatible endpoint)
- SSLCOMMERZ payment gateway

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
      commerce.py
      vendor.py
      vendor_profile.py
    routes/
      auth_routes.py
      admin_routes.py
      meal_routes.py
      nutrition_routes.py
      vendor_routes.py
      commerce_routes.py
    services/
      analytics_service.py
      auth_service.py
      cloudinary_service.py
      nutrition_service.py
      sslcommerz_service.py
    templates/
      auth/
      admin/
      vendor/
      meals/
      vendors/
      nutrition/
      errors/
      commerce/
    static/
      css/style.css
      js/
  main.py
  migrations/
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
- Keep a persistent, account-owned cart
- Place paid food orders and view order history
- Purchase a verified NutriSnap Plus subscription

### Food Vendor

- Register with business details
- Status starts as `pending`
- Pending vendor sees approval status page
- Approved vendor can access `/vendor/dashboard`
- Manage only own menu items (create/edit/delete/toggle availability)
- Manage vendor profile from `/vendor/profile`
- View paid customer orders and move them through controlled fulfilment states

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
- Audit recent payment transactions, orders, and verified revenue from `/admin/commerce`

## Environment Variables

Create `.env` from `.env.example`:

Never commit real API keys or gateway credentials. If a credential has ever appeared in Git history, revoke and replace it; removing it from the latest file does not remove the historical exposure.

```env
SECRET_KEY=
DATABASE_URL=postgresql://user:password@host:5432/nutrisnap
AUTO_CREATE_DB=false
PUBLIC_BASE_URL=https://your-production-domain.example
SESSION_COOKIE_SECURE=true

# SSLCOMMERZ Sandbox
SSLCOMMERZ_STORE_ID=
SSLCOMMERZ_STORE_PASSWORD=
SSLCOMMERZ_SANDBOX=true
PAYMENT_HTTP_TIMEOUT_SECONDS=15
ORDER_DELIVERY_FEE_BDT=60
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
NUTRITION_API_KEY=

# Direct OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1/chat/completions

# OpenRouter (optional)
OPENROUTER_API_KEY=
OPENROUTER_SITE_URL=
OPENROUTER_SITE_NAME=
DEFAULT_ADMIN_EMAIL=admin@nutrisnap.local
DEFAULT_ADMIN_PASSWORD=replace-with-a-strong-password
DEFAULT_ADMIN_NAME=NutriSnap Admin
DEFAULT_ADMIN_PHONE=01000000000
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=yourgmail@gmail.com
MAIL_PASSWORD=your-google-app-password
MAIL_USE_TLS=true
MAIL_DEFAULT_SENDER=yourgmail@gmail.com
```

If you use OpenRouter, change `OPENAI_BASE_URL` to:

```env
OPENAI_BASE_URL=https://openrouter.ai/api/v1/chat/completions
OPENAI_MODEL=openai/gpt-4o-mini
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
python main.py
```

Open:

- `http://127.0.0.1:5000`

## Default Admin Account

A default admin is auto-created at startup (if not already present) using:

- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_PASSWORD`

Always provide unique production credentials. Do not deploy the development defaults.

## Database migrations

The repository includes an Alembic migration baseline. For a new database:

```bash
flask --app main:app db upgrade
```

For an older database created with `db.create_all()`, back it up first, reconcile its schema, and stamp the matching migration before switching `AUTO_CREATE_DB=false`. Use managed PostgreSQL for production; serverless local SQLite is not durable.

## Payment setup and trust model

1. Create an SSLCOMMERZ Sandbox store and set its store ID/password.
2. Set `PUBLIC_BASE_URL` to the exact HTTPS deployment origin.
3. Configure the IPN URL as `https://your-domain/payments/ipn` in the merchant panel.
4. Keep `SSLCOMMERZ_SANDBOX=true` until the complete callback flow passes.

NutriSnap never grants paid access from a redirect alone. It calls the SSLCOMMERZ validation API and matches the transaction ID, amount, currency, status, and risk level. Duplicate success/IPN calls are idempotent. Store credentials remain server-side.

SSLCOMMERZ Sandbox is for testing only. A live merchant account, business verification, production credentials, refund policy, privacy policy, terms, and operational reconciliation are still required before accepting real money.

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

### Commerce and payments

- `GET /cart`
- `POST /cart/items/<int:item_id>`
- `GET/POST /checkout`
- `GET /orders`
- `GET /orders/<int:order_id>`
- `GET /subscriptions`
- `POST /subscriptions/<int:plan_id>/checkout`
- `POST /payments/ipn`
- `GET/POST /payments/success`
- `GET/POST /payments/fail`
- `GET/POST /payments/cancel`
- `GET /vendor/orders`
- `POST /vendor/orders/<int:order_id>/status`
- `GET /admin/commerce`

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

Favorites are account-owned through `user_id`; different users can save the same vendor, menu item, or meal independently.

## Tests

```bash
pytest -q
```

The commerce suite covers pending-vs-paid subscription access, amount tampering, order price snapshots, cart persistence, verified fulfilment, and repeated callback idempotency. Gateway HTTP calls are mocked in tests.
