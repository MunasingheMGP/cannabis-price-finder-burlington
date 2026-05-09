"""
Shared PostgreSQL connection config for the MontKailash pipeline.
All scripts import get_engine() from here.
"""

from sqlalchemy import create_engine, text
import pandas as pd

#  CONNECTION 
DB_USER     = "postgres"
DB_PASSWORD = "pgadmin"
DB_HOST     = "localhost"
DB_PORT     = "5432"
DB_NAME     = "cannabis_db"

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)


def get_engine():
    """Return a SQLAlchemy engine. Call once per script."""
    return create_engine(DATABASE_URL, future=True)


#  HELPERS 

def table_exists(engine, table_name: str) -> bool:
    """Check whether a table exists AND has at least one row (cache guard)."""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'public'"
            f" AND table_name = '{table_name}'"
            ")"
        ))
        exists = result.scalar()
        if not exists:
            return False
        count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
        return count > 0


def write_df(df: pd.DataFrame, table_name: str, engine,
             if_exists: str = "replace"):
    """Write a DataFrame to a PostgreSQL table."""
    df.to_sql(table_name, engine, if_exists=if_exists,
              index=False, method="multi", chunksize=500)
    print(f"  DB ← '{table_name}': {len(df)} rows written")


def read_df(table_name: str, engine) -> pd.DataFrame:
    """Read a full table into a DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(f'SELECT * FROM "{table_name}"', conn)
