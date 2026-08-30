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
- Adaptive weekly meal planning with deterministic nutrition, preference, favorite, variety, and pantry-aware suggestions
- Private pantry inventory, expiry/low-stock signals, and active-plan grocery generation
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
- Build, generate, swap, activate, and track seven-day meal plans at `/meal-planner`
- Manage pantry stock and plan-aware grocery lists at `/pantry`

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
DATABASE_URL=
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

## Local SQLite development

Leave `DATABASE_URL` empty (or point it at a local SQLite file), set `AUTO_CREATE_DB=false`, and use Alembic:

```powershell
.\.venv\Scripts\python.exe -m flask --app main:app db upgrade
.\.venv\Scripts\python.exe -m flask --app main:app db-preflight
.\.venv\Scripts\python.exe main.py
```

Never use the repository's local SQLite database on Vercel.

## Existing Supabase production upgrade

The graph is `000000000001` (non-destructive legacy baseline) → `13c04f232d70` (favorites and commerce). Existing databases already stamped `13c04f232d70` remain at head because that revision ID did not change. An unstamped legacy database runs the baseline with `checkfirst=True`, preserving existing tables and rows, then creates only missing commerce tables and plans.

Before the real upgrade, create or verify a recoverable Supabase backup. Use a session-pooler URL on port `5432` only as a temporary process variable. Do not replace local `.env`, do not run a downgrade, and do not use the dashboard HTTPS URL.

```powershell
$env:DATABASE_URL = '<Supabase session pooler PostgreSQL URL on port 5432>'
.\.venv\Scripts\python.exe -m flask --app main:app db-preflight
.\.venv\Scripts\python.exe -m flask --app main:app db upgrade
.\.venv\Scripts\python.exe -m flask --app main:app db-preflight
Remove-Item Env:DATABASE_URL
```

The first preflight is expected to report missing tables or no revision on an unupgraded legacy database. Review both migration files before execution: permitted operations create missing tables/indexes/constraints, migrate legacy favorite ownership where determinable, seed missing plan codes, and update `alembic_version`. The upgrade path contains no destructive operation against application data. Record row counts for legacy tables before and after in Supabase. Stop if the dialect is not `postgresql` or the safe host fingerprint is not the expected project.

## Fresh Supabase setup

Against an empty disposable project, set the session-pooler URL temporarily and run `db upgrade`, then `db-preflight`. The baseline creates the complete core schema and the incremental revision adds commerce. Configure the runtime `DATABASE_URL` separately with the transaction pooler on port `6543`.

## Vercel environment variables

Configure `SECRET_KEY`, `DATABASE_URL`, `AUTO_CREATE_DB=false`, `PUBLIC_BASE_URL`, `SESSION_COOKIE_SECURE=true`, `SSLCOMMERZ_STORE_ID`, `SSLCOMMERZ_STORE_PASSWORD`, `SSLCOMMERZ_SANDBOX=true`, `PAYMENT_HTTP_TIMEOUT_SECONDS`, `ORDER_DELIVERY_FEE_BDT`, the Cloudinary variables, `NUTRITION_API_KEY`, OpenAI/OpenRouter variables, and mail variables. Vercel runtime `DATABASE_URL` must be Supabase's transaction pooler URL on port `6543`. Never enable startup schema creation in production.

## Administrator creation

Administrator bootstrap is deliberately independent of application startup and has no fallback credentials:

```powershell
.\.venv\Scripts\python.exe -m flask --app main:app create-admin
```

The command securely prompts for the password, enforces complexity, refuses to promote an existing non-admin account, and makes no change when the admin already exists.

## Credential rotation

Before redeployment, revoke and replace every previously exposed Flask secret, OpenRouter key, Gmail App Password, Cloudinary secret, nutrition API key, administrator password, and SSLCOMMERZ Store Password. Never recover values from old `.env` files or Git history. Confirm `.env`, database files, backups, virtual environments, and caches remain ignored.

## Payment setup and trust model

1. Create an SSLCOMMERZ Sandbox store and set its store ID/password.
2. Set `PUBLIC_BASE_URL` to the exact HTTPS deployment origin.
3. Configure the IPN URL as `https://your-domain/payments/ipn` in the merchant panel.
4. Keep `SSLCOMMERZ_SANDBOX=true` until the complete callback flow passes.

NutriSnap never grants paid access from a redirect alone. It calls the SSLCOMMERZ validation API and matches the transaction ID, amount, currency, status, and risk level. Duplicate success/IPN calls are idempotent. Store credentials remain server-side.

SSLCOMMERZ Sandbox is for testing only. A live merchant account, business verification, production credentials, refund policy, privacy policy, terms, and operational reconciliation are still required before accepting real money.

For this deployment, configure the merchant-panel IPN URL exactly as:

```text
https://cse-471-nutrisnap.vercel.app/payments/ipn
```

### Manual Sandbox smoke testing

1. Confirm `PUBLIC_BASE_URL=https://cse-471-nutrisnap.vercel.app`, Sandbox mode, and rotated store credentials.
2. Log in as a normal user and start one subscription payment; cancel it and verify no access is granted.
3. Complete a subscription payment and confirm it becomes active only after server validation.
4. Add one vendor's items, verify the price snapshot and delivery fee, then complete checkout.
5. Confirm the order becomes paid/confirmed and the cart clears only after session initiation succeeds.
6. Replay success and IPN callbacks and confirm there is only one fulfilment.
7. Exercise failed/cancelled payments and confirm friendly pages, rollback, and sanitized logs.
8. Verify user, vendor, and administrator commerce views with authorization boundaries.

### Rollback and recovery

Commerce and baseline downgrades intentionally refuse to run because deleting commerce or legacy tables would destroy history. If an upgrade fails, stop traffic-changing work, preserve logs, and restore the verified Supabase backup or perform a reviewed forward-only corrective migration. Never run a production downgrade, truncate tables, or recreate the database.

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

### Planning and pantry

- `GET /meal-planner`
- `POST /meal-planner/create`
- `POST /meal-planner/<plan_id>/generate`
- `POST /meal-planner/<plan_id>/activate`
- `POST /meal-planner/<plan_id>/entries`
- `POST /meal-planner/entries/<entry_id>/swap`
- `POST /meal-planner/entries/<entry_id>/consume`
- `GET /pantry`
- `POST /pantry/items`
- `POST /grocery/generate`
- `POST /grocery/items`
- `POST /grocery/items/<item_id>/transfer`

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
