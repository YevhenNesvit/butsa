import json
import os

# ==========================================
# 1. ВХІДНІ ДАНІ
# ==========================================
CONTEXT = {
    'tournament_cap': 800,   
    'is_opponent_home': True, # True = Суперник вдома (+4 моралі)
    'match_type': 'club'      
}

ROSTER_FILE = 'tactics_preds/opponent_roster.json'

# ТВОЯ КОМАНДА (Вкажи свої РЕАЛЬНІ сили, а не номінальні, якщо можеш)
MY_TEAM = {
    'def': 212, 'mid': 161, 'att': 358, 'stamina': 97
}

# --- ЗАВАНТАЖЕННЯ ---
if not os.path.exists(ROSTER_FILE):
    print(f"❌ Файл '{ROSTER_FILE}' не знайдено!")
    exit()

with open(ROSTER_FILE, 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

# Чистка дублікатів
roster_data = []
seen = set()
for p in raw_data:
    if p['name'] not in seen:
        roster_data.append(p)
        seen.add(p['name'])

formations = {
    '3-4-3': {'def': 3, 'mid': 4, 'att': 3},
    # '3-5-2': {'def': 3, 'mid': 5, 'att': 2},
    # '4-4-2': {'def': 4, 'mid': 4, 'att': 2},
    # '4-3-3': {'def': 4, 'mid': 3, 'att': 3},
    # '4-5-1': {'def': 4, 'mid': 5, 'att': 1},
    # '5-3-2': {'def': 5, 'mid': 3, 'att': 2},
    # '5-4-1': {'def': 5, 'mid': 4, 'att': 1}
}

# ==========================================
# 2. МАТЕМАТИКА REAL POWER
# ==========================================
def calculate_real_power(player, context):
    base_power = player['power']
    stamina = player.get('stamina', 100)
    morale = player.get('morale', 13) 
    stamina_mult = stamina / 100.0
    home_bonus = 4 if (context['is_opponent_home'] and context['match_type'] == 'club') else 0
    current_morale = morale + home_bonus
    morale_mult = 1.0 + (current_morale - 13) * 0.004
    return base_power * stamina_mult * morale_mult

for p in roster_data:
    p['real_power'] = calculate_real_power(p, CONTEXT)
    # Гарантуємо, що поле minutes існує
    if 'minutes' not in p: p['minutes'] = 0

# ==========================================
# 3. АЛГОРИТМ ЗАМІН (ПРІОРИТЕТ: ХВИЛИНИ)
# ==========================================
def get_valid_pos_list(line_name):
    if line_name == 'gk': return ['GK']
    if line_name == 'def': return ['CD', 'LD', 'RD', 'SW']
    if line_name == 'mid': return ['CM', 'RM', 'LM', 'DM', 'AM']
    if line_name == 'att': return ['CF', 'LF', 'RF', 'LW', 'RW']
    return []

def solve_cap_puzzle(roster, formation, cap):
    starters = {'gk': [], 'def': [], 'mid': [], 'att': []}
    used_names = set()

    # --- [ГОЛОВНА ЗМІНА] Сортування ---
    # 1. Minutes (Descending)
    # 2. Real Power (Descending) - як тай-брейкер
    sorted_roster = sorted(roster, key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)

    # 1. Формування основи (хто більше грає)
    order_of_fill = [('gk', 1), ('def', formation['def']), ('mid', formation['mid']), ('att', formation['att'])]
    
    for line_name, needed_count in order_of_fill:
        count = 0
        valid_positions = get_valid_pos_list(line_name)
        for p in sorted_roster:
            if count >= needed_count: break
            if p['name'] in used_names: continue 
            if any(pos in p['pos'] for pos in valid_positions):
                starters[line_name].append(p)
                used_names.add(p['name'])
                count += 1

    # 2. Формування лавки (теж сортуємо за хвилинами, щоб міняти на "найближчого" гравця основи)
    bench = [p for p in sorted_roster if p['name'] not in used_names]

    def calc_nominal_total(sq_dict):
        return sum(p['power'] for line in sq_dict.values() for p in line)
    def calc_real_total(sq_dict):
        return sum(p['real_power'] for line in sq_dict.values() for p in line)

    current_nominal = calc_nominal_total(starters)

    # 3. Оптимізація під ліміт
    # Якщо основа (ті, хто завжди грають) не влазить у ліміт, значить тренер когось ротує.
    # Ми шукаємо заміну, яка допоможе влізти в ліміт.
    loop_limit = 0
    while current_nominal > cap and loop_limit < 200:
        best_swap = None
        min_real_loss = 9999
        
        for line_name in ['gk', 'def', 'mid', 'att']:
            line_starters = starters[line_name]
            valid_pos = get_valid_pos_list(line_name)
            line_bench = [b for b in bench if any(vp in b['pos'] for vp in valid_pos)]
            
            for i, starter in enumerate(line_starters):
                for sub in line_bench:
                    nominal_diff = starter['power'] - sub['power']
                    
                    if nominal_diff > 0: # Заміна допомагає ліміту
                        # Тут ми все одно дивимось на Real Power, бо нам треба зберегти силу команди.
                        # Але оскільки 'starter' має більше хвилин, ми намагаємось його залишити,
                        # якщо є інший варіант.
                        # (В простій версії просто шукаємо min_real_loss)
                        real_diff = starter['real_power'] - sub['real_power']
                        
                        if real_diff < min_real_loss:
                            min_real_loss = real_diff
                            best_swap = (line_name, i, starter, sub)
        
        if best_swap:
            line, idx, out_p, in_p = best_swap
            starters[line][idx] = in_p
            
            used_names.remove(out_p['name']); used_names.add(in_p['name'])
            bench.remove(in_p); bench.append(out_p)
            
            # Лавку пересортовуємо, щоб наступним кандидатом був найкращий з решти
            bench.sort(key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)
            
            current_nominal = calc_nominal_total(starters)
            loop_limit += 1
        else: break

    full_squad_list = starters['gk'] + starters['def'] + starters['mid'] + starters['att']
    return {
        'nominal': current_nominal,
        'real_total': calc_real_total(starters),
        'def': sum(p['real_power'] for p in starters['def']), 
        'mid': sum(p['real_power'] for p in starters['mid']), 
        'att': sum(p['real_power'] for p in starters['att']),
        'squad_dict': starters, 'squad_list': full_squad_list
    }

# ==========================================
# 4. АНАЛІЗ ЗАГРОЗ (CF / Wingers)
# ==========================================
def analyze_threats(squad_dict):
    c_threat = 0 # CF
    w_threat = 0 # Winger
    
    # 1. Атака (Ліміт вінгерів = 2)
    att_wide_count = 0
    for p in squad_dict['att']:
        if 'CF' in p['pos']: c_threat += 1
        elif any(x in p['pos'] for x in ['LW', 'RW', 'LF', 'RF']): att_wide_count += 1
    w_threat += min(att_wide_count, 2) # Не більше 2 вінгерів

    # 2. Півзахист (Ліміт вінгерів = 2)
    mid_wide_count = 0
    for p in squad_dict['mid']:
        if any(x in p['pos'] for x in ['LM', 'RM']): mid_wide_count += 1
    w_threat += min(mid_wide_count, 2) # Не більше 2 вінгерів
            
    return c_threat, w_threat

# ==========================================
# 5. РОЗРАХУНОК (З урахуванням хвилин)
# ==========================================
results = []
print(f"\n⚙️  Аналіз (Minutes Priority). Ліміт: {CONTEXT['tournament_cap']}")

for fname, fstruct in formations.items():
    res = solve_cap_puzzle(roster_data, fstruct, CONTEXT['tournament_cap'])
    c, w = analyze_threats(res['squad_dict'])
    
    # Рахуємо "Імовірність схеми" за сумою хвилин гравців у старті
    total_minutes_on_pitch = sum(p['minutes'] for p in res['squad_list'])
    
    results.append({
        'name': fname, 'res': res, 'c': c, 'w': w, 
        'total_mins': total_minutes_on_pitch
    })

# Сортуємо: 
# 1. За сумарними хвилинами (схема, якою грають частіше)
# 2. За реальною силою
results.sort(key=lambda x: (x['total_mins'], x['res']['real_total']), reverse=True)
best_scenario = results[0]
best_opp = best_scenario['res']

# ==========================================
# 6. ВІЗУАЛІЗАЦІЯ
# ==========================================
print("\n" + "="*60)
print(f"🏆 ПРОГНОЗ: {best_scenario['name']}")
print(f"   Досвід складу (сума хвилин): {best_scenario['total_mins']}")
print(f"   Номінал: {best_opp['nominal']} / {CONTEXT['tournament_cap']}")
print(f"   REAL POWER: {best_opp['real_total']:.1f}")
print("-" * 60)

def print_line(label, players):
    # Додав вивід хвилин
    data = [f"{p['name']} [{p['minutes']}хв|{p['power']}]" for p in players]
    print(f"{label:<4}: {', '.join(data)}")

s = best_opp['squad_dict']
print_line("GK", s['gk'])
print_line("DEF", s['def'])
print_line("MID", s['mid'])
print_line("ATT", s['att'])
print("="*60)

# ==========================================
# 7. ТРЕНЕРСЬКІ РІШЕННЯ (SCALING FIX)
# ==========================================
my_tot = sum([MY_TEAM['def'], MY_TEAM['mid'], MY_TEAM['att']])
opp_tot = best_opp['real_total'] - best_opp['squad_dict']['gk'][0]['real_power']
power_diff = my_tot - opp_tot

# 1. ТАКТИКА (Плавна шкала)
# 0 різниці = 50. -100 різниці = 30.
base_tactic = 50 + (power_diff * 0.2)

if CONTEXT['is_opponent_home']: base_tactic -= 11
else: base_tactic += 11

# LOCK: Якщо 3 CF -> Не більше 50
cfs = best_scenario['c']
if cfs >= 3 and base_tactic > 50:
    base_tactic = 50
    t_desc = "Норма (Lock: 3 CF)"
else:
    t_desc = "Розрахункова"

tactic_val = max(11, min(92, base_tactic))
if tactic_val > 60: t_desc += " -> Атака"
elif tactic_val < 41: t_desc += " -> Захист"
else: t_desc += " -> Баланс"

# 2. ПАСИ
mid_ratio = MY_TEAM['mid'] / best_opp['mid']
passing = "Змішані"; p_reason = "Рівна гра"
if mid_ratio > 1.11: passing = "Короткі"; p_reason = "Виграємо центр"
elif mid_ratio < 0.92: passing = "Дальні"; p_reason = "Програємо центр"
# Safety: При захисті завжди граємо простіше
if tactic_val < 41 and passing == "Короткі": passing = "Змішані"; p_reason += " (Safety)"
# Underdog: Якщо ми значно слабші, тільки дальні
if power_diff < -50: passing = "Дальні"; p_reason = "Underdog (Виніс)"

# 3. СТРАТЕГІЯ
att_ratio = MY_TEAM['att'] / best_opp['def'] # Наш напад vs Їх захист
strat = "Нормальна"
s_reason = "Баланс"

if mid_ratio < 0.92: 
    strat = "Дальні удари"
    s_reason = "Без м'яча -> Б'ємо при нагоді"

elif att_ratio > 1.19: 
    strat = "Технічна гра"
    s_reason = "Слабкий захист ворога -> Дриблінг"

elif mid_ratio > 1.10 and passing == "Короткі": 
    # ТУТ БУЛА ПОМИЛКА: Ми радили "Гру в пас" тільки через перевагу в центрі.
    # АЛЕ якщо напад слабкий (як у вас 361), "Гра в пас" призведе до втрат.
    
    if att_ratio < 0.83: # Наш напад слабший за їх захист
        strat = "Дальні удари" 
        s_reason = "Центр наш, але Напад слабкий -> Б'ємо здалеку"
    else:
        strat = "Гра в пас"
        s_reason = "Контроль м'яча + Сильний напад"

# 4. ЩІЛЬНІСТЬ У ЛІНІЇ
dens_in = 50 
wings = best_scenario['w']
dens_in = 50 + (cfs * 20) - (wings * 15)
w_reason = f"{cfs} CF vs {wings} Wing"

if best_opp['att'] > MY_TEAM['def']:
    dens_in += 11; w_reason += " + Def Weakness"

if cfs >= 3: dens_in = max(dens_in, 65) 
dens_in = max(11, min(92, dens_in))

# --- 5. ЩІЛЬНІСТЬ МІЖ ЛІНІЯМИ (ВИПРАВЛЕНО) ---
dens_btwn = 50; d_reason = "База"

if mid_ratio < 0.95: 
    dens_btwn += 11; d_reason = "Програли центр -> Всі назад (Compact)"
elif mid_ratio > 1.05: 
    dens_btwn -= 11; d_reason = "Виграли центр -> Півзахист в атаку"

# ANTI-COUNTER (Якщо 3 CF -> Максимальна компактність)
if cfs >= 3:
    # Ми НЕ можемо лишати захисників самих. Кличемо всіх назад.
    dens_btwn = max(dens_btwn, 83) 
    d_reason = "3 CF -> Бетон (Всі назад до захисту!)"

# Якщо тактика захисна (Автобус) -> Тим паче всі назад
if tactic_val < 41: 
    dens_btwn = max(dens_btwn, 74)
    d_reason += " + Автобус (Compact Defense)"

dens_btwn = max(11, min(92, dens_btwn))

# 6. ПРЕСИНГ
press = "НІ"
# Вмикаємо пресинг, тільки якщо ми сильніші АБО якщо треба ламати гру (Underdog)
if MY_TEAM['stamina'] >= 95:
    if tactic_val > 60: press = "ТАК (Атака)"
    elif power_diff < -50: press = "ТАК (Underdog Chance)"

# ВИВІД
print(f"📊 БАЛАНС: Ми {my_tot} vs Вони {opp_tot:.0f} (Diff: {power_diff:.1f})")
print(f"🔸 ЦЕНТР: Ми {MY_TEAM['mid']} vs Вони {best_opp['mid']:.0f} (Ratio {mid_ratio:.2f})")
print("-" * 60)
print(f"{'1. СТРАТЕГІЯ':<20} | [{strat.upper()}] ({s_reason})")
print(f"{'2. ПАСИ':<20} | [{passing.upper()}] ({p_reason})")
print(f"{'3. ТАКТИКА':<20} | [{tactic_val:.0f}] ({t_desc})")
print(f"{'4. ЩІЛ. В ЛІНІЇ':<20} | [{dens_in:.0f}] ({w_reason})")
print(f"{'5. ЩІЛ. МІЖ ЛІН':<20} | [{dens_btwn:.0f}] ({d_reason})")
print(f"{'6. ПРЕСИНГ':<20} | [{press}]")
print("="*60)
