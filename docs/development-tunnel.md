# Local portal through a development tunnel

Forward Vite port 5173. Vite proxies `/api` and `/media` to Django on port 8000.
API requests and document previews must remain relative to the frontend origin;
remote browsers cannot use the developer computer's localhost URLs.

In the ignored `frontend/.env.local`:

```text
VITE_API_BASE_URL=/api/v1
PORTAL_PUBLIC_ORIGINS=https://YOUR-EXACT-TUNNEL-HOST
```

Start Django with the same exact public origin in its environment:

```sh
PORTAL_PUBLIC_ORIGINS=https://YOUR-EXACT-TUNNEL-HOST python backend/manage.py runserver \
  127.0.0.1:8000 --settings=config.settings_database
```

For sharing with another computer, run `npm run demo` from `frontend`. This builds
the frontend and serves the compiled assets on port 5173 with the same API/media
proxy. It avoids sending individual development modules and HMR over the tunnel.
Rebuild/restart after code changes. Use `npm run dev` for local development.
Both commands use port 5173 and stop with an error if it is already occupied;
do not run both simultaneously or forward an automatically chosen alternate port.

The explicit origin configures Vite's host
allowlist and Django's trusted CSRF/CORS origins. Wildcards are not enabled;
session authentication and CSRF checks remain active. Changing the public URL
requires updating the local configuration and restarting the services.

A tunnel is available only while the computer, Django, Vite, forwarding service
and (for new OCR jobs) live OCR worker are running. It is not permanent hosting.
The live OCR worker uses its separate, persistent approved budget; changing
tunnel URLs or restarting the web server does not reset that budget.
