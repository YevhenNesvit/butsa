import bisect
import csv
import itertools
import os

# --- БОНУСИ ГРАВЦІВ ---
# Бонус гравця підсилює лише його власне уміння: +2% за рівень (рівень 5 → +10%)
BONUS_PER_LEVEL = 0.02
SKILL_BONUS = {'Пас': 'Пл', 'Дриблинг': 'Тх', 'Прием мяча': 'Пр', 'Отбор': 'Пд'}

# --- КОНСТАНТИ СХЕМ ---
ALL_FORMATIONS = {
    '1-6-3': {'def': 1, 'mid': 6, 'att': 3},
    '1-7-2': {'def': 1, 'mid': 7, 'att': 2},
    '2-5-3': {'def': 2, 'mid': 5, 'att': 3},
    '2-6-2': {'def': 2, 'mid': 6, 'att': 2},
    '2-7-1': {'def': 2, 'mid': 7, 'att': 1},
    '3-3-4': {'def': 3, 'mid': 3, 'att': 4},
    '3-4-3': {'def': 3, 'mid': 4, 'att': 3},
    '3-5-2': {'def': 3, 'mid': 5, 'att': 2},
    '3-6-1': {'def': 3, 'mid': 6, 'att': 1},
    '3-7-0': {'def': 3, 'mid': 7, 'att': 0},
    '4-3-3': {'def': 4, 'mid': 3, 'att': 3},
    '4-4-2': {'def': 4, 'mid': 4, 'att': 2},
    '4-5-1': {'def': 4, 'mid': 5, 'att': 1},
    '5-3-2': {'def': 5, 'mid': 3, 'att': 2},
    '5-4-1': {'def': 5, 'mid': 4, 'att': 1}
}

# --- ПАДІННЯ ФІЗГОТОВНОСТІ ЗА МАТЧ (help.butsa.ru, сторінка "Падение физготовности") ---
# Відсотки падіння після повного офіційного матчу без замін. Таблиця лежить у data/fatigue_drop.csv:
# рядки: витривалість 1..29 (разом з бонусом Ат), стовпці: вік 16..36.
FATIGUE_TABLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'fatigue_drop.csv')

def _load_fatigue_table(path=FATIGUE_TABLE_PATH):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        ages = [int(a) for a in next(reader)[1:]]
        rows = {int(r[0]): [float(v) for v in r[1:]] for r in reader if r}
    if ages != list(range(16, 37)) or sorted(rows) != list(range(1, 30)) or any(len(v) != len(ages) for v in rows.values()):
        raise ValueError(f"{path}: очікується вік 16..36 у заголовку та рядки витривалості 1..29")
    return rows

_FATIGUE_ROWS = _load_fatigue_table()

DEFAULT_AGE = 25  # якщо вік гравця невідомий (ростер завантажено без колонки "Воз")

def match_fatigue_drop(endurance, age):
    """Падіння фізготовності (%) за повний офіційний матч за таблицею вікі.
    Білінійна інтерполяція між рядками витривалості й віком, значення за межами обрізаються."""
    e = min(29.0, max(1.0, endurance))
    a = min(36.0, max(16.0, age))
    e0, a0 = int(e), int(a)
    e1, a1 = min(29, e0 + 1), min(36, a0 + 1)
    e_frac, a_frac = e - e0, a - a0

    def at_endurance(row):
        lo, hi = _FATIGUE_ROWS[row][a0 - 16], _FATIGUE_ROWS[row][a1 - 16]
        return lo + (hi - lo) * a_frac

    low = at_endurance(e0)
    return low + (at_endurance(e1) - low) * e_frac

def calculate_nominal_power(player, is_home=False):
    return player['power']

def morale_coef(player, is_home):
    cur_mor = player.get('morale', 13) + (4 if is_home else 0)
    return 1.0 + (cur_mor - 13) * 0.004

def calculate_real_power(player, is_home):
    stam_coef = player.get('stamina', 100) / 100.0
    return player['power'] * stam_coef * morale_coef(player, is_home)

def calculate_line_power(players_list):
    if not players_list: return 0
    return sum(p['real_power'] for p in players_list)

def get_valid_pos_list(line_name):
    if line_name == 'gk': return ['GK']
    if line_name == 'def': return ['CD', 'LD', 'RD', 'SW', 'LWD', 'RWD']
    if line_name == 'mid': return ['CM', 'RM', 'LM', 'DM', 'AM']
    if line_name == 'att': return ['CF', 'LF', 'RF', 'LW', 'RW']
    return []

def solve_cap_puzzle(roster, formation, cap):
    """
    Підбирає склад (здорових) з пріоритетом на хвилини і силу.
    Проводить послідовну оптимізацію (Downgrade -> Upgrade).
    """
    starters = {'gk': [], 'def': [], 'mid': [], 'att': []}
    used_names = set()
    
    healthy_roster = [p for p in roster if not p.get('is_injured', False)]
    # Сортуємо: Хвилини -> Сила
    sorted_roster = sorted(healthy_roster, key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)

    order = [('gk', 1), ('def', formation['def']), ('mid', formation['mid']), ('att', formation['att'])]
    
    # 1. Draft (Первинний набір)
    for line, count in order:
        c = 0
        valid = get_valid_pos_list(line)
        for p in sorted_roster:
            if c >= count: break
            if p['name'] in used_names: continue
            if any(pos in p['pos'] for pos in valid):
                starters[line].append(p)
                used_names.add(p['name'])
                c += 1

    bench = [p for p in sorted_roster if p['name'] not in used_names]

    # 2. Rebalancing (Закриття дірок)
    for target_line in ['mid', 'def', 'att']: 
        needed = formation[target_line]
        while len(starters[target_line]) < needed:
            moved_someone = False
            for donor_line in ['def', 'mid', 'att']:
                if donor_line == target_line: continue
                if not starters[donor_line]: continue 
                
                valid_target = get_valid_pos_list(target_line)
                valid_donor = get_valid_pos_list(donor_line)
                
                for i, candidate in enumerate(starters[donor_line]):
                    if any(pos in candidate['pos'] for pos in valid_target):
                        replacement = None
                        for b in bench:
                            if any(pos in b['pos'] for pos in valid_donor):
                                replacement = b
                                break
                        if replacement:
                            starters[target_line].append(candidate)
                            starters[donor_line].pop(i)
                            starters[donor_line].append(replacement)
                            used_names.add(replacement['name'])
                            bench.remove(replacement)
                            moved_someone = True
                            break 
                if moved_someone: break 
            if not moved_someone: break 

    bench = [p for p in sorted_roster if p['name'] not in used_names]
    bench.sort(key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)

    # Номінал тепер із сотими: округляємо суму, щоб похибка float не змінювала порівняння з лімітом
    def calc_nom_total(sq): return round(sum(p['nominal_power'] for l in sq.values() for p in l), 2)
    def calc_real_total(sq): return sum(p['real_power'] for l in sq.values() for p in l)

    curr_nom = calc_nom_total(starters)
    
    # 3. Optimization (Cap)
    # Downgrade if > Cap
    if curr_nom > cap:
        limit_loops = 0
        while curr_nom > cap and limit_loops < 220:
            best_swap = None
            min_real_loss = 9999
            for line in ['gk', 'def', 'mid', 'att']:
                valid = get_valid_pos_list(line)
                line_bench = [b for b in bench if any(vp in b['pos'] for vp in valid)]
                for i, start_p in enumerate(starters[line]):
                    for sub_p in line_bench:
                        if start_p['nominal_power'] > sub_p['nominal_power']:
                            real_loss = start_p['real_power'] - sub_p['real_power']
                            if real_loss < min_real_loss:
                                min_real_loss = real_loss
                                best_swap = (line, i, start_p, sub_p)
            if best_swap:
                l, idx, out_p, in_p = best_swap
                starters[l][idx] = in_p
                used_names.remove(out_p['name']); used_names.add(in_p['name'])
                bench.remove(in_p); bench.append(out_p)
                bench.sort(key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)
                curr_nom = calc_nom_total(starters)
                limit_loops += 1
            else: break

    # Upgrade if < Cap
    curr_nom = calc_nom_total(starters)
    if curr_nom < cap:
        limit_loops = 0
        while limit_loops < 220:
            best_swap = None
            max_real_gain = 0.01 
            for line in ['gk', 'def', 'mid', 'att']:
                valid = get_valid_pos_list(line)
                line_bench = sorted([b for b in bench if any(vp in b['pos'] for vp in valid)], 
                                  key=lambda x: x['real_power'], reverse=True)
                for i, start_p in enumerate(starters[line]):
                    for sub_p in line_bench:
                        diff_nom = sub_p['nominal_power'] - start_p['nominal_power']
                        if round(curr_nom + diff_nom, 2) <= cap:
                            real_gain = sub_p['real_power'] - start_p['real_power']
                            if real_gain > max_real_gain:
                                max_real_gain = real_gain
                                best_swap = (line, i, start_p, sub_p)
            if best_swap:
                l, idx, out_p, in_p = best_swap
                starters[l][idx] = in_p
                used_names.remove(out_p['name']); used_names.add(in_p['name'])
                bench.remove(in_p); bench.append(out_p)
                bench.sort(key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)
                curr_nom = calc_nom_total(starters)
                limit_loops += 1
            else: break

    flat_list = starters['gk'] + starters['def'] + starters['mid'] + starters['att']
    return {
        'nominal': curr_nom,
        'real_total': calc_real_total(starters),
        'squad_dict': starters,
        'squad_list': flat_list,
        'def': sum(p['real_power'] for p in starters['def']),
        'mid': sum(p['real_power'] for p in starters['mid']),
        'att': sum(p['real_power'] for p in starters['att'])
    }

# [НОВЕ] Аналіз бонусів
def analyze_bonuses(squad_dict):
    """Рахує сумарні рівні бонусів по лініях"""
    stats = {
        'playmaker_mid': 0, # Пл у півзахисті
        'technique_att': 0, # Тх у нападі
        'crossing_wing': 0, # Нв на флангах (Def/Mid/Att)
        'heading_att': 0,   # Гл у форвардів
        'athleticism_total': 0,  # [НОВИЙ БОНУС] Ат (Атлетизм)
        'interception_total': 0, # [НОВИЙ БОНУС] Пр (Перехват)
        'tackle_total': 0,       # [НОВИЙ БОНУС] От (Отбор)
    }
    
    # 1. Плеймейкери (MID)
    for p in squad_dict['mid']:
        stats['playmaker_mid'] += p.get('bonuses', {}).get('Пл', 0)
        
    # 2. Техніка (ATT)
    for p in squad_dict['att']:
        stats['technique_att'] += p.get('bonuses', {}).get('Тх', 0)
        
    # 3. Навіси (флангові гравці)
    wing_positions = ['LD', 'RD', 'LWD', 'RWD', 'LM', 'RM', 'LW', 'RW']
    all_field = squad_dict['def'] + squad_dict['mid'] + squad_dict['att']
    for p in all_field:
        stats['athleticism_total'] += p.get('bonuses', {}).get('Ат', 0)  # [НОВИЙ БОНУС]
        stats['interception_total'] += p.get('bonuses', {}).get('Пр', 0) # [НОВИЙ БОНУС]
        stats['tackle_total'] += p.get('bonuses', {}).get('Пд', 0)

        # Якщо гравець на фланзі (має позицію в списку)
        if any(pos in p['pos'] for pos in wing_positions):
             stats['crossing_wing'] += p.get('bonuses', {}).get('Нв', 0)

    # 4. Голова (CF/ST)
    for p in squad_dict['att']:
        if 'CF' in p['pos']:
            stats['heading_att'] += p.get('bonuses', {}).get('Гл', 0)
            
    return stats

def analyze_skills(squad_dict, is_home=False):
    """Рахує значення умінь для ліній."""
    # [ЗМІНЕНО] Замінили середні скіли (mid_pass тощо) на сумарні + додали Прийом
    stats = {
        'team_pass': 0, 
        'team_reception': 0,      # [ДОДАНО] Прийом м'яча
        'team_tackle': 0,
        'team_dribble': 0, 
        'expected_shot_power': 0, # [ЗМІНЕНО] Замість att_shot_power
        'expected_shot_acc': 0,   # [ЗМІНЕНО] Замість att_shot_acc
        'team_stamina': 0, 
        'gk_skill': 0
    }

    # [ДОДАНО] Об'єднуємо всіх польових гравців для Тотального футболу
    all_players = squad_dict['gk'] + squad_dict['def'] + squad_dict['mid'] + squad_dict['att']

    def get_mor_coef(p):
        return morale_coef(p, is_home)

    # [ЗМІНЕНО] Тепер рахуємо суму замість середнього (avg_skill -> sum_skill)
    # Бонус гравця (SKILL_BONUS) множить лише уміння цього гравця: +BONUS_PER_LEVEL за рівень
    def sum_skill(players, skill_names):
        total = 0
        for p in players:
            coef = get_mor_coef(p)
            for sn in skill_names:
                bonus_code = SKILL_BONUS.get(sn)
                level = p.get('bonuses', {}).get(bonus_code, 0) if bonus_code else 0
                total += p.get('skills', {}).get(sn, 0) * coef * (1 + BONUS_PER_LEVEL * level)
        return total

    # [ЗМІНЕНО] Рахуємо скіли для ВСІЄЇ команди, а не окремих ліній
    stats['team_pass'] = sum_skill(all_players, ['Пас'])                 # з бонусом Пл
    stats['team_reception'] = sum_skill(all_players, ['Прием мяча'])     # з бонусом Пр
    stats['team_dribble'] = sum_skill(all_players, ['Дриблинг'])         # з бонусом Тх
    stats['team_tackle'] = sum_skill(all_players, ['Отбор', 'Опека'])    # Відбір з бонусом Пд, Опіка без бонусу
    
    stats['team_stamina'] = sum_skill(all_players, ['Выносливость']) / len(all_players) if all_players else 0

    # Падіння фізи за матч для кожного гравця за таблицею вікі (витривалість + рівні Ат, вік),
    # далі середнє по команді. Кожен рівень Ат додає 1 до витривалості в матчі.
    drops, endurances = [], []
    for line in ('gk', 'def', 'mid', 'att'):
        for p in squad_dict[line]:
            if line == 'gk':
                # У воротарів немає умінь, умовна витривалість приблизно мастерство/8 + 2
                base_endurance = p.get('power', 0) / 8.0 + 2
            else:
                base_endurance = p.get('skills', {}).get('Выносливость', 0) * get_mor_coef(p)
            endurance = base_endurance + p.get('bonuses', {}).get('Ат', 0)
            drops.append(match_fatigue_drop(endurance, p.get('age') or DEFAULT_AGE))
            endurances.append(endurance)
    stats['fatigue_drop'] = sum(drops) / len(drops) if drops else None
    stats['team_stamina_eff'] = sum(endurances) / len(endurances) if endurances else 0

    # Штрафні: виконавець це гравець з найвищим бонусом Шт серед усіх 11 (воротар теж може бити),
    # а проти штрафних суперника діє Шт воротаря
    stats['fk_taker'] = max((p.get('bonuses', {}).get('Шт', 0) for p in all_players), default=0)
    stats['gk_fk'] = max((p.get('bonuses', {}).get('Шт', 0) for p in squad_dict['gk']), default=0)

    if squad_dict['gk']: 
        gk_p = squad_dict['gk'][0]
        stats['gk_skill'] = gk_p.get('skills', {}).get('Голкиперство', 0) * get_mor_coef(gk_p)

    # [ДОДАНО] Зважений середній удар (Weighted Average)
    total_weight = 0
    total_power = 0
    total_acc = 0

    # Нападники б'ють частіше (вага 3), півзахисники (вага 2), захисники (вага 1)
    for line, weight in [('def', 1), ('mid', 2), ('att', 3)]:
        for p in squad_dict[line]:
            coef = get_mor_coef(p)
            total_power += p.get('skills', {}).get('Сила удара', 0) * weight * coef
            total_acc += p.get('skills', {}).get('Точность удара', 0) * weight * coef
            total_weight += weight

    if total_weight > 0:
        stats['expected_shot_power'] = total_power / total_weight
        stats['expected_shot_acc'] = total_acc / total_weight
        
    return stats

def prepare_engine_stats(my_team, opp_stats, is_my_home=False, is_opp_home=False):
    """Формує ЕФЕКТИВНІ показники команд з урахуванням бонусів ТА стадіону"""
    opp_b = analyze_bonuses(opp_stats['squad_dict'])
    opp_s = analyze_skills(opp_stats['squad_dict'], is_home=is_opp_home) 
    
    my_b = analyze_bonuses(my_team['squad_dict']) if 'squad_dict' in my_team else {'playmaker_mid': 0, 'technique_att': 0, 'crossing_wing': 0, 'heading_att': 0, 'athleticism_total': 0, 'interception_total': 0, 'tackle_total': 0}
    my_s = analyze_skills(my_team['squad_dict'], is_home=is_my_home) if 'squad_dict' in my_team else {'team_pass': 0, 'team_reception': 0, 'team_tackle': 0, 'team_dribble': 0, 'expected_shot_power': 0, 'expected_shot_acc': 0, 'team_stamina': 0, 'gk_skill': 0}

    def calc_eff(base_stats, bonuses):
        # Бонуси Пл, Тх, Пр, Пд вже враховано в умінях кожного гравця (analyze_skills)
        rec_eff = base_stats['team_reception']
        return {
            'possession': base_stats['team_pass'] + rec_eff,
            'technique': base_stats['team_dribble'] + rec_eff,
            'tackle_eff': base_stats['team_tackle'],
            # Ат вже враховано в team_stamina_eff (+1 до витривалості за рівень); стара формула
            # лишається лише для статистики без складу
            'stamina_eff': base_stats.get('team_stamina_eff', base_stats['team_stamina'] * (1 + (bonuses['athleticism_total'] * 0.02))),
            'fatigue_drop': base_stats.get('fatigue_drop'),
            'fk_taker': base_stats.get('fk_taker', 0),
            'gk_fk': base_stats.get('gk_fk', 0),
            'shot_power': base_stats['expected_shot_power'],
            'shot_acc': base_stats['expected_shot_acc'],
            'gk_skill': base_stats['gk_skill']
        }
    return calc_eff(my_s, my_b), calc_eff(opp_s, opp_b), my_b, opp_b

def calculate_strength_diff(my_team, opp_stats):
    """Різниця реальної сили: ваші лінії (захист + півзахист + напад) мінус реальна сила складу суперника"""
    my_tot = my_team['def'] + my_team['mid'] + my_team['att']
    return my_tot - opp_stats['real_total']


# ==============================================================================
# ПІДБІР СКЛАДУ ПІД ЛІМІТ З ОБОВ'ЯЗКОВИМИ ГРАВЦЯМИ (для вашої команди)
# Ліміт це чиста сума номіналу (мастерства), тому ціль: набрати склад якомога
# ближче до ліміту, не перевищуючи його. За рівної суми кращий той, що має більше Real.
# ==============================================================================

def _line_options(player):
    """Лінії, де гравець може стояти за своїми позиціями"""
    return [line for line in ('gk', 'def', 'mid', 'att')
            if any(pos in player['pos'] for pos in get_valid_pos_list(line))]

def solve_my_lineup(roster, formation, cap, forced_names=(), excluded_names=()):
    """Точний підбір складу: усі forced_names обов'язково у складі, решта добирається так, щоб
    сума номіналу була найбільшою, але не більшою за cap. Повертає словник як solve_cap_puzzle
    або None, якщо такого складу не існує."""
    lines = ('gk', 'def', 'mid', 'att')
    need = {'gk': 1, 'def': formation['def'], 'mid': formation['mid'], 'att': formation['att']}
    pool = [p for p in roster if not p.get('is_injured', False) and p['name'] not in excluded_names]
    forced = [p for p in pool if p['name'] in forced_names]
    if len(forced) < len(set(forced_names)):
        return None  # хтось із обов'язкових недоступний (травма, виключений)
    forced_options = [_line_options(p) for p in forced]
    if any(not o for o in forced_options):
        return None  # позиція обов'язкового гравця не підходить жодній лінії
    forced_set = {p['name'] for p in forced}
    free = [p for p in pool if p['name'] not in forced_set]
    options = {p['name']: _line_options(p) for p in pool}

    def combos_of(cands, count):
        """Усі способи узяти count гравців: (номінал, реал, гравці, імена)"""
        return [(round(sum(p['nominal_power'] for p in c), 2), sum(p['real_power'] for p in c), list(c), frozenset(p['name'] for p in c))
                for c in itertools.combinations(cands, count)]

    best = None  # (номінал, реал, обов'язкові по лініях, gk, def, mid, att)
    # Обов'язковий гравець з кількома позиціями може стояти в різних лініях: перебираємо розміщення
    for assign in itertools.product(*forced_options):
        fixed = {l: [] for l in lines}
        for p, l in zip(forced, assign):
            fixed[l].append(p)
        if any(len(fixed[l]) > need[l] for l in lines):
            continue
        fixed_nom = round(sum(p['nominal_power'] for l in lines for p in fixed[l]), 2)
        if fixed_nom > cap + 1e-9:
            continue
        fixed_real = sum(p['real_power'] for l in lines for p in fixed[l])
        rem = {l: need[l] - len(fixed[l]) for l in lines}
        cands = {l: [p for p in free if l in options[p['name']]] for l in lines}
        if any(len(cands[l]) < rem[l] for l in lines):
            continue
        combos = {l: combos_of(cands[l], rem[l]) for l in lines}

        # Зустріч посередині: (воротар + захист) проти (півзахист + напад), без спільних гравців
        left = [(gn + dn, gr + dr, gc, dc, gnames | dnames)
                for gn, gr, gc, gnames in combos['gk'] for dn, dr, dc, dnames in combos['def'] if not (gnames & dnames)]
        right = [(mn + an, mr + ar, mc, ac, mnames | anames)
                 for mn, mr, mc, mnames in combos['mid'] for an, ar, ac, anames in combos['att'] if not (mnames & anames)]
        if not left or not right:
            continue
        right.sort(key=lambda x: x[0])
        right_noms = [x[0] for x in right]
        for l_nom, l_real, l_gk, l_def, l_names in left:
            limit = round(cap - fixed_nom - l_nom, 2)
            j = bisect.bisect_right(right_noms, limit + 1e-9) - 1
            found_nom = None
            while j >= 0:
                r_nom, r_real, r_mid, r_att, r_names = right[j]
                if found_nom is not None and r_nom < found_nom - 1e-9:
                    break  # нижче вже гірші за номіналом (за рівного номіналу перебираємо за Real)
                if not (l_names & r_names):
                    total = round(fixed_nom + l_nom + r_nom, 2)
                    real = fixed_real + l_real + r_real
                    if best is None or (total, real) > (best[0], best[1]):
                        best = (total, real, fixed, l_gk, l_def, r_mid, r_att)
                    found_nom = r_nom
                j -= 1
    if best is None:
        return None

    total, real, fixed, gk_extra, def_extra, mid_extra, att_extra = best
    squad = {
        'gk': fixed['gk'] + gk_extra,
        'def': fixed['def'] + def_extra,
        'mid': fixed['mid'] + mid_extra,
        'att': fixed['att'] + att_extra,
    }
    flat = squad['gk'] + squad['def'] + squad['mid'] + squad['att']
    return {
        'nominal': total,
        'real_total': sum(p['real_power'] for p in flat),
        'squad_dict': squad,
        'squad_list': flat,
        'def': sum(p['real_power'] for p in squad['def']),
        'mid': sum(p['real_power'] for p in squad['mid']),
        'att': sum(p['real_power'] for p in squad['att'])
    }


def _best_over_formations(roster, formations, cap, forced, excluded):
    """Найкращий склад серед схем: більший номіналом (ближче до ліміту), далі більший Real"""
    best = None
    for fname, fstruct in formations:
        res = solve_my_lineup(roster, fstruct, cap, forced, excluded)
        if res and (best is None or (res['nominal'], res['real_total']) > (best[1]['nominal'], best[1]['real_total'])):
            best = (fname, res)
    return best

def explain_forced_failure(roster, forced_names, cap, excluded_names=()):
    """Чому обов'язкових гравців не вдалося вмістити в склад"""
    by_name = {p['name']: p for p in roster}
    unavailable = [n for n in forced_names if n not in by_name or by_name[n].get('is_injured') or n in excluded_names]
    if unavailable:
        return "Недоступні (травма або виключені): " + ", ".join(unavailable) + "."
    total = round(sum(by_name[n]['nominal_power'] for n in forced_names), 2)
    if total > cap + 1e-9:
        return f"Сума номіналу обов'язкових гравців {total:.2f} перевищує ліміт {cap}."
    return ("Обов'язкові гравці разом не вміщуються в жодну схему під ліміт: або склад із ними перевищує ліміт, "
            "або їхні позиції не лягають у схему чи не вистачає гравців на лінії.")

def propose_my_lineup(roster, formation_name, cap, forced_names=(), excluded_names=(), max_variants=60):
    """Склад вашої команди під ліміт з обов'язковими гравцями. formation_name це схема з ALL_FORMATIONS
    або будь-що інше для автоматичного вибору найкращої. Якщо вмістити всіх обов'язкових неможливо
    (перевищують ліміт, не лягають у схему), пропонує власний склад із найбільшою кількістю
    обов'язкових і розповідає, кого довелося прибрати і чому."""
    formations = ([(formation_name, ALL_FORMATIONS[formation_name])] if formation_name in ALL_FORMATIONS
                  else list(ALL_FORMATIONS.items()))
    forced = list(forced_names)
    full = _best_over_formations(roster, formations, cap, forced, excluded_names)
    if full:
        return {'formation': full[0], 'result': full[1], 'dropped': [], 'reason': ''}

    reason = explain_forced_failure(roster, forced, cap, excluded_names)
    by_name = {p['name']: p for p in roster}
    nominal = lambda names: sum(by_name[n]['nominal_power'] for n in names if n in by_name)
    for k in range(len(forced) - 1, -1, -1):
        # Дешеве відсіювання: сума номіналу обов'язкових не має перевищувати ліміт
        subsets = [s for s in itertools.combinations(forced, k) if nominal(s) <= cap + 1e-9]
        subsets.sort(key=nominal)
        best = None
        for subset in subsets[:max_variants]:
            cand = _best_over_formations(roster, formations, cap, list(subset), excluded_names)
            if cand and (best is None or (cand[1]['nominal'], cand[1]['real_total']) > (best[1]['nominal'], best[1]['real_total'])):
                best = (cand[0], cand[1], subset)
        if best:
            return {'formation': best[0], 'result': best[1], 'dropped': [n for n in forced if n not in best[2]], 'reason': reason}
    return {'formation': None, 'result': None, 'dropped': forced,
            'reason': reason + " Склад скласти неможливо: перевірте ліміт і кількість гравців на лініях."}
