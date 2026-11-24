# Public deployment with Railway

This deployment keeps the existing stack: FastAPI, MySQL, the public kiosk, and the authenticated admin panel. It does not publish the local `.env` or copy local database records automatically.

## Before deployment

- Create a Railway account and review its current plan and usage charges. The current Hobby plan has a US$5 monthly minimum; resource use above the included allowance can add charges. A trial credit is limited and is not a permanent free production host.
- Create a private Railway project and add a MySQL service. Keep MySQL on Railway's private network; do not enable a public TCP proxy for this app.
- Deploy the FastAPI service from this `backend` directory. Railway will build the included `Dockerfile`.
- Configure `/health` as the service health-check path.
- Set `FORCE_HTTPS=true`; Railway terminates TLS and forwards `X-Forwarded-Proto`. The API rejects public requests that arrive without HTTPS. Leave this unset for local `http://127.0.0.1` development.
- Tune `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, and `DB_POOL_TIMEOUT` against the MySQL plan and measured concurrent load; defaults are 5, 10, and 10 seconds.
- Add a persistent volume mounted at `/app/uploads` before publishing institutional PDF attachments.

## Backend variables

Set these in the FastAPI service's Railway Variables. Use Railway's variable reference for the MySQL service's private `MYSQL_URL`; do not paste credentials into source files.

- `DATABASE_URL`: reference the MySQL service's `MYSQL_URL` variable.
- `ADMIN_TOKEN_SECRET`: a new random secret of at least 32 bytes, different from the local value.
- `REGISTRATION_AUTHORIZATION_KEY`: a new authorization secret, different from the local value.
- `GEMINI_API_KEY`: set only if Gemini chat/import/voice should be active in the public deployment.
- `GEMINI_TTS_VOICE`: `es-419-concierge-8` for the Mexican Spanish masculine guide voice.

Railway's MySQL URL commonly uses the `mysql://` scheme. The backend converts it to the installed PyMySQL SQLAlchemy driver automatically.

## Database and files

The Railway MySQL service starts separately from the local MySQL database. Back up the local database first, review which institutional data and administrator accounts should be public, and migrate only approved records. Do not import student personal data or sample password hashes. Apply reviewed numbered migrations manually; this deployment never runs `DROP` or schema migrations at startup.

Files under `backend/uploads/institutional` are intentionally excluded from the deployment image. After mounting the persistent volume, copy only approved public PDFs into its `institutional` subdirectory and verify their database metadata before publishing them.

## URLs and access

After the service gets a Railway domain, use `/kiosko/` for the public kiosk. `/panel/` will also be reachable on the Internet, so keep it protected with strong admin credentials and do not leave registration authorization open. The backend serves both interfaces from one origin; CORS does not need a wildcard.
