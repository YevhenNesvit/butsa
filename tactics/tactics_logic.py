# --- КОНСТАНТИ СХЕМ ---
ALL_FORMATIONS = {
    '1-6-3': {'def': 1, 'mid': 6, 'att': 3},
    '2-5-3': {'def': 2, 'mid': 5, 'att': 3},
    '2-6-2': {'def': 2, 'mid': 6, 'att': 2},
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

def calculate_nominal_power(player, is_home=False):
    return player['power']

def calculate_real_power(player, is_home):
    base = player['power']
    stam_coef = player.get('stamina', 100) / 100.0
    mor = player.get('morale', 13)
    home_bonus = 4 if is_home else 0
    cur_mor = mor + home_bonus
    mor_coef = 1.0 + (cur_mor - 13) * 0.004
    return base * stam_coef * mor_coef

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

    def calc_nom_total(sq): return sum(p['nominal_power'] for l in sq.values() for p in l)
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
                        if (curr_nom + diff_nom) <= cap:
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

def analyze_threats(squad):
    c, w = 0, 0
    att_wide = 0
    for p in squad['att']:
        if 'CF' in p['pos']: c += 1
        elif any(x in p['pos'] for x in ['LW', 'RW', 'LF', 'RF']): att_wide += 1
    w += min(att_wide, 2)
    mid_wide = 0
    for p in squad['mid']:
        if any(x in p['pos'] for x in ['LM', 'RM']): mid_wide += 1
    w += min(mid_wide, 2)
    return c, w

# [НОВЕ] Аналіз бонусів
def analyze_bonuses(squad_dict):
    """Рахує сумарні рівні бонусів по лініях"""
    stats = {
        'playmaker_mid': 0, # Пл у півзахисті
        'technique_att': 0, # Тх у нападі
        'crossing_wing': 0, # Нв на флангах (Def/Mid/Att)
        'heading_att': 0,   # Гл у форвардів
        'speed_total': 0,    # Ск загальна
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
        stats['speed_total'] += p.get('bonuses', {}).get('Ск', 0)
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
        mor = p.get('morale', 13)
        home_bonus = 4 if is_home else 0
        cur_mor = mor + home_bonus
        return 1.0 + (cur_mor - 13) * 0.004

    # [ЗМІНЕНО] Тепер рахуємо суму замість середнього (avg_skill -> sum_skill)
    def sum_skill(players, skill_names):
        total = 0
        for p in players:
            coef = get_mor_coef(p)
            for sn in skill_names: 
                total += p.get('skills', {}).get(sn, 0) * coef
        return total

    # [ЗМІНЕНО] Рахуємо скіли для ВСІЄЇ команди, а не окремих ліній
    stats['team_pass'] = sum_skill(all_players, ['Пас'])
    stats['team_reception'] = sum_skill(all_players, ['Прием мяча']) # [ДОДАНО]
    stats['team_dribble'] = sum_skill(all_players, ['Дриблинг'])
    stats['team_tackle'] = sum_skill(all_players, ['Отбор', 'Опека']) # 2 скіли захисту
    
    stats['team_stamina'] = sum_skill(all_players, ['Выносливость']) / len(all_players) if all_players else 0
    
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
    
    my_b = analyze_bonuses(my_team['squad_dict']) if 'squad_dict' in my_team else {'playmaker_mid': 0, 'technique_att': 0, 'crossing_wing': 0, 'heading_att': 0, 'speed_total': 0, 'athleticism_total': 0, 'interception_total': 0, 'tackle_total': 0}
    my_s = analyze_skills(my_team['squad_dict'], is_home=is_my_home) if 'squad_dict' in my_team else {'team_pass': 0, 'team_reception': 0, 'team_tackle': 0, 'team_dribble': 0, 'expected_shot_power': 0, 'expected_shot_acc': 0, 'team_stamina': 0, 'gk_skill': 0}

    def calc_eff(base_stats, bonuses):
        rec_eff = base_stats['team_reception'] * (1 + (bonuses['interception_total'] * 0.02))
        return {
            'possession': base_stats['team_pass'] + rec_eff,
            'technique': base_stats['team_dribble'] + rec_eff,
            'tackle_eff': base_stats['team_tackle'] * (1 + (bonuses['tackle_total'] * 0.02)),
            'stamina_eff': base_stats['team_stamina'] * (1 + (bonuses['athleticism_total'] * 0.02)),
            'shot_power': base_stats['expected_shot_power'],
            'shot_acc': base_stats['expected_shot_acc'],
            'gk_skill': base_stats['gk_skill']
        }
    return calc_eff(my_s, my_b), calc_eff(opp_s, opp_b), my_b, opp_b

def get_tactical_advice(my_team, opp_stats, best_meta, is_opp_home):
    my_tot = my_team['def'] + my_team['mid'] + my_team['att']
    diff = my_tot - opp_stats['real_total']
    
    my_eng, opp_eng, my_b, opp_b = prepare_engine_stats(my_team, opp_stats, not is_opp_home, is_opp_home)

    mid_ratio = my_team['mid'] / opp_stats['mid'] if opp_stats['mid'] > 0 else 1.0
    opp_mid_adv = opp_stats['mid'] / my_team['mid'] if my_team['mid'] > 0 else 1.0
    opp_att_adv = opp_stats['att'] / my_team['def'] if my_team['def'] > 0 else 1.0
    
    cfs = best_meta['c']
    wings = min(best_meta['w'], 2)

    # ---------------------------------------------------------
    # 1. ТЕКСТОВИЙ АНАЛІЗ СУПЕРНИКА
    # ---------------------------------------------------------
    opp_guess_str = "Нормальна"
    opp_strat_clean = "Нормальна" 
    guess_details = []
    
    # 1. Аутсайдер (Якщо наша перевага > 47, суперник піде в глуху оборону)
    if diff > 47:
        guess_details.append("Underdog")
        opp_guess_str = "Дальні удари (Від оборони)"
        opp_strat_clean = "Дальні удари"

    # 2. Фланги (Дзеркально до нашого: Нв >= 2 і Гл >= 1)
    elif opp_b['crossing_wing'] >= 2 and opp_b['heading_att'] >= 1:
        guess_details.append(f"Нв{opp_b['crossing_wing']}+Гл{opp_b['heading_att']}")
        opp_guess_str = "Дальні удари (Фланги)"
        opp_strat_clean = "Дальні удари"

    # 3. Технічна гра (Бонуси Тх АБО Техніка б'є наш Захист)
    elif opp_b['technique_att'] >= 3 or (opp_eng['technique'] > my_eng['tackle_eff'] * 1.19 and opp_eng['technique'] > 0):
        if opp_b['technique_att'] >= 3: guess_details.append(f"Тх{opp_b['technique_att']}")
        else: guess_details.append(f"Дриблінг ({opp_eng['technique']:.0f})")
        opp_guess_str = "Технічна гра"
        opp_strat_clean = "Технічна гра"

    # 4. Гра в пас (Бонуси Пл АБО Володіння б'є наш Захист)
    elif opp_b['playmaker_mid'] >= 4 or (opp_eng['possession'] > my_eng['tackle_eff'] * 1.19 and opp_eng['possession'] > 0): 
        if opp_b['playmaker_mid'] >= 4: guess_details.append(f"Пл{opp_b['playmaker_mid']}")
        else: guess_details.append(f"Пас/Прийом ({opp_eng['possession']:.0f})")
        opp_guess_str = "Гра в пас (Володіння)"
        opp_strat_clean = "Гра в пас"

    # 5. Слабкий воротар (Якщо їхній Удар пробиває НАШОГО воротаря з запасом 13.7%)
    elif opp_eng['shot_power'] > my_eng['gk_skill'] * 1.137 and opp_eng['shot_acc'] > my_eng['gk_skill'] * 1.137:
        guess_details.append("Б'ють по нашому GK")
        opp_guess_str = "Дальні удари"
        opp_strat_clean = "Дальні удари"

    # ---------------------------------------------------------
    # 2. [НОВЕ] ГЕНЕРАЦІЯ ЦИФРОВОГО ПРОФІЛЮ СУПЕРНИКА
    # ---------------------------------------------------------
    opp_pass = "Змішані"
    if opp_strat_clean == "Гра в пас": opp_pass = "Короткі"
    elif opp_strat_clean == "Дальні удари": opp_pass = "Дальні"

    # Як вони налаштують повзунок Атаки/Захисту?
    # Якщо diff < 0 (ми слабші), суперник відчуває силу і буде атакувати
    opp_tactic_val = 47 + (diff * -0.11) 
    # Якщо суперник вдома, він грає агресивніше
    opp_tactic_val += 11 if is_opp_home else -11
    
    if cfs >= 3: opp_tactic_val = max(opp_tactic_val, 61) # 3 форварди = атака
    opp_tactic_val = max(11, min(91, opp_tactic_val))

    # Як вони розставлять щільність?
    opp_dens_in, opp_dens_btwn = 51, 51
    if opp_strat_clean == "Гра в пас":
        opp_dens_in, opp_dens_btwn = 71, 71
    elif opp_strat_clean == "Дальні удари":
        opp_dens_in, opp_dens_btwn = 51, 31
    elif opp_strat_clean == "Технічна гра":
        opp_dens_in, opp_dens_btwn = 31, 51

    opp_press = "НІ"
    if opp_eng['stamina_eff'] > my_eng['stamina_eff'] * 1.1 or opp_tactic_val > 60:
        opp_press = "ТАК"

    # ГОТОВИЙ ПРОФІЛЬ ДЛЯ СИМУЛЯТОРА
    opp_predicted_tactic = {
        'pass_type': opp_pass,
        'strat': opp_strat_clean,
        'press': opp_press,
        'tactic_val': int(opp_tactic_val),
        'dens_in': int(opp_dens_in),
        'dens_btwn': int(opp_dens_btwn)
    }

    return {
        'diff': diff,
        'opp_guess': f"{opp_guess_str} {guess_details}", 
        'opp_predicted_tactic': opp_predicted_tactic
    }
