import argparse
import csv
import json
import os
import re
import time

import requests

from fetcher import get_soup

# ==============================================================================
# ЕКСПОРТ МАТЧІВ КОМАНД У CSV (для калібрування рушія)
# Збирає звіти матчів вибраного турніру з сторінок "Всі матчі" команд.
# Рядки тактики, пресингу, стратегії й передач видно лише з cookie учасника матчу.
# ==============================================================================

BASE = "https://www.butsa.pro/xml"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'matches_commercial.csv')
FIXED_COLUMNS = ['id', 'team_id', 'date', 'tour', 'home', 'away', 'score', 'tp']


def load_cookie():
    """Cookie беремо зі змінної BUTSA_COOKIE або з config.json (поле cookie), без нього тактики не буде.
    Значення: або PHPSESSID, або повний рядок cookie "name=value; name2=value2" (його не треба зберігати у файл)."""
    cookie = os.environ.get('BUTSA_COOKIE', '')
    if not cookie and os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cookie = json.load(f).get('cookie', '')
    return cookie


def list_matches(team_id, tournament, cookie, session, max_pages=10):
    """Матчі команди з потрібного турніру: {id матчу: дані зі списку}"""
    found = {}
    for page in range(1, max_pages + 1):
        url = f"{BASE}/players/roster.php?act=allmatches&id={team_id}"
        if page > 1:
            url += f"&page={page}&type=players/roster"
        soup = get_soup(url, cookie, session)
        if not soup:
            break
        new_on_page = 0
        for a in soup.find_all('a', href=re.compile(r'tour/match\.php\?id=\d+')):
            match_id = int(re.search(r'id=(\d+)', a['href']).group(1))
            cells = [c.get_text(' ', strip=True) for c in a.find_parent('tr').find_all('td')]
            if len(cells) < 5 or match_id in found:
                continue
            new_on_page += 1
            if tournament.lower() in cells[4].lower():
                found[match_id] = {'team_id': team_id, 'date': cells[0], 'home': cells[1],
                                   'score': cells[2], 'away': cells[3], 'tour': cells[4]}
        if new_on_page == 0:
            break
    return found


def read_report(match_id, cookie, session):
    """Рядки статистики звіту: підпис посередині, значення для господарів і гостей з боків"""
    soup = get_soup(f"{BASE}/tour/match.php?id={match_id}", cookie, session)
    if not soup:
        return None, {}
    stats = {}
    for tr in soup.find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all('td')]
        label = cells[1] if len(cells) == 3 else ''
        # підпис статистики: текст без цифр у середині (рядки гравців і шапка мають інший вигляд)
        if label and len(label) < 40 and not re.search(r'\d', label) and cells[0] and cells[2]:
            stats[label] = (cells[0], cells[2])
    return ('ТП' in soup.get_text(' ')), stats


def main():
    parser = argparse.ArgumentParser(description="Експорт матчів команд butsa.pro у CSV")
    parser.add_argument('team_ids', nargs='*', type=int, default=[343, 11322, 39], help="ID команд")
    parser.add_argument('--tournament', default='Коммерческие турниры', help="частина назви турніру")
    parser.add_argument('--out', default=DEFAULT_OUT)
    args = parser.parse_args()

    cookie = load_cookie()
    print("Cookie знайдено, тактика буде в звітах." if cookie else "Cookie немає: рядків тактики не буде.")
    session = requests.Session()

    matches = {}
    for team_id in args.team_ids:
        for match_id, info in list_matches(team_id, args.tournament, cookie, session).items():
            matches.setdefault(match_id, info)
    print(f"Знайдено матчів: {len(matches)}")

    rows, labels = [], []
    for match_id, info in matches.items():
        tp, stats = read_report(match_id, cookie, session)
        row = {'id': match_id, 'tp': int(bool(tp)), **info}
        for label, (home, away) in stats.items():
            if label not in labels:
                labels.append(label)
            row[f'{label} (господарі)'], row[f'{label} (гості)'] = home, away
        rows.append(row)
        time.sleep(0.2)

    columns = FIXED_COLUMNS + [f'{l} ({side})' for l in labels for side in ('господарі', 'гості')]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, restval='')
        writer.writeheader()
        writer.writerows(rows)
    print(f"Збережено {len(rows)} матчів у {args.out}")
    print("Колонки статистики:", ', '.join(labels))


if __name__ == '__main__':
    main()
