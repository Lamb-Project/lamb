#!/usr/bin/env python3

"""Backfill Open WebUI user settings for LAMB.

Open WebUI stores per-user UI preferences in the `user.settings` JSON column.
When `settings.ui.showUpdateToast` / `settings.ui.showChangelog` are missing,
Open WebUI's frontend defaults them to `true`.

This script backfills existing users so those keys exist and are set to `false`
when missing.

Safe to run multiple times (idempotent).

Usage:
  python3 scripts/backfill_owi_user_ui_settings.py [--dry-run] [--db-path /path/to/webui.db]

Notes:
  - If --db-path is not provided, the script tries:
      1) $OWI_PATH/webui.db
      2) $OWI_DATA_PATH/webui.db
      3) common repo-relative locations (open-webui/backend/data/webui.db, ...)
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"


def print_color(color: str, text: str) -> None:
    print(f"{color}{text}{Colors.NC}")


def find_database(db_path: str | None) -> str:
    if db_path:
        if not os.path.isfile(db_path):
            print_color(Colors.RED, f"Error: Database not found at {db_path}")
            sys.exit(1)
        return db_path

    env_owi_path = os.getenv("OWI_PATH")
    if env_owi_path:
        candidate = os.path.join(env_owi_path, "webui.db")
        if os.path.isfile(candidate):
            return candidate

    env_owi_data_path = os.getenv("OWI_DATA_PATH")
    if env_owi_data_path:
        candidate = os.path.join(env_owi_data_path, "webui.db")
        if os.path.isfile(candidate):
            return candidate

    script_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(script_dir, "../open-webui/backend/data/webui.db"),
        os.path.join(script_dir, "../backend/data/webui.db"),
        "./open-webui/backend/data/webui.db",
        "./backend/data/webui.db",
        "../open-webui/backend/data/webui.db",
        os.path.expanduser("~/.open-webui/webui.db"),
    ]

    for path in possible_paths:
        expanded = os.path.expanduser(path)
        if os.path.isfile(expanded):
            return expanded

    print_color(Colors.RED, "Error: Could not find webui.db")
    print("Please specify the database path with --db-path")
    sys.exit(1)


def backup_database(db_path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.bak.{ts}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def ensure_ui_flags(settings_value):
    """Return (new_settings_dict, changed_bool)."""
    changed = False

    if settings_value is None or settings_value == "":
        settings = {}
        changed = True
    else:
        if isinstance(settings_value, (bytes, bytearray)):
            settings_value = settings_value.decode("utf-8", errors="replace")
        if isinstance(settings_value, str):
            try:
                settings = json.loads(settings_value)
            except json.JSONDecodeError:
                return None, False
        elif isinstance(settings_value, dict):
            settings = settings_value
        else:
            return None, False

    if not isinstance(settings, dict):
        return None, False

    ui = settings.get("ui")
    if ui is None:
        ui = {}
        settings["ui"] = ui
        changed = True

    if not isinstance(ui, dict):
        return None, False

    if "showUpdateToast" not in ui:
        ui["showUpdateToast"] = False
        changed = True

    if "showChangelog" not in ui:
        ui["showChangelog"] = False
        changed = True

    return settings, changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill Open WebUI user.settings UI flags (showUpdateToast/showChangelog) to false when missing"
    )
    parser.add_argument("--db-path", help="Path to the webui.db database")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a .bak timestamped copy of the database before writing",
    )

    args = parser.parse_args()

    db_path = find_database(args.db_path)
    print_color(Colors.BLUE, f"Using database: {db_path}")

    if not args.dry_run and not args.no_backup:
        backup_path = backup_database(db_path)
        print_color(Colors.GREEN, f"Backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    updated = 0
    skipped_invalid = 0
    unchanged = 0

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, email, settings FROM "user"')
        rows = cursor.fetchall()

        print_color(Colors.BLUE, f"Scanning {len(rows)} users...")

        now = int(time.time())

        for row in rows:
            user_id = row["id"]
            email = row["email"]
            settings_value = row["settings"]

            new_settings, changed = ensure_ui_flags(settings_value)
            if new_settings is None:
                skipped_invalid += 1
                print_color(
                    Colors.YELLOW,
                    f"Skipping user {email} ({user_id}): settings JSON invalid or unexpected type",
                )
                continue

            if not changed:
                unchanged += 1
                continue

            updated += 1

            if args.dry_run:
                print_color(
                    Colors.GREEN,
                    f"Would update user {email} ({user_id}): add missing ui flags",
                )
                continue

            cursor.execute(
                'UPDATE "user" SET settings = ?, updated_at = ? WHERE id = ?',
                (json.dumps(new_settings), now, user_id),
            )

        if args.dry_run:
            print_color(Colors.YELLOW, "DRY RUN: no changes were written")
        else:
            conn.commit()

    finally:
        conn.close()

    print()
    print_color(Colors.BLUE, "SUMMARY")
    print(f"Users updated: {Colors.GREEN}{updated}{Colors.NC}")
    print(f"Users unchanged: {Colors.GREEN}{unchanged}{Colors.NC}")
    if skipped_invalid:
        print(
            f"Users skipped (invalid settings): {Colors.YELLOW}{skipped_invalid}{Colors.NC}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
