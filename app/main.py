from dotenv import load_dotenv
from fastapi import FastAPI
from .routes import auth, users, api_keys, agents, chat, model_settings, data_source, dashboard, subscriptions
from .database import engine
from .models import user, subscription
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Create database tables
user.Base.metadata.create_all(bind=engine)
subscription.Base.metadata.create_all(bind=engine)

origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://3.112.199.154:3000",
    "https://3.112.199.154:3000",
    "http://app.finiite.com",
    "https://app.finiite.com",
]

app = FastAPI(title="Finiite API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicitly list methods
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
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
app.include_router(subscriptions.router)

@app.get("/")
def root():
    return {"message": "Welcome to Your API"}
