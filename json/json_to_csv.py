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

            all_players.append(flat_player)

df = pd.DataFrame(all_players)

trans_df = pd.read_csv('json/responses/transfer_players.csv', dtype=str)

df["id"] = df["id"].astype(str).str.strip()
df = df.drop_duplicates(
    subset=["id"],
    keep="last"   # беремо останню команду (актуальну)
)

trans_ids = set(trans_df["id"].astype(str).str.strip())

ids_to_update = set(trans_df["id"])
mask = df["id"].isin(ids_to_update)
df.loc[mask, "transfer"] = 2

print("Унікальних ID:", trans_df["id"].nunique())
print(df['transfer'].value_counts(dropna=False))

# --- перейменування колонок під схему таблиці players у БД ---
RENAME_MAP = {
    "id": "playerid",
    "club_country_id": "countryid",
    "club_country_name": "countryname",
    "team_id": "teamid",
    "team_name": "teamname",
    "team_divisionid": "divisionid",
    "team_divisiontype": "divisiontype",
    "number": "number",
    "name": "name",
    "country_id": "nationalityid",
    "country_name": "nationalityname",
    "primaryPosition": "primaryposition",
    "secondaryPosition": "secondaryposition",
    "aspectName": "aspectname",
    "age": "age",
    "stamina": "stamina",
    "tired": "tired",
    "morale": "morale",
    "power": "power",
    "bonuses_str": "bonusesstr",
    "bonusPoints": "bonuspoints",
    "nextBonusPoints": "nextbonuspoints",
    "talent": "talent",
    "rTalent": "rtalent",
    "expLevel": "explevel",
    "expPoints": "exppoints",
    "salary": "salary",
    "cost": "cost",
    "injury": "injury",
    "transfer": "transfer",
    "loan": "loan",
    "skl": "skl",
    "tckl": "tckl",
    "mrk": "mrk",
    "drbl": "drbl",
    "brcv": "brcv",
    "edrnc": "edrnc",
    "pass": "pass",
    "shotPwr": "shotpwr",
    "shotAcc": "shotacc",
    # team_division_name не має відповідної колонки в таблиці БД —
    # лишаємо як є, додамо останньою колонкою нижче
}

df = df.rename(columns=RENAME_MAP)

# порядок колонок як у CREATE TABLE players (+ team_division_name в кінці,
# бо такої колонки в таблиці БД немає)
COLUMN_ORDER = [
    "playerid", "countryid", "countryname",
    "teamid", "teamname", "divisionid", "divisiontype",
    "number", "name",
    "nationalityid", "nationalityname",
    "primaryposition", "secondaryposition", "aspectname", "age",
    "stamina", "tired", "morale", "power",
    "bonusesstr", "bonuspoints", "nextbonuspoints",
    "talent", "rtalent", "explevel", "exppoints",
    "salary", "cost", "injury", "transfer", "loan",
    "skl", "tckl", "mrk", "drbl", "brcv", "edrnc",
    "pass", "shotpwr", "shotacc",
    "team_division_name",
]

df = df[[c for c in COLUMN_ORDER if c in df.columns]]

# Зберігаємо в CSV
df.to_csv("json/responses/all_players.csv", index=False, encoding='utf-8')
