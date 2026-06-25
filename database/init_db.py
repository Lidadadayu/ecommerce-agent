from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db import execute_sql_file


BASE_DIR = Path(__file__).resolve().parent.parent

SCHEMA_FILE = BASE_DIR / "database" / "schema.sql"
SEED_FILE = BASE_DIR / "data" / "seed_sample.sql"


def main() -> None:
    print("Creating database tables...")
    execute_sql_file(SCHEMA_FILE)

    print("Inserting sample data...")
    execute_sql_file(SEED_FILE)

    print("Database initialization completed.")


if __name__ == "__main__":
    main()