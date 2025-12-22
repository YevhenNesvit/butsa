import math

# --- КОНСТАНТИ СХЕМ ---
ALL_FORMATIONS = {
    '3-4-3': {'def': 3, 'mid': 4, 'att': 3},
    '3-5-2': {'def': 3, 'mid': 5, 'att': 2},
    '4-4-2': {'def': 4, 'mid': 4, 'att': 2},
    '4-3-3': {'def': 4, 'mid': 3, 'att': 3},
    '4-5-1': {'def': 4, 'mid': 5, 'att': 1},
    '5-3-2': {'def': 5, 'mid': 3, 'att': 2},
    '5-4-1': {'def': 5, 'mid': 4, 'att': 1},
    '2-5-3': {'def': 2, 'mid': 5, 'att': 3}
}

def calculate_nominal_power(player, is_home=False):
    """
    Повертає НОМІНАЛЬНУ силу (для ліміту турніру).
    Це чиста сила гравця (з колонки 'Мас') без жодних бонусів.
    Аргумент is_home залишено для сумісності виклику, але він не впливає на номінал.
    """
    return player['power']

def calculate_real_power(player, is_home):
    """
    Розраховує РЕАЛЬНУ силу (для матчу).
    Формула: Базова сила * Коефіцієнт Стаміни * Коефіцієнт Моралі.
    """
    base = player['power']
    
    # 1. Вплив фізготовності (Stamina)
    # 100% стаміни = 1.0, 90% = 0.9
    stam_coef = player.get('stamina', 100) / 100.0
    
    # 2. Вплив моралі + домашнього бонусу
    mor = player.get('morale', 13)
    home_bonus = 4 if is_home else 0
    cur_mor = mor + home_bonus
    
    # Формула моралі: базовий 1.0 + (відхилення від 13) * 0.004
    # Приклад: Мораль 20 -> 1 + (7 * 0.004) = 1.028
    mor_coef = 1.0 + (cur_mor - 13) * 0.004
    
    return base * stam_coef * mor_coef

def calculate_line_power(players_list):
    """Рахує сумарну РЕАЛЬНУ силу списку гравців (для оцінки сили ліній)."""
    if not players_list:
        return 0
    return sum(p['real_power'] for p in players_list)

def get_valid_pos_list(line_name):
    if line_name == 'gk': return ['GK']
    if line_name == 'def': return ['CD', 'LD', 'RD', 'SW', 'LWD', 'RWD']
    if line_name == 'mid': return ['CM', 'RM', 'LM', 'DM', 'AM']
    if line_name == 'att': return ['CF', 'LF', 'RF', 'LW', 'RW']
    return []

def solve_cap_puzzle(roster, formation, cap):
    """
    Підбирає склад так, щоб НОМІНАЛЬНА сила (Мас) не перевищувала CAP.
    Пріоритет: 1. Хвилини -> 2. Реальна сила.
    """
    starters = {'gk': [], 'def': [], 'mid': [], 'att': []}
    used_names = set()
    
    # Сортування: Спочатку ті, хто має ігрову практику, потім найсильніші реально
    sorted_roster = sorted(roster, key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)

    order = [('gk', 1), ('def', formation['def']), ('mid', formation['mid']), ('att', formation['att'])]
    
    # --- ЕТАП 1: НАБІР ОСНОВИ (Draft) ---
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
        # Fallback (якщо не вистачило гравців з хвилинами)
        if c < count:
             for p in sorted_roster:
                if c >= count: break
                if p['name'] in used_names: continue
                if any(pos in p['pos'] for pos in valid):
                    starters[line].append(p)
                    used_names.add(p['name'])
                    c += 1

    bench = [p for p in sorted_roster if p['name'] not in used_names]
    
    # Допоміжні функції для підрахунку сум
    def calc_nom_total(sq): 
        # Рахуємо по nominal_power (чистий Мас)
        return sum(p['nominal_power'] for l in sq.values() for p in l)
    
    def calc_real_total(sq): 
        return sum(p['real_power'] for l in sq.values() for p in l)

    curr_nom = calc_nom_total(starters)
    limit_loops = 0
    
    # --- ЕТАП 2: ОПТИМІЗАЦІЯ ---
    
    # ВАРІАНТ А: ПЕРЕБІР (> Cap) -> Зменшуємо номінал
    if curr_nom > cap:
        while curr_nom > cap and limit_loops < 200:
            best_swap = None
            min_real_loss = 9999
            
            for line in ['gk', 'def', 'mid', 'att']:
                valid = get_valid_pos_list(line)
                line_bench = [b for b in bench if any(vp in b['pos'] for vp in valid)]
                
                for i, start_p in enumerate(starters[line]):
                    for sub_p in line_bench:
                        # Шукаємо заміну, яка зменшує НОМІНАЛ (start > sub)
                        if start_p['nominal_power'] > sub_p['nominal_power']:
                            # Але при цьому намагаємось втратити мінімум РЕАЛЬНОЇ сили
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

    # ВАРІАНТ Б: НЕДОБІР (< Cap) -> Збільшуємо реальну силу (Upgrade)
    elif curr_nom < cap:
        while limit_loops < 200:
            best_swap = None
            max_real_gain = 0.01 # Поріг мінімального покращення
            
            for line in ['gk', 'def', 'mid', 'att']:
                valid = get_valid_pos_list(line)
                line_bench = [b for b in bench if any(vp in b['pos'] for vp in valid)]
                
                for i, start_p in enumerate(starters[line]):
                    for sub_p in line_bench:
                        # Різниця в номіналі
                        diff_nom = sub_p['nominal_power'] - start_p['nominal_power']
                        
                        # Перевіряємо:
                        # 1. Чи вліземо ми в ліміт з новим гравцем? (curr_nom + diff <= cap)
                        # 2. Чи дасть це приріст РЕАЛЬНОЇ сили?
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

def get_tactical_advice(my_team, opp_stats, best_meta, is_opp_home):
    """
    Повертає словник з порадами.
    """
    my_tot = my_team['def'] + my_team['mid'] + my_team['att']
    opp_gk_pow = opp_stats['squad_dict']['gk'][0]['real_power'] if opp_stats['squad_dict']['gk'] else 0
    opp_field_pow = opp_stats['real_total'] - opp_gk_pow
    diff = my_tot - opp_field_pow
    
    mid_ratio = my_team['mid'] / opp_stats['mid'] if opp_stats['mid'] > 0 else 1.0
    opp_mid_adv = opp_stats['mid'] / my_team['mid'] if my_team['mid'] > 0 else 1.0
    opp_att_adv = opp_stats['att'] / my_team['def'] if my_team['def'] > 0 else 1.0
    
    cfs = best_meta['c']
    wings = best_meta['w']

    # 1. Прогноз дій суперника
    opp_guess = "Нормальна"
    if cfs >= 3: opp_guess = "Нормальна (Акцент на 3 CF)"
    elif opp_mid_adv > 1.05: opp_guess = "Гра в пас (Володіння)"
    elif opp_att_adv > 1.10: opp_guess = "Технічна гра (Дриблінг)"
    else: opp_guess = "Дальні удари (Безпека)"

    # 2. Наша Тактика
    base_tactic = 50 + (diff * 0.2)
    base_tactic += -11 if is_opp_home else 11
    if cfs >= 3 and base_tactic > 50: base_tactic = 50 
    
    tactic_val = max(11, min(92, base_tactic))
    t_desc = "Баланс"
    if tactic_val > 60: t_desc = "Атака"
    elif tactic_val < 41: t_desc = "Захист"
    if cfs >= 3 and tactic_val == 50: t_desc += " (Lock: 3 CF)"

    # 3. Наші Паси
    pass_type = "Змішані"; pass_reason = "Рівна гра"
    if mid_ratio > 1.10: pass_type, pass_reason = "Короткі", "Виграємо центр"
    elif mid_ratio < 0.92: pass_type, pass_reason = "Дальні", "Програємо центр"
    if tactic_val < 41 and pass_type == "Короткі": pass_type += " -> Змішані (Safety)"
    if diff < -50: pass_type = "Дальні"; pass_reason = "Underdog"

    # 4. Наша Стратегія
    strat = "Нормальна"; strat_reason = "Баланс"
    att_ratio = my_team['att'] / opp_stats['def'] if opp_stats['def'] > 0 else 1.0

    if diff < -50: strat, strat_reason = "Дальні удари", "Ми слабші"
    elif mid_ratio < 0.92: strat, strat_reason = "Дальні удари", "Без м'яча"
    elif att_ratio > 1.19: strat, strat_reason = "Технічна гра", "Дриблінг (Слабкий захист)"
    elif mid_ratio > 1.10 and pass_type.startswith("Короткі"):
        if att_ratio < 0.92: strat, strat_reason = "Дальні удари", "Контроль але слабкий напад"
        else: strat, strat_reason = "Гра в пас", "Тотальний контроль"

    # 5. Щільність в лінії
    dens_in = 50 + (cfs * 20) - (wings * 20)
    dr_in_reason = f"{cfs} CF vs {wings} Wing"
    if opp_stats['att'] > my_team['def']: dens_in += 11; dr_in_reason += " + Def Weakness"
    if cfs >= 3: dens_in = max(dens_in, 65)
    dens_in = max(11, min(92, dens_in))

    # 6. Щільність між лініями
    dens_btwn = 50; dr_bt_reason = "База"
    if mid_ratio < 0.92: dens_btwn += 20; dr_bt_reason = "Програли центр (Compact)"
    elif mid_ratio > 1.10: dens_btwn -= 20; dr_bt_reason = "Виграли центр"
    if cfs >= 3: dens_btwn = max(dens_btwn, 83); dr_bt_reason = "3 CF -> Бетон"
    if tactic_val < 41: dens_btwn = max(dens_btwn, 74); dr_bt_reason += " + Автобус"
    dens_btwn = max(11, min(92, dens_btwn))

    # 7. Пресинг
    press = "НІ"; press_reason = ""
    if my_team['stamina'] >= 95:
        if tactic_val > 60: press = "ТАК"; press_reason = "Атака"
        elif diff < -47: press = "ТАК"; press_reason = "Underdog"

    return {
        'my_tot': my_tot, 'opp_tot': opp_field_pow, 'diff': diff, 'mid_ratio': mid_ratio,
        'opp_guess': opp_guess,
        'strat': strat, 'strat_reason': strat_reason,
        'pass_type': pass_type, 'pass_reason': pass_reason,
        'tactic_val': tactic_val, 't_desc': t_desc,
        'dens_in': dens_in, 'dr_in_reason': dr_in_reason,
        'dens_btwn': dens_btwn, 'dr_bt_reason': dr_bt_reason,
        'press': press, 'press_reason': press_reason
    }
