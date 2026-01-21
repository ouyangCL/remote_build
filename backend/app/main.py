"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import deployments, projects, servers, users
from app.api.auth import router as auth_router
from app.config import settings
from app.db.session import ensure_directories, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Args:
        app: FastAPI application

    Yields:
        None
    """
    # Startup
    init_db()
    ensure_directories()

    yield

    # Shutdown
    pass


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(projects.router)
app.include_router(servers.router)
app.include_router(servers.groups_router)
app.include_router(deployments.router)
app.include_router(users.router)
app.include_router(users.audit_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Welcome message
    """
    return {"message": "DevOps Deployment Platform API", "version": settings.app_version}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
