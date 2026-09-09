from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.api.routes.resume import router as resume_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.applications import router as applications_router
from backend.app.api.routes.tasks import router as tasks_router
from backend.app.api.routes.scheduler import router as scheduler_router
from backend.app.api.routes.auto_apply import router as auto_apply_router
from backend.app.api.routes.analytics import router as analytics_router
from backend.app.core.scheduler import job_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize tables on startup
    init_db()
    yield
    # Graceful shutdown
    if job_scheduler.is_active:
        job_scheduler.stop()


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


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Exempt health checks and documentation from rate limiting
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)
    client_ip = request.client.host if request.client else "127.0.0.1"
    from backend.app.core.security import rate_limiter
    rate_limiter.check_rate_limit(client_ip)
    return await call_next(request)


# Register routers
app.include_router(resume_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(tasks_router)
app.include_router(scheduler_router)
app.include_router(auto_apply_router)
app.include_router(analytics_router)




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

