from fastapi import FastAPI
from .routes import auth, users, api_keys
from .database import engine
from .models import user
from fastapi.middleware.cors import CORSMiddleware
# Create database tables
user.Base.metadata.create_all(bind=engine)

origins = [
    "http://localhost:3000",  # Allow requests from your frontend
]

app = FastAPI(title="Your API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allow cookies (if needed)
    allow_methods=["*"],     # Allow all HTTP methods
    allow_headers=["*"],     # Allow all headers
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(api_keys.router)

@app.get("/")
def root():
    return {"message": "Welcome to Your API"}
