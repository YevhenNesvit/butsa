import requests
from bs4 import BeautifulSoup
import re
import time
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# МОДУЛЬ ФЕТЧІНГУ ДАНИХ (Хвилини + Бонуси + УМІННЯ)
# ==============================================================================

REQUEST_TIMEOUT = 15  # секунд на один запит
FETCH_THREADS = 4     # скільки профілів гравців вантажимо паралельно

def get_soup(url, cookie, session=None):
    # Або лише значення PHPSESSID, або готовий рядок "name=value; name2=value2" (якщо сайт
    # впізнає вхід за кількома cookie, а не за самим PHPSESSID)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': cookie if '=' in cookie else f'PHPSESSID={cookie}'
    }
    try:
        # session перевикористовує з'єднання між запитами замість нового на кожен
        r = (session or requests).get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        r.encoding = 'utf-8' 
        if r.status_code == 200:
            return BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching: {e}")
    return None

def parse_player_details(player_url, cookie, target_tournament, session=None):
    """
    Заходить у профіль гравця і тягне:
    1. Хвилини
    2. Бонуси
    3. Уміння (Скіли)
    4. Майстерність із сотими (у ростері вона округлена, а ліміт сили рахується з сотими)
    """
    full_url = "https://butsa.pro" + player_url if not player_url.startswith("http") else player_url
    soup = get_soup(full_url, cookie, session)

    minutes = 0
    bonuses = {}
    skills = {}

    if not soup: return 0, {}, {}, None

    # --- 1. ПАРСИНГ ХВИЛИН ---
    season_header = soup.find(string=re.compile("Текущий сезон"))
    if season_header:
        stats_table = season_header.find_next('table')
        if stats_table:
            rows = stats_table.find_all('tr')
            idx_tourn, idx_mins = 2, 4
            for row in rows:
                cols = row.find_all('td')
                if len(cols) <= idx_mins: continue
                row_tourn_name = cols[idx_tourn].get_text(strip=True)
                if target_tournament.lower() in row_tourn_name.lower():
                    minutes_text = cols[idx_mins].get_text(strip=True)
                    clean_mins = re.sub(r'\D', '', minutes_text)
                    if clean_mins: minutes = int(clean_mins)
                    break 

    # --- 2. ПАРСИНГ БОНУСІВ ---
    bonus_label = soup.find('td', string=re.compile(r'^\s*Бонусы\s*$'))
    if bonus_label:
        row = bonus_label.find_parent('tr')
        if row:
            bs = row.find_all('td')
            if len(bs) > 1:
                bonus_text = bs[1].get_text(strip=True)
                matches = re.findall(r'([А-Яа-я]{2})(\d?)', bonus_text)
                for code, lvl in matches:
                    level = int(lvl) if lvl else 1
                    bonuses[code] = level

    # --- 3. ПАРСИНГ УМІНЬ ---
    skill_names = [
        "Отбор", "Опека", "Дриблинг", "Прием мяча", 
        "Выносливость", "Пас", "Сила удара", "Точность удара", "Голкиперство"
    ]
    for s_name in skill_names:
        # Шукаємо комірку з точною назвою уміння
        s_td = soup.find('td', string=re.compile(rf'^\s*{s_name}\s*$'))
        if s_td:
            row = s_td.find_parent('tr')
            if row:
                tds = row.find_all('td')
                if len(tds) >= 2:
                    # Беремо останню комірку (це зазвичай ефективне значення з урахуванням бонусів)
                    val_str = tds[1].get_text(strip=True).replace(',', '.')
                    try:
                        skills[s_name] = float(re.sub(r'[^\d.]', '', val_str))
                    except ValueError:
                        skills[s_name] = 0.0

    # --- 4. ПАРСИНГ МАЙСТЕРНОСТІ (блок "Характеристики", перша комірка після назви) ---
    mastery = None
    mastery_label = soup.find('td', string=re.compile(r'^\s*Мастерство\s*$'))
    if mastery_label:
        row = mastery_label.find_parent('tr')
        if row:
            tds = row.find_all('td')
            if len(tds) >= 2:
                val_str = tds[1].get_text(strip=True).replace(',', '.')
                try:
                    mastery = float(re.sub(r'[^\d.]', '', val_str))
                except ValueError:
                    mastery = None

    return minutes, bonuses, skills, mastery


def scrape_roster(url, cookie, tournament_name, progress_callback=None):
    session = requests.Session()
    soup = get_soup(url, cookie, session)
    if not soup: return "Помилка", []

    team_name = "Команда"
    team_label = soup.find('td', string=re.compile(r'^\s*Команда\s*$'))
    if team_label:
        row = team_label.find_parent('tr')
        if row:
            span = row.find('span')
            if span:
                team_name = span.get_text(strip=True)

    links = soup.find_all('a', href=re.compile(r'/players/\d+$'))
    players = []
    processed_urls = set()
    pending = []  # (базові дані гравця, href): профілі довантажуємо паралельно нижче

    for link in links:
        href = link.get('href', '')
        if href in processed_urls: continue
        processed_urls.add(href)
        
        row = link.find_parent('tr')
        if not row: continue
        cols = row.find_all('td')
        if len(cols) < 10: continue

        try:
            name = link.get_text(strip=True)
            pos_text = cols[3].get_text(strip=True)
            clean_pos = [p.strip().upper() for p in pos_text.split('/')]
            p_val = int(re.sub(r'\D', '', cols[5].get_text(strip=True)))
            s_val = int(re.sub(r'\D', '', cols[7].get_text(strip=True)))
            # Вік (колонка "Воз"); без нього гравець не відкидається, лише рахуємо за віком за замовчуванням
            age_digits = re.sub(r'\D', '', cols[4].get_text(strip=True))
            age = int(age_digits) if age_digits else None

            is_injured = False
            injury_img = row.find('img', src=re.compile(r'injury\.gif'))
            if injury_img: is_injured = True
            else:
                for img in row.find_all('img'):
                    if img.get('title', '').lower() == 'травма' or img.get('alt', '').lower() == 'травма':
                        is_injured = True
                        break

            m_td = cols[10]
            m_title = m_td.get('title', '') or (m_td.find('img').get('title', '') if m_td.find('img') else '')
            m_match = re.search(r'\((\d+)\)', m_title)
            mor_val = int(m_match.group(1)) if m_match else 13

            pending.append(((name, clean_pos, p_val, s_val, mor_val, is_injured, age), href))

        except Exception:
            continue

    def load_player(item):
        (name, clean_pos, p_val, s_val, mor_val, is_injured, age), href = item
        try:
            # [ЗМІНЕНО] Тепер розпаковуємо 4 змінні (включаючи skills і точне майстерство)
            mins, bonuses, skills, mastery = parse_player_details(href, cookie, tournament_name, session)
            time.sleep(0.1)
        except Exception:
            return None
        # Ростер округлює майстерність, а ліміт сили рахується з сотими. Точне значення
        # беремо лише якщо воно узгоджується з ростером (округлення дає розбіжність <= 0.5)
        power = mastery if mastery is not None and abs(mastery - p_val) <= 1.0 else p_val
        return {
            "name": name,
            "pos": clean_pos,
            "age": age,
            "power": power,
            "stamina": s_val,
            "morale": mor_val,
            "minutes": mins,
            "is_injured": is_injured,
            "bonuses": bonuses,
            "skills": skills  # <--- Додали уміння
        }

    # map зберігає порядок гравців, як у ростері
    with ThreadPoolExecutor(max_workers=FETCH_THREADS) as pool:
        for i, player in enumerate(pool.map(load_player, pending)):
            if progress_callback:
                progress_callback((i + 1) / len(pending), i + 1, len(pending))
            if player:
                players.append(player)

    return team_name, players
