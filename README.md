# RM e-HotelManager

Application Revenue Management hotelier pour importer les donnees partenaires, tarifs et disponibilites, piloter les tarifs de reference, simuler les commissions/remises OTA et exposer deux interfaces separees.

## Services

- `backend` : API FastAPI + SQLModel.
- `apps/admin-web` : interface Admin protegee par `X-Admin-Api-Key`.
- `apps/user-web` : interface utilisateur publique de consultation/simulation.
- `hotel-db` : PostgreSQL.

## Developpement local

Backend et base :

```powershell
docker compose up --build
```

Admin :

```powershell
cd apps/admin-web
npm install
npm run dev
```

User :

```powershell
cd apps/user-web
npm install
npm run dev
```

URLs locales par defaut :

- Backend : `http://localhost:8000`
- Admin : `http://localhost:5173`
- User : `http://localhost:5174`

## Variables

Copier `.env.example` vers `.env` pour le developpement local.

Variables backend principales :

- `DATABASE_URL`
- `ADMIN_API_KEY`
- `ENV`
- `USER_WEB_ORIGIN`
- `ADMIN_WEB_ORIGIN`
- `DEFAULT_RATE_SOURCE_MODE`

Variable frontend de build :

- `VITE_API_URL`

## Production

Le depot contient :

- `backend/Dockerfile`
- `apps/admin-web/Dockerfile`
- `apps/user-web/Dockerfile`
- `docker-compose.prod.example.yml`
- `docs/coolify.md`

Les frontends sont servis en statique par Nginx sur le port interne `8080`. Le backend expose `/health`; les frontends exposent `/health`.

## Tests

```powershell
$env:PYTHONPATH="C:\Users\Farouk\Documents\New project\rm.e-hotelmanager\backend"
.venv\Scripts\python.exe -m pytest backend\tests
```

Build frontend :

```powershell
cd apps/admin-web
npm run build

cd ..\user-web
npm run build
```
