# Deploiement Coolify

## Architecture cible

Creer quatre services :

- `hotel-db` : PostgreSQL persistant.
- `hotel-rm-backend` : FastAPI.
- `hotel-rm-admin-web` : build statique Admin.
- `hotel-rm-user-web` : build statique User.

## Variables backend

Configurer sur `hotel-rm-backend` :

```txt
DATABASE_URL=postgresql+psycopg://<user>:<password>@hotel-db:5432/hoteldb
ADMIN_API_KEY=<secret-long-et-aleatoire>
ENV=production
DEFAULT_RATE_SOURCE_MODE=hybrid
USER_WEB_ORIGIN=https://<domaine-user>
ADMIN_WEB_ORIGIN=https://<domaine-admin>
```

## Variables frontend

Configurer comme build argument sur `hotel-rm-admin-web` et `hotel-rm-user-web` :

```txt
VITE_API_URL=https://<domaine-api>
```

Si Coolify expose l'API derriere le meme domaine avec un proxy `/api`, utiliser :

```txt
VITE_API_URL=/api
```

## Build settings

Backend :

```txt
Base directory: backend
Dockerfile: backend/Dockerfile
Port: 8000
Healthcheck: /health
```

Admin web :

```txt
Base directory: apps/admin-web
Dockerfile: apps/admin-web/Dockerfile
Port: 8080
Healthcheck: /health
```

User web :

```txt
Base directory: apps/user-web
Dockerfile: apps/user-web/Dockerfile
Port: 8080
Healthcheck: /health
```

## CORS

Le backend autorise uniquement :

- `USER_WEB_ORIGIN`
- `ADMIN_WEB_ORIGIN`
- les origines locales de developpement.

En production, verifier que les domaines Admin et User sont exactement ceux configures dans Coolify, protocole inclus.

## Base de donnees

Le backend cree les tables au demarrage via SQLModel. Pour une production plus stricte, l'etape suivante recommandee est d'ajouter Alembic afin de versionner les migrations.

## Verification apres deploiement

1. Ouvrir `https://<domaine-api>/health`.
2. Ouvrir `https://<domaine-admin>/health`.
3. Ouvrir `https://<domaine-user>/health`.
4. Depuis Admin, tester la cle `ADMIN_API_KEY`.
5. Importer le JSON partenaires, le CSV de regles, puis l'Excel Planning.
6. Depuis User, lancer une simulation publique sans cle Admin.
