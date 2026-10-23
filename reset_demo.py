"""Delete only the Prometheus demo database and reseed it."""

from pathlib import Path
from models import DATABASE_PATH, engine

engine.dispose()
path = Path(DATABASE_PATH)
if path.exists():
    path.unlink()

from database import init_database
from seed import seed_demo_data

init_database()
seed_demo_data()
print(f"Reset complete: {path}")
