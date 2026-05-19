from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.routers import (
    public,
    admin_excel,
    admin_hotels,
    admin_rates,
    admin_resolver,
    admin_uploads,
    admin_rate_plans,
    admin_rules,
    simulation,
)


app = FastAPI(
    title="RM e-HotelManager API",
    version="0.5.0",
)

origins = [
    settings.user_web_origin,
    settings.admin_web_origin,
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set([origin for origin in origins if origin])),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(public.router)
app.include_router(admin_hotels.router)
app.include_router(admin_uploads.router)
app.include_router(admin_rate_plans.router)
app.include_router(admin_rules.router)
app.include_router(admin_excel.router)
app.include_router(admin_resolver.router)
app.include_router(admin_rates.router)
app.include_router(simulation.public_router)
app.include_router(simulation.admin_router)
