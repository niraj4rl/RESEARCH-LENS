import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


def init_engine():
    """
    Try candidate database URLs in priority order and return the first engine
    that can connect.  Falls back to a local SQLite file so the app always
    starts, even without Docker / Postgres.
    """
    candidate_urls: list[str] = []

    # 1. Explicit environment variable wins
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        candidate_urls.append(db_url)

    # 2. Docker-compose container (port 5433)
    candidate_urls.append(
        "postgresql://researchlens:researchlens_password@localhost:5433/researchlens_db"
    )

    # 3. Local Postgres fallbacks
    candidate_urls.append("postgresql://postgres:Niraj%402005@localhost:5432/postgres")
    candidate_urls.append("postgresql://postgres:postgres@localhost:5432/postgres")

    # 4. Zero-config SQLite (always works)
    candidate_urls.append("sqlite:///./researchlens.db")

    for url in candidate_urls:
        try:
            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
            kwargs = {"connect_args": connect_args}
            if not url.startswith("sqlite"):
                kwargs["pool_pre_ping"] = True

            eng = create_engine(url, **kwargs)
            # Probe the connection
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))

            display_url = url.split("@")[-1] if "@" in url else url
            print(f"[DATABASE] Connected on: {display_url}")
            return eng
        except Exception as exc:
            display_url = url.split("@")[-1] if "@" in url else url
            print(f"[DATABASE] Skipping {display_url}: {exc}")
            continue

    # Guaranteed fallback
    print("[DATABASE] All candidates failed — using SQLite ./researchlens.db")
    eng = create_engine(
        "sqlite:///./researchlens.db",
        connect_args={"check_same_thread": False},
    )
    return eng


def migrate_schema(eng):
    """Ensure all tables and new columns exist across SQLite and PostgreSQL."""
    try:
        import models  # noqa: F401
        from sqlalchemy import inspect
        Base.metadata.create_all(bind=eng)
        inspector = inspect(eng)
        tables = inspector.get_table_names()
        
        if "analyses" in tables:
            existing_cols = {col["name"] for col in inspector.get_columns("analyses")}
            analyses_defs = {
                "stage": "VARCHAR(50) DEFAULT 'queued'",
                "error_message": "TEXT",
                "failed_stage": "VARCHAR(50)",
                "papers_retrieved": "INTEGER DEFAULT 0",
                "papers_analysed": "INTEGER DEFAULT 0",
                "raw_provider_results": "INTEGER DEFAULT 0",
                "deduplicated_papers": "INTEGER DEFAULT 0",
                "retained_papers": "INTEGER DEFAULT 0",
                "full_text_analysed": "INTEGER DEFAULT 0",
                "year_start": "INTEGER",
                "year_end": "INTEGER",
            }
            with eng.begin() as conn:
                for col_name, definition in analyses_defs.items():
                    if col_name not in existing_cols:
                        conn.execute(text(f'ALTER TABLE analyses ADD COLUMN "{col_name}" {definition}'))

        if "research_gaps" in tables:
            existing_cols = {col["name"] for col in inspector.get_columns("research_gaps")}
            gap_defs = {
                "source_coverage": "TEXT",
                "qualifications": "TEXT",
            }
            with eng.begin() as conn:
                for col_name, definition in gap_defs.items():
                    if col_name not in existing_cols:
                        conn.execute(text(f'ALTER TABLE research_gaps ADD COLUMN "{col_name}" {definition}'))

        if "gap_evidence" in tables:
            existing_cols = {col["name"] for col in inspector.get_columns("gap_evidence")}
            if "source_scope" not in existing_cols:
                with eng.begin() as conn:
                    conn.execute(text('ALTER TABLE gap_evidence ADD COLUMN "source_scope" VARCHAR(50) DEFAULT \'abstract_only\''))

        if "research_papers" in tables:
            existing_cols = {col["name"] for col in inspector.get_columns("research_papers")}
            paper_defs = {
                "doi": "VARCHAR(255)",
                "url": "VARCHAR(1024)",
                "pdf_url": "VARCHAR(1024)",
                "source": "VARCHAR(100)",
            }
            with eng.begin() as conn:
                for col_name, definition in paper_defs.items():
                    if col_name not in existing_cols:
                        conn.execute(text(f'ALTER TABLE research_papers ADD COLUMN "{col_name}" {definition}'))

        if eng.dialect.name == "postgresql":
            with eng.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE paper_authors DROP CONSTRAINT IF EXISTS paper_authors_paper_id_fkey;"
                    "ALTER TABLE paper_authors ADD CONSTRAINT paper_authors_paper_id_fkey "
                    "FOREIGN KEY (paper_id) REFERENCES research_papers (id) ON DELETE CASCADE;"
                    "ALTER TABLE paper_topics DROP CONSTRAINT IF EXISTS paper_topics_paper_id_fkey;"
                    "ALTER TABLE paper_topics ADD CONSTRAINT paper_topics_paper_id_fkey "
                    "FOREIGN KEY (paper_id) REFERENCES research_papers (id) ON DELETE CASCADE;"
                ))
    except Exception as exc:
        print(f"[DATABASE] Schema migration note: {exc}")


engine = init_engine()
migrate_schema(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

