# ==============================================================================
# МОДУЛЬ ТАКТИЧНОЇ ЛОГІКИ
# ==============================================================================

def calculate_real_power(player, is_home):
    """
    Розраховує реальну силу гравця з урахуванням стаміни, моралі та домашнього бонусу.
    """
    base = player['power']
    stam = player.get('stamina', 100) / 100.0
    mor = player.get('morale', 13)
    home_bonus = 4 if is_home else 0
    cur_mor = mor + home_bonus
    mor_mult = 1.0 + (cur_mor - 13) * 0.004
    return base * stam * mor_mult


def get_valid_pos_list(line_name):
    """
    Повертає список валідних позицій для заданої лінії.
    """
    if line_name == 'gk': return ['GK']
    if line_name == 'def': return ['CD', 'LD', 'RD', 'SW', 'LWD', 'RWD']
    if line_name == 'mid': return ['CM', 'RM', 'LM', 'DM', 'AM']
    if line_name == 'att': return ['CF', 'LF', 'RF', 'LW', 'RW']
    return []


def solve_cap_puzzle(roster, formation, cap):
    """
    Розумний підбір складу:
    1. Набирає основу за хвилинами.
    2. Якщо перебір (> Cap) -> міняє сильних на слабших.
    3. Якщо недобір (< Cap) -> міняє слабких на сильних (UPGRADE).
    """
    starters = {'gk': [], 'def': [], 'mid': [], 'att': []}
    used_names = set()
    
    # 1. Сортування (Хвилини -> Сила)
    sorted_roster = sorted(roster, key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)

    order = [('gk', 1), ('def', formation['def']), ('mid', formation['mid']), ('att', formation['att'])]
    
    # --- ЕТАП 1: НАБІР БАЗИ (за досвідом) ---
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
        # Fallback (якщо не вистачило)
        if c < count:
             for p in sorted_roster:
                if c >= count: break
                if p['name'] in used_names: continue
                if any(pos in p['pos'] for pos in valid):
                    starters[line].append(p)
                    used_names.add(p['name'])
                    c += 1

    # Формуємо лавку
    bench = [p for p in sorted_roster if p['name'] not in used_names]
    
    def calc_nom(sq): return sum(p['power'] for l in sq.values() for p in l)
    def calc_real(sq): return sum(p['real_power'] for l in sq.values() for p in l)

    curr_nom = calc_nom(starters)
    limit_loops = 0
    
    # --- ЕТАП 2: ОПТИМІЗАЦІЯ (ДВОСТОРОННЯ) ---

    # ВАРІАНТ А: ПЕРЕБІР (Треба зменшити силу)
    if curr_nom > cap:
        while curr_nom > cap and limit_loops < 200:
            best_swap = None
            min_real_loss = 9999
            
            for line in ['gk', 'def', 'mid', 'att']:
                valid = get_valid_pos_list(line)
                line_bench = [b for b in bench if any(vp in b['pos'] for vp in valid)]
                
                for i, start_p in enumerate(starters[line]):
                    for sub_p in line_bench:
                        # Шукаємо заміну, яка ЗМЕНШУЄ номінал (start > sub)
                        if start_p['power'] > sub_p['power']:
                            real_loss = start_p['real_power'] - sub_p['real_power']
                            # Мінімізуємо втрату реальної сили
                            if real_loss < min_real_loss:
                                min_real_loss = real_loss
                                best_swap = (line, i, start_p, sub_p)
            
            if best_swap:
                l, idx, out_p, in_p = best_swap
                starters[l][idx] = in_p
                used_names.remove(out_p['name']); used_names.add(in_p['name'])
                bench.remove(in_p); bench.append(out_p)
                bench.sort(key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)
                curr_nom = calc_nom(starters)
                limit_loops += 1
            else: break

    # ВАРІАНТ Б: НЕДОБІР (UPGRADE - Цього не вистачало!)
    # Якщо у нас є місце під лімітом, шукаємо кого підсилити
    elif curr_nom < cap:
        while limit_loops < 200:
            best_swap = None
            max_real_gain = 0.1 # Шукаємо хоч якийсь приріст
            
            for line in ['gk', 'def', 'mid', 'att']:
                valid = get_valid_pos_list(line)
                line_bench = [b for b in bench if any(vp in b['pos'] for vp in valid)]
                
                for i, start_p in enumerate(starters[line]):
                    for sub_p in line_bench:
                        # Шукаємо заміну, яка ЗБІЛЬШУЄ номінал (sub > start)
                        diff_nom = sub_p['power'] - start_p['power']
                        
                        # Умова 1: Гравець сильніший
                        # Умова 2: Ми все ще влазимо в CAP з цим гравцем
                        if diff_nom > 0 and (curr_nom + diff_nom) <= cap:
                            real_gain = sub_p['real_power'] - start_p['real_power']
                            
                            # Максимізуємо приріст реальної сили
                            if real_gain > max_real_gain:
                                max_real_gain = real_gain
                                best_swap = (line, i, start_p, sub_p)
            
            if best_swap:
                l, idx, out_p, in_p = best_swap
                starters[l][idx] = in_p
                used_names.remove(out_p['name']); used_names.add(in_p['name'])
                bench.remove(in_p); bench.append(out_p)
                # Пересортовувати лавку тут не обов'язково, але хай буде
                bench.sort(key=lambda x: (x.get('minutes', 0), x['real_power']), reverse=True)
                curr_nom = calc_nom(starters)
                limit_loops += 1
            else: break # Більше нікого не можна покращити, не пробивши стелю

    flat_list = starters['gk'] + starters['def'] + starters['mid'] + starters['att']
    return {
        'nominal': curr_nom,
        'real_total': calc_real(starters),
        'squad_dict': starters,
        'squad_list': flat_list,
        'def': sum(p['real_power'] for p in starters['def']),
        'mid': sum(p['real_power'] for p in starters['mid']),
        'att': sum(p['real_power'] for p in starters['att'])
    }


def analyze_threats(squad):
    """
    Аналізує загрози атаки: кількість центрфорвардів і вінгерів.
    """
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


def calculate_tactics(my_team, opp_stats, opponent_home, best_formation):
    """
    Розраховує тактичні рекомендації на основі балансу сил.
    
    Args:
        my_team: dict з 'def', 'mid', 'att', 'stamina'
        opp_stats: результат solve_cap_puzzle
        opponent_home: bool - чи суперник вдома
        best_formation: dict з 'c', 'w' (кількість CF і вінгерів)
    
    Returns:
        dict: Тактичні рекомендації
    """
    my_tot = my_team['def'] + my_team['mid'] + my_team['att']
    opp_gk_pow = opp_stats['squad_dict']['gk'][0]['real_power']
    opp_tot = opp_stats['real_total'] - opp_gk_pow
    diff = my_tot - opp_tot
    
    mid_ratio = my_team['mid'] / opp_stats['mid'] if opp_stats['mid'] > 0 else 1
    att_ratio = my_team['att'] / opp_stats['def'] if opp_stats['def'] > 0 else 1
    cfs = best_formation['c']
    wings = best_formation['w']

    # Тактика
    base_tactic = 50 + (diff * 0.2)
    base_tactic += -11 if opponent_home else 11
    if cfs >= 3 and base_tactic > 50: base_tactic = 50  # Lock
    
    tactic_val = max(11, min(92, base_tactic))
    t_desc = "Баланс"
    if tactic_val > 60: t_desc = "Атака"
    elif tactic_val < 41: t_desc = "Захист"
    if cfs >= 3: t_desc += " (Lock: 3 CF)"

    # Паси
    pass_type = "Змішані"
    pass_reason = "Рівна гра"
    if mid_ratio > 1.10: pass_type, pass_reason = "Короткі", "Виграємо центр"
    elif mid_ratio < 0.92: pass_type, pass_reason = "Дальні", "Програємо центр"
    if tactic_val < 41 and pass_type == "Короткі": pass_type += " -> Змішані (Safety)"
    if diff < -50: pass_type = "Дальні (Underdog)"

    # Стратегія
    strat = "Нормальна"
    strat_reason = "Баланс"
    if mid_ratio < 0.92: strat, strat_reason = "Дальні удари", "Без м'яча"
    elif att_ratio > 1.19: strat, strat_reason = "Технічна гра", "Дриблінг (Слабкий захист)"
    elif mid_ratio > 1.10 and pass_type.startswith("Короткі"):
        if att_ratio < 0.92: strat, strat_reason = "Дальні удари", "Контроль але слабкий напад"
        else: strat, strat_reason = "Гра в пас", "Тотальний контроль"

    # Щільність в лінії
    dens_in = 50 + (cfs * 20) - (wings * 20)
    dr_in_reason = f"{cfs} CF vs {wings} Wing"
    if opp_stats['att'] > my_team['def']: 
        dens_in += 11; dr_in_reason += " + Def Weakness"
    if cfs >= 3: dens_in = max(dens_in, 65)
    dens_in = max(11, min(92, dens_in))

    # Щільність між лініями
    dens_btwn = 50
    dr_bt_reason = "База"
    if mid_ratio < 0.92: dens_btwn += 20; dr_bt_reason = "Програли центр (Compact)"
    elif mid_ratio > 1.10: dens_btwn -= 20; dr_bt_reason = "Виграли центр"
    
    if cfs >= 3: 
        dens_btwn = max(dens_btwn, 83); dr_bt_reason = "3 CF -> Бетон"
    if tactic_val < 41:
        dens_btwn = max(dens_btwn, 74); dr_bt_reason += " + Автобус"
    dens_btwn = max(11, min(92, dens_btwn))

    # Пресинг
    press = "НІ"
    press_reason = ""
    if my_team['stamina'] == 100:
        if tactic_val > 60: press = "ТАК"; press_reason = "Атака"
        elif diff < -47: press = "ТАК"; press_reason = "Underdog"

    return {
        'my_tot': my_tot,
        'opp_tot': opp_tot,
        'diff': diff,
        'mid_ratio': mid_ratio,
        'strat': strat,
        'strat_reason': strat_reason,
        'pass_type': pass_type,
        'pass_reason': pass_reason,
        'tactic_val': tactic_val,
        't_desc': t_desc,
        'dens_in': dens_in,
        'dr_in_reason': dr_in_reason,
        'dens_btwn': dens_btwn,
        'dr_bt_reason': dr_bt_reason,
        'press': press,
        'press_reason': press_reason
    }
