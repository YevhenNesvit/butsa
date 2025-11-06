import json
import pandas as pd
from pathlib import Path
from data import unions   # імпортуємо словник divisionid → назва

def flatten_dict(d, parent_key='', sep='_'):
    """
    Рекурсивно розплющує вкладені словники.
    Наприклад {'a': {'b': 1}} -> {'a_b': 1}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

folder = Path("json/responses")
files = folder.glob("country_*.json")

all_players = []

for file in files:
    with open(file, encoding='utf-8') as f:
        data = json.load(f)

    club_country_id = data.get("id")
    club_country_name = data.get("name")

    for team_key, team in data.get("teams", {}).items():
        team_id = team.get("id") or team_key
        team_name = team.get("name")
        team_divisionid = team.get("divisionid")
        team_divisiontype = team.get("divisiontype")

        # шукаємо назву дивізіону у словнику unions
        division_name = None
        if team_divisionid and team_divisionid.isdigit():
            division_name = unions.get(int(team_divisionid))

        for player_key, player in team.get("players", {}).items():
            flat_player = flatten_dict(player)

            # дані країни клубу
            flat_player["club_country_id"] = club_country_id
            flat_player["club_country_name"] = club_country_name

            # дані команди
            flat_player["team_id"] = team_id
            flat_player["team_name"] = team_name
            flat_player["team_divisionid"] = team_divisionid
            flat_player["team_divisiontype"] = team_divisiontype
            flat_player["team_division_name"] = division_name

            all_players.append(flat_player)

df = pd.DataFrame(all_players)

trans_df = pd.read_csv('json/responses/transfer_players.csv', dtype=str)

df["id"] = df["id"].astype(str).str.strip()
trans_ids = set(trans_df["id"].astype(str).str.strip())

ids_to_update = set(trans_df["id"])
mask = df["id"].isin(ids_to_update)
df.loc[mask, "transfer"] = 2

print("Унікальних ID:", trans_df["id"].nunique())
print(df['transfer'].value_counts(dropna=False))

# Зберігаємо в CSV
df.to_csv("json/responses/all_players.csv", index=False, encoding='utf-8')
