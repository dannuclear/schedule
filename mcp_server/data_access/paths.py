import os
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR = Path(
    os.environ.get("DATA_DIR", str(DEFAULT_DATA_DIR))
).expanduser().resolve()
BASE_SCHEDULE_PATH = DATA_DIR / "base" / "schedule.json"
WEEK_SCHEDULES_DIR = DATA_DIR / "weeks"
EXPORTS_DIR = Path(os.environ.get("EXPORTS_DIR", str(DATA_DIR / "exports"))).resolve()
