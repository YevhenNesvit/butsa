"""Один запуск замість трьох: країни -> трансфери -> all_players.csv.

Запуск з будь-якої папки:  python json/run_all.py
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # скрипти використовують шляхи виду json/responses/...

STEPS = [
    "fetch_players.py",     # country_*.json
    "transfer_players.py",  # transfer_players.csv
    "json_to_csv.py",       # all_players.csv
]


def main():
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        subprocess.run([sys.executable, str(HERE / step)], cwd=ROOT, check=True)

        if step == "transfer_players.py":
            # без логіну скрипт тихо пише порожній CSV — зупиняємось одразу
            csv = HERE / "responses" / "transfer_players.csv"
            if not csv.exists() or pd.read_csv(csv).empty:
                sys.exit("transfer_players.csv порожній — перевірте логін/пароль у .env")

    print("\nГотово: json/responses/all_players.csv")


if __name__ == "__main__":
    main()
