from fastapi import FastAPI
from .routes import auth, users
from .database import engine
from .models import user

# Create database tables
user.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Your API")

# Include routers
app.include_router(auth.router)
app.include_router(users.router)

@app.get("/")
def root():
    return {"message": "Welcome to Your API"}
