from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.api.routes.resume import router as resume_router
from backend.app.api.routes.jobs import router as jobs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize tables on startup
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Backend API service for AI Job Application Agent",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(resume_router)
app.include_router(jobs_router)


@app.get("/", tags=["Root"])
def read_root():
    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "version": "0.1.0"
    }


@app.patch("/profile", tags=["Profile"])
def update_profile_direct(update_data: dict):
    """Direct alias for updating candidate profile preferences."""
    from backend.app.models.resume import CandidateProfileUpdate
    from backend.app.services.resume_service import resume_service
    parsed = CandidateProfileUpdate.model_validate(update_data)
    return resume_service.update_profile(parsed)

