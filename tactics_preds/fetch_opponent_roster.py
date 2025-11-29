import requests
from bs4 import BeautifulSoup
import json
import re

# ==============================================================================
# 1. НАЛАШТУВАННЯ (ВВЕДИ СВОЇ ДАНІ ТУТ)
# ==============================================================================

# Посилання на сторінку "Ростер" команди суперника (або своєї)
TARGET_URL = "https://butsa.pro/roster/8650/" 

# Твій "Ключ" від гри (PHPSESSID). Без нього скрипт не побачить таблицю!
# Встав сюди те, що скопіював з браузера (Value)
MY_COOKIE = "pkusg39o9c441h8llq92juu418"  # <-- Встав свій код сюди між лапками

# ==============================================================================
# 2. СКРИПТ
# ==============================================================================
def scrape_roster_clean(url, cookie_value):
    print(f"🕵️  Підключаємося до: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': f'PHPSESSID={cookie_value}'
    }

    try:
        response = requests.get(url, headers=headers)
        
        # --- ВИПРАВЛЕННЯ 1: Правильне кодування (UTF-8) ---
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            print(f"❌ Помилка з'єднання: код {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        players = []
        rows = soup.find_all('tr')
        
        print(f"✅ Сторінку завантажено. Фільтруємо гравців...")

        for row in rows:
            cols = row.find_all('td')
            
            # --- ВИПРАВЛЕННЯ 2: Жорсткий фільтр таблиці ---
            # Рядок гравця має багато колонок (вік, сила, позиція, ціна...). 
            # У меню їх зазвичай 1-3.
            if len(cols) < 10: continue
            
            # Шукаємо посилання на гравця
            link = cols[1].find('a')
            if not link: continue
            
            href = link.get('href', '')
            
            # --- ВИПРАВЛЕННЯ 3: Regex фільтр ---
            # Беремо тільки посилання виду /players/123456
            # Це відсіює "?act=...", "sort=..." і меню
            if not re.search(r'/players/\d+$', href):
                continue

            try:
                # 1. ІМ'Я
                name = link.get_text(strip=True)
                
                # 2. ПОЗИЦІЯ (Колонка 3 -> індекс 3)
                # Шукаємо текст типу "Gk", "Cd/Ld"
                pos_text = cols[3].get_text(strip=True)
                
                # Додаткова перевірка, чи це дійсно позиція
                valid_positions = ['GK', 'CD', 'LD', 'RD', 'DM', 'CM', 'LM', 'RM', 'AM', 'CF', 'LW', 'RW', 'SW']
                clean_pos = [p.strip().upper() for p in pos_text.split('/')]
                
                # Якщо хоч одна позиція невалідна - це якесь сміття
                if not any(p in valid_positions for p in clean_pos):
                    continue

                # 3. СИЛА (Колонка 5 -> індекс 5)
                power_text = cols[5].get_text(strip=True)
                # Витягуємо тільки цифри
                power_digits = re.sub(r'\D', '', power_text)
                
                if not power_digits: continue
                power_val = int(power_digits)

                # Фільтр адекватності сили (від 10 до 300)
                if not (10 < power_val < 300): continue

                # Додаємо у список
                players.append({
                    "name": name,
                    "pos": clean_pos,
                    "power": power_val
                })

            except Exception:
                continue

        return players

    except Exception as e:
        print(f"❌ Помилка: {e}")
        return []

# ==============================================================================
# 3. ЗАПУСК
# ==============================================================================

roster_data = scrape_roster_clean(TARGET_URL, MY_COOKIE)

if roster_data:
    print(f"\n🎉 Знайдено гравців: {len(roster_data)}")
    
    # Перевірка перших 3
    for p in roster_data[:3]:
        print(f"   {p['name']} | {p['pos']} | {p['power']}")

    # Збереження
    with open('tactics_preds/opponent_roster.json', 'w', encoding='utf-8') as f:
        json.dump(roster_data, f, ensure_ascii=False, indent=4)
    print(f"\n💾 Дані збережено у 'opponent_roster.json' (Нормальна кирилиця!)")
else:
    print("\n⚠️ Гравців не знайдено.")
