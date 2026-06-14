from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

load_dotenv()

from src.api.routes import router
from src.database.seed import seed_database
from src.utils.logger import app_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Starting up — seeding database")
    await seed_database()
    app_logger.info("Startup complete")
    yield
    app_logger.info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Data Lineage Agent",
        description="LLM-powered agent that autonomously discovers and documents data lineage",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router, prefix="/api/v1")
    app.mount("/", StaticFiles(directory="src/static", html=True), name="static")
    return app


app = create_app()
