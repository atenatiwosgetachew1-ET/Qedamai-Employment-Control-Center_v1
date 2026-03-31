# Employment Portal Company Control Center

Separate project scaffold for your company-side administration surface.

## Database

This backend now relies on PostgreSQL only. SQLite is not supported.

Required backend environment variables:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT` default `5432`
- `CUSTOMER_PORTAL_SYNC_BASE_URL` fallback only when an organization does not have its own `portal_api_base_url`

Example `backend/.env`:

```env
POSTGRES_DB=employment_control_center
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
CUSTOMER_PORTAL_SYNC_BASE_URL=https://customer-portal.example.com
```

Frontend local API override:

Create `frontend/.env.local` with:

```env
VITE_API_BASE_URL=http://localhost:8001
```

This is especially useful when you are running the company control center and the organization portal side by side, so the frontend always talks to the correct backend.

For local cross-origin development, the backend also allows these frontend origins by default:

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `http://localhost:5174`
- `http://127.0.0.1:5174`

You can override them with `CORS_ALLOWED_ORIGINS` in `backend/.env`.

Email delivery for reset links:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=qedamaitechnologies@gmail.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=qedamaitechnologies@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
```

Important:

- for Gmail, use an app password, not your normal account password
- if these values are not configured, reset emails will use the console email backend in development

## Purpose

This project is intended to be deployed separately from the customer-facing Employment Portal.

It is the place where your company can:

- create and manage customer organizations
- assign plans and subscriptions
- place organizations into grace, suspended, or cancelled states
- manage notes, reputation tiers, and billing operations

## Suggested Next Steps

1. Connect this project to your production Employment Portal database or API strategy.
2. Add authenticated company staff accounts and permissions.
3. Build organization, plan, and subscription management screens.
4. Add reporting, billing workflows, and license event review.

## Secure Sync

This project now supports a safer integration model:

- the company control center is the source of truth
- it sends signed server-to-server sync requests to the customer Employment Portal
- the customer Employment Portal verifies the request using a dynamically fetched public key and asymmetric signature validation

The signing keys themselves are now managed in the company control center database and exposed as public-key records through the API. The private key remains on the company side and is used to sign sync requests automatically.

Operators can now inspect active sync keys and rotate them from the company control center API and frontend.

Failed sync deliveries are also recorded in a retryable outbox so temporary outages do not silently lose updates.

## Customer Portal Bootstrap Login

The company control center can now verify first-time organization superadmin credentials for a customer portal.

Organization URL guidance:

- `portal_base_url`: the organization portal frontend URL used for reset links, for example `http://localhost:5173`
- `portal_api_base_url`: the organization portal backend URL used for sync delivery, for example `http://localhost:8000`

When `portal_api_base_url` is set on an organization, sync requests are sent there. The global `CUSTOMER_PORTAL_SYNC_BASE_URL` env var is now just a fallback for organizations that do not yet have their own backend URL saved in the database.

Endpoint:

- `POST /api/customer-portals/bootstrap-login/`

Request JSON:

```json
{
  "username": "org-superadmin",
  "password": "plain-text-password"
}
```

Success response shape:

```json
{
  "success": true,
  "organization": {
    "id": 1,
    "external_reference": "",
    "name": "Acme Corp",
    "slug": "acme-corp",
    "portal_base_url": "https://portal.example.com",
    "superadmin_username": "org-superadmin",
    "billing_contact_name": "",
    "billing_contact_email": "",
    "reputation_tier": "standard",
    "status": "active",
    "read_only_mode": false,
    "notes": "",
    "subscription": {
      "id": 1,
      "status": "active",
      "starts_at": null,
      "renews_at": null,
      "grace_ends_at": null,
      "cancelled_at": null,
      "last_payment_status": "paid",
      "notes": "",
      "plan": {
        "id": 1,
        "code": "starter",
        "name": "Starter",
        "description": "",
        "monthly_price": "25.00",
        "currency": "USD",
        "max_superadmins": 1,
        "max_admins": 1,
        "max_staff": 4,
        "max_customers": 5,
        "feature_flags": {},
        "is_active": true
      }
    }
  }
}
```

Notes:

- the password is stored only as a Django password hash in the company control center database
- the raw password is still forwarded during organization sync when an operator sets or rotates it
- customer portals should treat `401` from this endpoint as invalid bootstrap credentials

## Token-Based Password Reset

The recommended recovery flow is now token-based instead of emailing or syncing a new plaintext password.

Company operator action:

- `POST /api/organizations/<id>/request-superadmin-password-reset/`

What it does:

- creates a one-time reset token for that organization superadmin
- sends an email to the configured `superadmin_email`
- returns a `reset_url` so operators can copy the link manually if email delivery is not configured yet

Customer portal endpoints to call back into this company project:

- `POST /api/customer-portals/password-reset-tokens/validate/`
- `POST /api/customer-portals/password-reset-tokens/consume/`

Validate request:

```json
{
  "token": "one-time-token"
}
```

Consume request:

```json
{
  "token": "one-time-token",
  "new_password": "new-password-chosen-by-the-user"
}
```

Recommended user experience:

- operator issues a reset link from the company control center
- superadmin opens the link on the organization portal
- organization portal validates the token with this company backend
- user chooses a new password on the organization portal
- organization portal calls the consume endpoint so the company-side password hash is updated and the token is invalidated

Authority model:

- the company control center is the password authority for the organization superadmin only
- child users remain local to each organization portal
- after a superadmin reset completes, the organization portal should verify future superadmin logins against this company project instead of expecting the company project to mirror that password into local child-user auth flows

## Superadmin Password Reset

Company operators can reset an organization superadmin password from the control center.

Endpoint:

- `POST /api/organizations/<id>/reset-superadmin-password/`

Request JSON:

```json
{
  "new_password": "new-plain-text-password"
}
```

Behavior:

- updates the stored bootstrap password hash for that organization
- records a license event for the reset action
- re-syncs the organization to the customer portal and includes the new raw password in that sync request

This direct reset endpoint is still available as an operator fallback, but the token-based reset flow above is the preferred modern path.

## Lightweight Scheduled Retries

Use the lightweight management command below with Windows Task Scheduler or cron:

`python manage.py retry_sync_jobs --limit 25`

Recommended approach:

- run `python manage.py migrate` before using scheduled retries in a new environment
- run every 5 minutes
- keep the limit small, such as `10` to `25`
- let the built-in backoff schedule control when failed jobs become due
