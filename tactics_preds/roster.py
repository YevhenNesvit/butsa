import pandas as pd
import json
import os

# ==========================================
# 1. ВХІДНІ ДАНІ
# ==========================================
CONTEXT = {
    'tournament_cap': 1800,   
    'is_opponent_home': True, 
    'match_type': 'club'      
}

ROSTER_FILE = 'opponent_roster.json'

MY_TEAM = {
    'def': 464, 'mid': 658, 'att': 526, 'stamina': 100 
}

if not os.path.exists(ROSTER_FILE):
    print(f"❌ Файл '{ROSTER_FILE}' не знайдено!")
    exit()

with open(ROSTER_FILE, 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

# Чистка дублікатів у самому файлі (на всяк випадок)
roster_data = []
seen = set()
for p in raw_data:
    if p['name'] not in seen:
        roster_data.append(p)
        seen.add(p['name'])

formations = {
    '3-4-3': {'def': 3, 'mid': 4, 'att': 3},
    '3-5-2': {'def': 3, 'mid': 5, 'att': 2},
    '4-4-2': {'def': 4, 'mid': 4, 'att': 2},
    '4-3-3': {'def': 4, 'mid': 3, 'att': 3},
    '4-5-1': {'def': 4, 'mid': 5, 'att': 1},
    '5-3-2': {'def': 5, 'mid': 3, 'att': 2},
    '5-4-1': {'def': 5, 'mid': 4, 'att': 1}
}

# ==========================================
# 2. АЛГОРИТМ ЗАМІН (ВИПРАВЛЕНИЙ)
# ==========================================
def get_valid_pos_list(line_name):
    if line_name == 'gk': return ['GK']
    if line_name == 'def': return ['CD', 'LD', 'RD', 'SW']
    if line_name == 'mid': return ['CM', 'RM', 'LM', 'DM', 'AM']
    if line_name == 'att': return ['CF', 'LF', 'RF', 'LW', 'RW']
    return []

def solve_cap_puzzle(roster, formation, cap):
    """
    Алгоритм послідовного заповнення (без дублікатів).
    """
    # 1. Структури
    starters = {'gk': [], 'def': [], 'mid': [], 'att': []}
    used_names = set()

    # Сортуємо весь ростер за силою
    sorted_roster = sorted(roster, key=lambda x: x['power'], reverse=True)

    # 2. Послідовне заповнення ліній
    # Пріоритет: GK -> DEF -> MID -> ATT
    order_of_fill = [
        ('gk', 1),
        ('def', formation['def']),
        ('mid', formation['mid']),
        ('att', formation['att'])
    ]

    for line_name, needed_count in order_of_fill:
        count = 0
        valid_positions = get_valid_pos_list(line_name)
        
        for p in sorted_roster:
            if count >= needed_count: break
            
            # --- ВИПРАВЛЕННЯ: Пропускаємо, якщо вже взяли ---
            if p['name'] in used_names: continue 
            
            if any(pos in p['pos'] for pos in valid_positions):
                starters[line_name].append(p)
                used_names.add(p['name'])
                count += 1

    # 3. Формуємо лавку (тільки ті, хто вільний)
    bench = [p for p in sorted_roster if p['name'] not in used_names]

    def calc_total():
        return sum(p['power'] for line in starters.values() for p in line)

    current_total = calc_total()

    # 4. Оптимізація (Заміни під ліміт)
    loop_limit = 0
    while current_total > cap and loop_limit < 200:
        best_swap = None
        min_loss = 9999
        
        for line_name in ['gk', 'def', 'mid', 'att']:
            line_starters = starters[line_name]
            valid_pos = get_valid_pos_list(line_name)
            
            # Шукаємо кандидата на лавці
            line_bench_candidates = [b for b in bench if any(vp in b['pos'] for vp in valid_pos)]
            
            for i, starter in enumerate(line_starters):
                for sub in line_bench_candidates:
                    diff = starter['power'] - sub['power']
                    # Шукаємо заміну, що зменшує силу (diff > 0)
                    if diff > 0 and diff < min_loss:
                        min_loss = diff
                        best_swap = (line_name, i, starter, sub)
        
        if best_swap:
            line_name, idx, out_p, in_p = best_swap
            
            # Заміна
            starters[line_name][idx] = in_p
            
            # Оновлюємо списки
            used_names.remove(out_p['name'])
            used_names.add(in_p['name'])
            
            bench.remove(in_p)
            bench.append(out_p)
            bench.sort(key=lambda x: x['power'], reverse=True)
            
            current_total = calc_total()
            loop_limit += 1
        else:
            break

    # Повертаємо і суми, і структуру складу для візуалізації
    full_squad_list = starters['gk'] + starters['def'] + starters['mid'] + starters['att']
    
    return {
        'total': current_total, 
        'def': sum(p['power'] for p in starters['def']), 
        'mid': sum(p['power'] for p in starters['mid']), 
        'att': sum(p['power'] for p in starters['att']),
        'squad_dict': starters, # <--- Словник для візуалізації
        'squad_list': full_squad_list
    }

def analyze_geometry(squad_list):
    wide_count = 0
    for p in squad_list:
        is_wide = False
        for pos in p['pos']:
            if pos in ['LD', 'RD', 'LM', 'RM', 'LW', 'RW']:
                is_wide = True; break
        if is_wide: wide_count += 1
    return wide_count

# ==========================================
# 4. РОЗРАХУНОК
# ==========================================
bonus_mult = 1.016 if (CONTEXT['is_opponent_home'] and CONTEXT['match_type'] == 'club') else 1.0
results = []

for form_name, form_struct in formations.items():
    res = solve_cap_puzzle(roster_data, form_struct, CONTEXT['tournament_cap'])
    w_count = analyze_geometry(res['squad_list'])
    
    results.append({
        'name': form_name, 
        'total': res['total'], 
        'wide_players': w_count,
        'm_def': res['def'] * bonus_mult, 
        'm_mid': res['mid'] * bonus_mult, 
        'm_att': res['att'] * bonus_mult,
        'squad_dict': res['squad_dict'], # Зберігаємо для виводу
        'squad_list': res['squad_list']
    })

results.sort(key=lambda x: x['total'], reverse=True)
best_opp = results[0] 

# ==========================================
# 5. ВІЗУАЛІЗАЦІЯ СКЛАДУ (ДОДАНО)
# ==========================================
print("\n" + "="*60)
print(f"🏆 ПРОГНОЗОВАНИЙ СКЛАД СУПЕРНИКА ({best_opp['name']})")
print(f"   Сума сили (Номінал): {best_opp['total']}")
print("-" * 60)

def print_line(label, players):
    names = [f"{p['name']} [{p['power']}]" for p in players]
    print(f"{label:<4} : {', '.join(names)}")

s = best_opp['squad_dict']
print_line("GK", s['gk'])
print_line("DEF", s['def'])
print_line("MID", s['mid'])
print_line("ATT", s['att'])

# Перевірка на унікальність
unique_players = set(p['name'] for p in best_opp['squad_list'])
if len(unique_players) == 11:
    print(f"\n✅ Перевірка пройдена: 11 унікальних гравців.")
else:
    print(f"\n⚠️ УВАГА: Знайдено дублікати! ({len(unique_players)} гравців)")
print("="*60)

# ==========================================
# 6. ГЕНЕРАЦІЯ РІШЕНЬ
# ==========================================
# 1. ТАКТИКА
my_tot = sum([MY_TEAM['def'], MY_TEAM['mid'], MY_TEAM['att']])
opp_tot = best_opp['m_def'] + best_opp['m_mid'] + best_opp['m_att']
power_ratio = my_tot / opp_tot

tactic_val = 50
if power_ratio > 1.05: tactic_val = 70
elif power_ratio < 0.95: tactic_val = 30
if CONTEXT['is_opponent_home']: tactic_val -= 10
else: tactic_val += 10
tactic_val = max(11, min(92, tactic_val))
tactic_desc = "Атака" if tactic_val >= 60 else "Захист" if tactic_val <= 40 else "Норма"

# 2. ПАСИ
mid_ratio = MY_TEAM['mid'] / best_opp['m_mid']
passing = "Змішані"; pass_reason = "Рівна гра"
if mid_ratio > 1.05: passing = "Короткі"; pass_reason = "Мід він"
elif mid_ratio < 0.95: passing = "Дальні"; pass_reason = "Мід луз"
if tactic_val < 41 and passing == "Короткі": passing = "Змішані"; pass_reason += " (Safety)"

# 3. СТРАТЕГІЯ
att_ratio = MY_TEAM['att'] / best_opp['m_def']
strategy = "Нормальна"; strat_reason = "Баланс"
if mid_ratio < 0.95: strategy = "Дальні удари"; strat_reason = "Мало м'яча"
elif att_ratio > 1.10: strategy = "Технічна гра"; strat_reason = "Слабкий захист"
elif mid_ratio > 1.05 and passing == "Короткі": strategy = "Гра в пас"; strat_reason = "Контроль"

# 4. ЩІЛЬНІСТЬ
dens_in = 50; w_reason = "База"
if best_opp['wide_players'] >= 2: dens_in -= 20; w_reason = "Широкий суперник"
else: dens_in += 20; w_reason = "Вузький суперник"
strikers = len(s['att'])
if strikers >= 3: dens_in += 29; w_reason += ", 3 Форварди!"
elif strikers == 1: dens_in -= 11
dens_in = max(11, min(92, dens_in))

# 5. ГЛИБИНА
dens_btwn = 50; d_reason = "База"
if mid_ratio < 0.95: dens_btwn -= 15; d_reason = "Сідаємо"
elif mid_ratio > 1.05: dens_btwn += 15; d_reason = "Піднімаємось"
if tactic_val < 41: dens_btwn = min(dens_btwn, 35)
dens_btwn = max(11, min(92, dens_btwn))

# 6. ПРЕСИНГ
press = "ВИКЛ"; press_reason = "Економія"
if MY_TEAM['stamina'] < 92: press = "ВИКЛ"; press_reason = "Мало сил"
elif tactic_val >= 65: press = "ВКЛ"; press_reason = "Агресія"
elif not CONTEXT['is_opponent_home'] and power_ratio > 1.1: press = "ВКЛ"

# ВИВІД ТАБЛИЦІ
print(f"📊 Сила: Ми {my_tot} vs Вони {opp_tot:.0f} (Ratio {power_ratio:.2f})")
print(f"🔸 Центр: Ми {MY_TEAM['mid']} vs Вони {best_opp['m_mid']:.0f} (Ratio {mid_ratio:.2f})")
print("-" * 60)
print(f"{'1. СТРАТЕГІЯ':<25} | [{strategy.upper()}] ({strat_reason})")
print(f"{'2. ПАСИ':<25} | [{passing.upper()}] ({pass_reason})")
print(f"{'3. ТАКТИКА':<25} | [{tactic_val:.0f}] ({tactic_desc})")
print(f"{'4. ЩІЛ. В ЛІНІЇ':<25} | [{dens_in:.0f}] ({w_reason})")
print(f"{'5. ЩІЛ. МІЖ ЛІН':<25} | [{dens_btwn:.0f}] ({d_reason})")
print(f"{'6. ПРЕСИНГ':<25} | [{press}] ({press_reason})")
print("="*60)
