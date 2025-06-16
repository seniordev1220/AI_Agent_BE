from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .routes import auth, users, api_keys, agents, chat, model_settings, data_source, dashboard, payments, settings, activity
from .database import engine
from .models import user, settings as settings_model, user_activity
import os

load_dotenv()

# Create database tables
user.Base.metadata.create_all(bind=engine)
settings_model.Base.metadata.create_all(bind=engine)
user_activity.Base.metadata.create_all(bind=engine)

# Create static directory if it doesn't exist
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://3.112.199.154:3000",
    "https://3.112.199.154:3000",
    "http://app.finiite.com",
    "https://app.finiite.com",
    "*",  # Allow all origins for the widget (you may want to restrict this in production)
]

app = FastAPI(title="Finiite API")

# Mount static files directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(api_keys.router)
app.include_router(agents.router)
app.include_router(chat.router)
app.include_router(model_settings.router)
app.include_router(data_source.router)
app.include_router(dashboard.router)
app.include_router(payments.router)
app.include_router(settings.router)
app.include_router(activity.router)

@app.get("/")
def root():
    return {"message": "Welcome to Your API"}
