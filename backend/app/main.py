from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.routers import public, admin_hotels


app = FastAPI(
    title='RM e-HotelManager API',
    version='0.1.0',
)

origins = [
    settings.user_web_origin,
    settings.admin_web_origin,
    'http://localhost:5173',
    'http://localhost:5174',
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(set([origin for origin in origins if origin])),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def on_startup():
    init_db()


app.include_router(public.router)
app.include_router(admin_hotels.router)
