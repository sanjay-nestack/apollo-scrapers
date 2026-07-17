"""Explicit context objects that replace the old module-level driver/wait globals."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ScrapeSession:
    """Per-account browser state (was the `driver` / `wait` module globals)."""
    driver: Any = None
    wait: Any = None
    email: str = ""
    password: str = ""


@dataclass
class Conditions:
    """Per-account 22h freshness flags. Only condition2 AND condition3 gate the
    whole account; condition1 and condition4 are computed for parity but do not gate."""
    condition1: bool = False
    condition2: bool = False
    condition3: bool = False
    condition4: bool = True


@dataclass
class RunContext:
    """Run-wide, immutable-ish config/state built once in main() before the loop."""
    base_folder: str
    search_csv: str
    credits_csv: str
    upload_csv: str
    sleep_between_accounts: float
    months_to_include: int
    max_people_rows: int
    enable_aws_upload: bool
    db: Any = None
    search_df: Any = None
    credits_df: Any = None
    upload_df: Any = None
    final_df_sorted: Any = None
    email_number: int = 0
