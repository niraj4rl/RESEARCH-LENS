import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from database import engine, Base
from sqlalchemy import inspect, text
import models  # noqa: F401 – side-effect: registers all ORM classes with Base
from api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all DB tables on startup (idempotent)."""
    try:
        Base.metadata.create_all(bind=engine)
        # create_all does not add columns to an existing table.
        inspector = inspect(engine)
        if "analyses" in inspector.get_table_names():
            existing_columns = {col["name"] for col in inspector.get_columns("analyses")}
            analyses_defs = {
                "stage": "VARCHAR(50) DEFAULT 'queued'",
                "error_message": "TEXT",
                "failed_stage": "VARCHAR(50)",
                "papers_retrieved": "INTEGER DEFAULT 0",
                "papers_analysed": "INTEGER DEFAULT 0",
                "year_start": "INTEGER",
                "year_end": "INTEGER",
            }
            with engine.begin() as connection:
                for col_name, definition in analyses_defs.items():
                    if col_name not in existing_columns:
                        connection.execute(text(f'ALTER TABLE analyses ADD COLUMN "{col_name}" {definition}'))

        if "research_papers" in inspector.get_table_names():
            existing_paper_cols = {col["name"] for col in inspector.get_columns("research_papers")}
            paper_defs = {
                "doi": "VARCHAR(255)",
                "url": "VARCHAR(1024)",
                "pdf_url": "VARCHAR(1024)",
                "source": "VARCHAR(100)",
            }
            with engine.begin() as connection:
                for col_name, definition in paper_defs.items():
                    if col_name not in existing_paper_cols:
                        connection.execute(text(f'ALTER TABLE research_papers ADD COLUMN "{col_name}" {definition}'))

        with engine.begin() as connection:
            if engine.dialect.name == "postgresql":
                connection.execute(text(
                    "ALTER TABLE paper_authors DROP CONSTRAINT IF EXISTS paper_authors_paper_id_fkey"
                ))
                connection.execute(text(
                    "ALTER TABLE paper_authors ADD CONSTRAINT paper_authors_paper_id_fkey "
                    "FOREIGN KEY (paper_id) REFERENCES research_papers (id) ON DELETE CASCADE"
                ))
                connection.execute(text(
                    "ALTER TABLE paper_topics DROP CONSTRAINT IF EXISTS paper_topics_paper_id_fkey"
                ))
                connection.execute(text(
                    "ALTER TABLE paper_topics ADD CONSTRAINT paper_topics_paper_id_fkey "
                    "FOREIGN KEY (paper_id) REFERENCES research_papers (id) ON DELETE CASCADE"
                ))
        print("[DATABASE] Schema verified — all tables exist.")
    except Exception as exc:
        print(f"[DATABASE ERROR] Could not create schema on startup: {exc}")
    yield


app = FastAPI(
    title="ResearchLens API",
    description="AI-Assisted Research Gap Discovery and Recommendation System",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Global exception handler — return JSON instead of plain-text 500 HTML so
# the frontend can always parse the error body.
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request body.", "details": str(exc.errors())},
    )


# CORS
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
_allowed_origins = _default_origins + _extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router.router, prefix="/api/research", tags=["research"])


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
