import requests
from bs4 import BeautifulSoup
import json
import re
import time

# ==============================================================================
# 1. НАЛАШТУВАННЯ
# ==============================================================================
TARGET_ROSTER_URL = "https://butsa.pro/roster/3469/" # <-- ID команди суперника
MY_COOKIE = "36nvedj4e7r5g1hhbacd9r1oac" 

# НАЗВА ТУРНІРУ (Точно як у таблиці!)
TARGET_TOURNAMENT = "Коммерческие турниры" 
# Приклади: "Чемпионат страны", "Кубок страны", "Товарищеские матчи"

# ==============================================================================
# 2. ФУНКЦІЇ
# ==============================================================================
def get_soup(url, cookie):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': f'PHPSESSID={cookie}'
    }
    try:
        r = requests.get(url, headers=headers)
        # Сайт віддає UTF-8 в метатегах, але іноді заголовки плутають. 
        # Beautiful Soup зазвичай сам розбирається, але про всяк випадок:
        r.encoding = 'utf-8' 
        if r.status_code == 200:
            return BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None

def parse_player_minutes(player_url, cookie, target_tournament):
    """
    Знаходить таблицю "Текущий сезон" і шукає хвилини в заданому турнірі.
    """
    full_url = "https://butsa.pro" + player_url if not player_url.startswith("http") else player_url
    soup = get_soup(full_url, cookie)
    
    if not soup: return 0, "Error"

    # 1. Шукаємо заголовок "Текущий сезон"
    # Використовуємо пошук по тексту, бо структура може бути вкладеною
    season_header = soup.find(string=re.compile("Текущий сезон"))
    
    if not season_header:
        # Якщо раптом заголовка немає (гравець не грав ніде), повертаємо 0
        return 0, "No Season Data"

    # 2. Знаходимо найближчу таблицю ПІСЛЯ цього заголовка
    # .find_next('table') шукає наступний тег table в HTML-дереві
    stats_table = season_header.find_next('table')
    
    if not stats_table:
        return 0, "No Table"

    # 3. Парсимо рядки цієї таблиці
    rows = stats_table.find_all('tr')
    
    # Визначаємо індекси колонок (про всяк випадок, хоча структура стабільна)
    # Стандарт: [Клуб] [С] [Турнир] [Игр] [Минут] ...
    # Індекси (0-based): 2 - Турнір, 4 - Хвилини
    idx_tourn = 2
    idx_mins = 4

    for row in rows:
        cols = row.find_all('td')
        # Пропускаємо заголовки і короткі рядки
        if len(cols) <= idx_mins: continue
        
        # Отримуємо назву турніру в рядку
        row_tourn_name = cols[idx_tourn].get_text(strip=True)
        
        # Перевірка на співпадіння (ігноруємо регістр)
        if target_tournament.lower() in row_tourn_name.lower():
            # Знайшли потрібний турнір! Беремо хвилини.
            minutes_text = cols[idx_mins].get_text(strip=True)
            
            # Чистим від сміття (на всяк випадок)
            clean_mins = re.sub(r'\D', '', minutes_text)
            
            if clean_mins:
                return int(clean_mins), row_tourn_name

    # Якщо пройшли всю таблицю "Текущий сезон" і не знайшли турнір
    return 0, "Not Played"

def scrape_roster_deep(url, cookie):
    print(f"🕵️  Аналіз ростера: {url}")
    soup = get_soup(url, cookie)
    if not soup: return []

    players = []
    # Шукаємо рядки з гравцями. Зазвичай це посилання на /players/
    # Шукаємо всі посилання, що ведуть на профіль
    links = soup.find_all('a', href=re.compile(r'/players/\d+$'))
    
    print(f"✅ Знайдено {len(links)} посилань на гравців. Починаємо сканування...")
    
    count = 0
    # Щоб не дублювати гравців (іноді посилання повторюються), використовуємо set
    processed_urls = set()

    for link in links:
        href = link.get('href', '')
        if href in processed_urls: continue
        processed_urls.add(href)
        
        # Знаходимо батьківський рядок (tr) для цього посилання, щоб взяти стат
        row = link.find_parent('tr')
        if not row: continue
        
        cols = row.find_all('td')
        if len(cols) < 10: continue # Це не рядок ростера

        try:
            name = link.get_text(strip=True)
            
            # Позиція (Колонка 3)
            pos_text = cols[3].get_text(strip=True)
            clean_pos = [p.strip().upper() for p in pos_text.split('/')]
            
            # Сила (Колонка 5)
            p_val = int(re.sub(r'\D', '', cols[5].get_text(strip=True)))
            
            # Стаміна (Колонка 7)
            s_val = int(re.sub(r'\D', '', cols[7].get_text(strip=True)))
            
            # Мораль (Колонка 10)
            m_td = cols[10]
            m_title = m_td.get('title', '') or (m_td.find('img').get('title', '') if m_td.find('img') else '')
            m_match = re.search(r'\((\d+)\)', m_title)
            mor_val = int(m_match.group(1)) if m_match else 13

            # --- ЗАХІД В ПРОФІЛЬ ---
            # Форматуємо вивід, щоб було красиво
            print(f"   [{count+1}/{len(links)}] {name[:20]:<20} ", end="")
            
            mins, found_tourn = parse_player_minutes(href, cookie, TARGET_TOURNAMENT)
            
            if mins > 0:
                print(f"-> {mins} хв ✅")
            else:
                print(f"-> 0 хв") # Не грав або не знайдено

            players.append({
                "name": name,
                "pos": clean_pos,
                "power": p_val,
                "stamina": s_val,
                "morale": mor_val,
                "minutes": mins
            })
            count += 1
            time.sleep(0.2) # Невелика пауза

        except Exception as e:
            # print(f"Помилка: {e}") 
            continue

    return players

# ==============================================================================
# 3. ЗАПУСК
# ==============================================================================

final_data = scrape_roster_deep(TARGET_ROSTER_URL, MY_COOKIE)

if final_data:
    final_data.sort(key=lambda x: x['minutes'], reverse=True)
    
    print(f"\n📊 РЕЗУЛЬТАТ (Турнир: {TARGET_TOURNAMENT}):")
    print(f"{'Ім\'я':<25} | {'Хв':<5} | {'Сила'}")
    print("-" * 45)
    for p in final_data:
        if p['minutes'] > 0:
            print(f"{p['name']:<25} | {p['minutes']:<5} | {p['power']}")

    with open('tactics_preds/opponent_roster.json', 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=4)
    print(f"\n💾 Дані збережено!")
