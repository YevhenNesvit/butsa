import json
import pandas as pd
from pathlib import Path

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
    
    country_name = data.get("name")
    
    for team_id, team in data.get("teams", {}).items():
        team_name = team.get("name")
        
        for player_id, player in team.get("players", {}).items():
            # flatten всі поля гравця
            flat_player = flatten_dict(player)
            # додаємо країну та команду
            flat_player["country"] = country_name
            flat_player["team"] = team_name
            all_players.append(flat_player)

df = pd.DataFrame(all_players)

# Зберігаємо в CSV
df.to_csv("json/responses/players_flat_all.csv", index=False, encoding='utf-8')
