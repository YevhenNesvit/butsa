import requests
from bs4 import BeautifulSoup
import re
import time

# ==============================================================================
# МОДУЛЬ ФЕТЧІНГУ ДАНИХ
# ==============================================================================

def get_soup(url, cookie):
    """
    Отримує BeautifulSoup об'єкт для заданого URL з cookie аутентифікацією.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': f'PHPSESSID={cookie}'
    }
    try:
        r = requests.get(url, headers=headers)
        r.encoding = 'utf-8' 
        if r.status_code == 200:
            return BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        raise Exception(f"Помилка з'єднання: {e}")
    return None


def parse_player_minutes(player_url, cookie, target_tournament):
    """
    Парсить хвилини гравця для заданого турніру з його профілю.
    Повертає кількість хвилин (int).
    """
    full_url = "https://butsa.pro" + player_url if not player_url.startswith("http") else player_url
    soup = get_soup(full_url, cookie)
    
    if not soup: 
        return 0
    
    # Шукаємо заголовок "Текущий сезон"
    season_header = soup.find(string=re.compile("Текущий сезон"))
    if not season_header: 
        return 0

    # Знаходимо таблицю статистики
    stats_table = season_header.find_next('table')
    if not stats_table: 
        return 0

    rows = stats_table.find_all('tr')
    idx_tourn, idx_mins = 2, 4

    for row in rows:
        cols = row.find_all('td')
        if len(cols) <= idx_mins: 
            continue
        
        row_tourn_name = cols[idx_tourn].get_text(strip=True)
        
        if target_tournament.lower() in row_tourn_name.lower():
            minutes_text = cols[idx_mins].get_text(strip=True)
            clean_mins = re.sub(r'\D', '', minutes_text)
            if clean_mins: 
                return int(clean_mins)
    
    return 0


def scrape_roster(url, cookie, tournament_name, progress_callback=None):
    """
    Скрапить повний ростер команди з урахуванням хвилин у турнірі.
    
    Args:
        url: URL ростера команди
        cookie: PHPSESSID для аутентифікації
        tournament_name: Назва турніру для пошуку хвилин
        progress_callback: Функція для оновлення прогресу (progress, current, total)
    
    Returns:
        List[dict]: Список гравців з їх характеристиками
    """
    soup = get_soup(url, cookie)
    if not soup: 
        return []

    links = soup.find_all('a', href=re.compile(r'/players/\d+$'))
    players = []
    processed_urls = set()
    total_links = len(links)
    
    for i, link in enumerate(links):
        # Оновлення прогресу
        if progress_callback:
            progress_callback((i + 1) / total_links, i + 1, total_links)
        
        href = link.get('href', '')
        if href in processed_urls: 
            continue
        processed_urls.add(href)
        
        row = link.find_parent('tr')
        if not row: 
            continue
        
        cols = row.find_all('td')
        if len(cols) < 10: 
            continue

        try:
            name = link.get_text(strip=True)
            
            # Позиція
            pos_text = cols[3].get_text(strip=True)
            clean_pos = [p.strip().upper() for p in pos_text.split('/')]
            
            # Сила
            p_val = int(re.sub(r'\D', '', cols[5].get_text(strip=True)))
            
            # Стаміна
            s_val = int(re.sub(r'\D', '', cols[7].get_text(strip=True)))
            
            # Мораль
            m_td = cols[10]
            m_title = m_td.get('title', '') or (m_td.find('img').get('title', '') if m_td.find('img') else '')
            m_match = re.search(r'\((\d+)\)', m_title)
            mor_val = int(m_match.group(1)) if m_match else 13

            # Парсинг хвилин з профілю гравця
            mins = parse_player_minutes(href, cookie, tournament_name)

            players.append({
                "name": name,
                "pos": clean_pos,
                "power": p_val,
                "stamina": s_val,
                "morale": mor_val,
                "minutes": mins
            })
            
            time.sleep(0.1)  # Невелика пауза між запитами
            
        except Exception:
            continue
        
    return players
