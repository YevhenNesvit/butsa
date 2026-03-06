import math

# --- КОНСТАНТИ СХЕМ ---
ALL_FORMATIONS = {
    '2-5-3': {'def': 2, 'mid': 5, 'att': 3},
    '2-6-2': {'def': 2, 'mid': 6, 'att': 2},
    '3-4-3': {'def': 3, 'mid': 4, 'att': 3},
    '3-5-2': {'def': 3, 'mid': 5, 'att': 2},
    '3-6-1': {'def': 3, 'mid': 6, 'att': 1},
    '3-7-0': {'def': 3, 'mid': 7, 'att': 0},
    '4-4-2': {'def': 4, 'mid': 4, 'att': 2},
    '4-3-3': {'def': 4, 'mid': 3, 'att': 3},
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
        'speed_total': 0    # Ск загальна
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
        # Якщо гравець на фланзі (має позицію в списку)
        if any(pos in p['pos'] for pos in wing_positions):
             stats['crossing_wing'] += p.get('bonuses', {}).get('Нв', 0)

    # 4. Голова (CF/ST)
    for p in squad_dict['att']:
        if 'CF' in p['pos']:
            stats['heading_att'] += p.get('bonuses', {}).get('Гл', 0)
            
    return stats

def get_tactical_advice(my_team, opp_stats, best_meta, is_opp_home):
    my_tot = my_team['def'] + my_team['mid'] + my_team['att']
    opp_field_pow = opp_stats['real_total']
    diff = my_tot - opp_field_pow

    mid_ratio = my_team['mid'] / opp_stats['mid'] if opp_stats['mid'] > 0 else 1.0
    opp_mid_adv = opp_stats['mid'] / my_team['mid'] if my_team['mid'] > 0 else 1.0
    opp_att_adv = opp_stats['att'] / my_team['def'] if my_team['def'] > 0 else 1.0
    
    cfs = best_meta['c']
    wings = best_meta['w']
    if wings > 2: wings = 2

    opp_b = analyze_bonuses(opp_stats['squad_dict'])

    my_b = {'playmaker_mid': 0, 'technique_att': 0, 'crossing_wing': 0, 'heading_att': 0, 'speed_total': 0}
    if 'squad_dict' in my_team:
        my_b = analyze_bonuses(my_team['squad_dict'])

    # 1. Прогноз Стратегії
    opp_guess = "Нормальна"
    guess_details = []
    
    # Фактори прогнозів
    if opp_b['playmaker_mid'] >= 3: 
        guess_details.append(f"Пл{opp_b['playmaker_mid']} (Пас)")
        opp_guess = "Гра в пас (Плеймейкери)"
    
    if opp_b['crossing_wing'] >= 3 and opp_b['heading_att'] >= 2:
        guess_details.append(f"Нв{opp_b['crossing_wing']}+Гл{opp_b['heading_att']} (Навіси)")
        # Якщо є явний перекос в навіси, це може бути Дальні удари/Фланги
        if opp_guess == "Нормальна": opp_guess = "Дальні удари (Фланги)"
    
    if opp_b['technique_att'] >= 3:
        guess_details.append(f"Тх{opp_b['technique_att']} (Дриблінг)")
        if opp_att_adv > 1.1: opp_guess = "Технічна гра"

    if cfs >= 3: 
        opp_guess = "Нормальна (3 CF)"
    elif not guess_details and opp_mid_adv > 1.10: 
        opp_guess = "Гра в пас (Володіння)"
    
    guess_str = f"{opp_guess}"
    if guess_details: guess_str += f" [{', '.join(guess_details)}]"

    # 2. Тактика (Повзунок)
    if diff > 0: base_tactic = 47 + (diff * 0.11)
    else: base_tactic = 47 + (diff * 0.2)
    
    base_tactic += -11 if is_opp_home else 11
    if cfs >= 3 and base_tactic > 47: base_tactic = 47 
    tactic_val = max(11, min(92, base_tactic))
    
    t_desc = "Баланс"
    if tactic_val > 60: t_desc = "Атака"
    elif tactic_val < 41: t_desc = "Захист"
    if cfs >= 3 and tactic_val == 47: t_desc += " (Lock: 3 CF)"

    # 3. Паси
    pass_type = "Змішані"; pass_reason = "Рівна гра"
    
    # Якщо у них багато Плеймейкерів -> вони грають коротко. Нам краще грати Дальні?
    # Ні, краще дивитися на співвідношення сил у центрі.
    if mid_ratio > 1.19: pass_type, pass_reason = "Короткі", "Виграємо центр"
    elif mid_ratio < 0.92: pass_type, pass_reason = "Дальні", "Програємо центр"

    # [ВАШІ БОНУСИ] Плеймейкери
    if my_b['playmaker_mid'] >= 3:
        pass_type = "Короткі"
        pass_reason = f"Бонус: {my_b['playmaker_mid']} Плеймейкерів"
    
    # [БОНУС] Якщо у нас перевага, але у них багато "Пл", вони можуть перехопити ініціативу
    if opp_b['playmaker_mid'] > 4 and mid_ratio < 1.10:
        pass_reason += f" (Обережно: у них Пл{opp_b['playmaker_mid']})"

    if tactic_val < 41 and pass_type == "Короткі": pass_type += " -> Змішані (Safety)"
    if diff < -47: pass_type = "Дальні"; pass_reason = "Underdog"

    # 4. Стратегія
    strat = "Нормальна"; strat_reason = "Баланс"
    att_ratio = my_team['att'] / opp_stats['def'] if opp_stats['def'] > 0 else 1.0

    # [ВАШІ БОНУСИ] Флангова гра (Навіс + Голова)
    combo_wing = (my_b['crossing_wing'] >= 2 and my_b['heading_att'] >= 1)
    
    # [ВАШІ БОНУСИ] Техніка
    tech_att = (my_b['technique_att'] >= 2)
    
    if diff < -47: strat, strat_reason = "Дальні удари", "Ми слабші"
    elif mid_ratio < 0.92: strat, strat_reason = "Дальні удари", "Без м'яча"

    # Пріоритет бонусів
    elif combo_wing:
        strat = "Дальні удари"
        strat_reason = f"Бонус: Навіси ({my_b['crossing_wing']}) + Голова ({my_b['heading_att']})"
    elif tech_att and att_ratio > 0.95:
        strat = "Технічна гра"
        strat_reason = f"Бонус: Техніка ({my_b['technique_att']})"

    elif att_ratio > 1.19: strat, strat_reason = "Технічна гра", "Дриблінг (Слабкий захист)"
    elif mid_ratio > 1.19 and pass_type.startswith("Короткі"):
        if att_ratio < 0.92: strat, strat_reason = "Дальні удари", "Контроль але слабкий напад"
        else: strat, strat_reason = "Гра в пас", "Тотальний контроль"

    # 5. Щільність в лінії
    dens_in = 47 + (cfs * 20) - (wings * 20)
    dr_in_reason = f"{cfs} CF vs {wings} Wing"
    
    # [БОНУС] Якщо у них сильні фланги (Навіси), треба розширювати захист?
    if opp_b['crossing_wing'] >= 4:
        dens_in -= 11
        dr_in_reason += " (Anti-Cross)"
        
    if opp_stats['att'] > my_team['def']: dens_in += 11; dr_in_reason += " + Def Weakness"
    if cfs >= 3: dens_in = max(dens_in, 65)
    dens_in = max(11, min(92, dens_in))

    # 6. Щільність між лініями
    dens_btwn = 47; dr_bt_reason = "База"
    if mid_ratio < 0.92: dens_btwn += 20; dr_bt_reason = "Програли центр (Compact)"
    elif mid_ratio > 1.10: dens_btwn -= 20; dr_bt_reason = "Виграли центр"
    if cfs >= 3: dens_btwn = max(dens_btwn, 83); dr_bt_reason = "3 CF -> Бетон"
    if tactic_val < 41: dens_btwn = max(dens_btwn, 74); dr_bt_reason += " + Автобус"
    dens_btwn = max(11, min(92, dens_btwn))

    # 7. Пресинг
    press = "НІ"; press_reason = ""
    if my_team['stamina'] == 100:
        if tactic_val > 60: press = "ТАК"; press_reason = "Атака"
        elif diff < -47: press = "ТАК"; press_reason = "Underdog"
        elif my_b['speed_total'] > 22: press = "ТАК"; press_reason = f"Бонус: Швидкість ({my_b['speed_total']})"

    return {
        'my_tot': my_tot, 'opp_tot': opp_field_pow, 'diff': diff, 'mid_ratio': mid_ratio,
        'opp_guess': guess_str, # Тепер повертаємо рядок з деталями бонусів
        'strat': strat, 'strat_reason': strat_reason,
        'pass_type': pass_type, 'pass_reason': pass_reason,
        'tactic_val': tactic_val, 't_desc': t_desc,
        'dens_in': dens_in, 'dr_in_reason': dr_in_reason,
        'dens_btwn': dens_btwn, 'dr_bt_reason': dr_bt_reason,
        'press': press, 'press_reason': press_reason
    }
