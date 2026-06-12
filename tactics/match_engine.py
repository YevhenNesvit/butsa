import random
import itertools
import os
from joblib import Parallel, delayed

# =====================================================================
# ФУНКЦІЯ-РОБІТНИК ДЛЯ БАГАТОЯДЕРНОСТІ
# Вона має бути поза класами, щоб Windows міг передати її іншим ядрам процесора
# =====================================================================
def evaluate_tactic_worker(args):
    my_t, opp_tactics_list, my_stats, opp_stats, iters_per_opp, min_c, max_c, tourn_coef, my_fouls_avg, opp_fouls_avg = args
    
    total_wins = 0
    total_my_goals = 0
    master_score_counts = {}
    
    # [ОПТИМІЗАЦІЯ 1]: Створюємо стадіон ЛИШЕ ОДИН РАЗ!
    engine = ButsaMatchEngine(my_stats, opp_stats, my_t, opp_tactics_list[0], min_c, max_c, tourn_coef, my_fouls_avg, opp_fouls_avg)
    
    for opp_t in opp_tactics_list:
        # Просто "перевдягаємо" тактику суперника без створення нового об'єкту
        engine.t_opp = opp_t 
        sim = engine.run_monte_carlo(iters_per_opp)
        
        total_wins += sim['wins']
        total_my_goals += sim['my_goals']
        
        for score, count in sim['score_counts'].items():
            master_score_counts[score] = master_score_counts.get(score, 0) + count

    total_matches = len(opp_tactics_list) * iters_per_opp
    winrate = (total_wins / total_matches) * 100 if total_matches > 0 else 0
    avg_goals = total_my_goals / total_matches if total_matches > 0 else 0
    
    most_likely_score = "0:0"
    score_prob = 0
    if master_score_counts:
        most_likely_score = max(master_score_counts, key=master_score_counts.get)
        score_prob = (master_score_counts[most_likely_score] / total_matches) * 100

    return {
        'combo': my_t, 
        'winrate': winrate, 
        'avg_goals': avg_goals,
        'most_likely_score': most_likely_score,
        'score_prob': score_prob
    }

class ButsaMatchEngine:
    def __init__(self, my_stats, opp_stats, my_tactics, opp_tactics, min_c, max_c, tourn_coef, my_fouls_avg=3.0, opp_fouls_avg=3.0):
        self.my = my_stats
        self.opp = opp_stats
        self.t_my = my_tactics
        self.t_opp = opp_tactics
        self.min_c = min_c # Зберегли
        self.max_c = max_c # Зберегли
        self.tourn_coef = tourn_coef
        self.my_fouls_avg = my_fouls_avg   # [НОВЕ]
        self.opp_fouls_avg = opp_fouls_avg # [НОВЕ]

    def get_tactical_multipliers(self, is_me=True):
        t = self.t_my if is_me else self.t_opp
        
        # Тактика (Атака/Захист)
        atk_w = 1.0 + (t['tactic_val'] - 47) / 146.0
        def_w = 1.0 + (47 - t['tactic_val']) / 146.0
        
        dens_b = t['dens_btwn']
        dens_i = t['dens_in']
        
        # 1. ПАСИ (Щільність МІЖ лініями)
        pass_mod = 1.0
        if t['pass_type'] == 'Короткі':
            if dens_b < 41: pass_mod = 0.92       # Розриви між гравцями (штраф)
            elif dens_b > 60: pass_mod = 1.1     # Щільно (бонус)
        elif t['pass_type'] == 'Дальні':
            if dens_b < 41: pass_mod = 1.1       # Широко (бонус)
            elif dens_b > 60: pass_mod = 0.92     # Скупченість (штраф)
        elif t['pass_type'] == 'Змішані':
            if 41 <= dens_b <= 60: pass_mod = 1.01 # Легкий бонус за баланс
            
        # 2. СТРАТЕГІЯ (Щільність В лініях) та УДАР
        strat_mod = 1.0
        shot_boost = 1.0
        
        if t['strat'] == 'Гра в пас':
            if dens_i > 60: strat_mod = 1.1      # Центр (бонус)
            elif dens_i < 41: strat_mod = 0.92    # Розірвані лінії (штраф)
            
        elif t['strat'] == 'Технічна гра':
            if dens_i < 41: strat_mod = 1.1      # Простір для дриблінгу (бонус)
            elif dens_i > 60: strat_mod = 0.92    # Занадто тісно (штраф)
            
        elif t['strat'] == 'Дальні удари':
            strat_mod = 0.92                      # Важче пройти захист (б'ємо здалеку)
            shot_boost = 1.1                     # Але удар небезпечніший
            if 41 <= dens_i <= 60: strat_mod = 1.01 # Легкий бонус за баланс
            
        elif t['strat'] == 'Нормальна':
            if 41 <= dens_i <= 60: strat_mod = 1.01  # Легкий бонус за баланс
            
        return atk_w, def_w, pass_mod, strat_mod, shot_boost

    def simulate_match(self, debug_mode=False):
        my_goals, opp_goals = 0, 0
        total_chances = random.randint(self.min_c, self.max_c)

        # Розпаковуємо всі 5 коефіцієнтів (включно з shot_boost)
        m_atk_w, m_def_w, m_pass_m, m_strat_m, m_shot_boost = self.get_tactical_multipliers(True)
        o_atk_w, o_def_w, o_pass_m, o_strat_m, o_shot_boost = self.get_tactical_multipliers(False)

        def get_rps_multiplier(s1, s2):
            # s1 отримує бонус, якщо б'є s2
            if s1 == 'Гра в пас' and s2 == 'Технічна гра': return 1.1
            if s1 == 'Дальні удари' and s2 == 'Гра в пас': return 1.1
            if s1 == 'Нормальна' and s2 == 'Дальні удари': return 1.1
            if s1 == 'Технічна гра' and s2 == 'Нормальна': return 1.1
            
            # s1 отримує штраф, якщо s2 б'є його
            if s1 == 'Технічна гра' and s2 == 'Гра в пас': return 0.92
            if s1 == 'Гра в пас' and s2 == 'Дальні удари': return 0.92
            if s1 == 'Дальні удари' and s2 == 'Нормальна': return 0.92
            if s1 == 'Нормальна' and s2 == 'Технічна гра': return 0.92
            
            return 1.0 # Нейтральні або однакові тактики

        rps_my = get_rps_multiplier(self.t_my['strat'], self.t_opp['strat'])
        rps_opp = get_rps_multiplier(self.t_opp['strat'], self.t_my['strat'])

        my_poss = self.my.get('possession', 0)
        opp_poss = self.opp.get('possession', 0)
        my_tech = self.my.get('technique', 0)
        opp_tech = self.opp.get('technique', 0)
        my_tack = self.my.get('tackle_eff', 0)
        opp_tack = self.opp.get('tackle_eff', 0)
        my_shot = self.my.get('shot_power', 0) + self.my.get('shot_acc', 0)
        opp_shot = self.opp.get('shot_power', 0) + self.opp.get('shot_acc', 0)
        my_gk = self.my.get('gk_skill', 0)
        opp_gk = self.opp.get('gk_skill', 0)

        my_stam_val = self.my.get('stamina_eff', 0)
        opp_stam_val = self.opp.get('stamina_eff', 0)
        
        # Базове падіння фізики за весь матч
        my_drop_pct = max(0.04, (15.5 - (my_stam_val / 3.0)) / 100.0) * self.tourn_coef
        opp_drop_pct = max(0.04, (15.5 - (opp_stam_val / 3.0)) / 100.0) * self.tourn_coef

        # [НОВЕ] Накопичувачі втоми
        my_current_fatigue = 0.0
        opp_current_fatigue = 0.0

        my_base_foul_chance = self.my_fouls_avg / total_chances if total_chances > 0 else 0
        opp_base_foul_chance = self.opp_fouls_avg / total_chances if total_chances > 0 else 0

        for minute in range(total_chances):
            # 1. РОЗУМНИЙ ПРЕСИНГ (За офіційними правилами Бутси)
            score_diff = abs(my_goals - opp_goals)
            
            my_press_bonus = 1.0
            my_press_penalty = 1.0
            my_is_pressing_now = False

            if self.t_my['press'] == 'ТАК':
                if score_diff < 2:
                    my_press_bonus = 1.10   
                    my_press_penalty = 1.50
                    my_is_pressing_now = True 
                else:
                    # Інтенсивність падає (тренер просив, але гравці бачать, що гра зроблена або провалена)
                    my_press_bonus = 1.0   
                    my_press_penalty = 1.0 
                    my_is_pressing_now = False

            opp_press_bonus = 1.0
            opp_press_penalty = 1.0
            opp_is_pressing_now = False

            if self.t_opp['press'] == 'ТАК':
                if score_diff < 2:
                    opp_press_bonus = 1.10
                    opp_press_penalty = 1.50
                    opp_is_pressing_now = True
                else:
                    opp_press_bonus = 1.0
                    opp_press_penalty = 1.0
                    opp_is_pressing_now = False

            # Накопичуємо втому епізод за епізодом
            my_current_fatigue += (my_drop_pct / total_chances) * my_press_penalty
            opp_current_fatigue += (opp_drop_pct / total_chances) * opp_press_penalty

            # Скільки сил залишилося прямо зараз
            my_stam_drop = max(0.1, 1.0 - my_current_fatigue)
            opp_stam_drop = max(0.1, 1.0 - opp_current_fatigue)

            if debug_mode:
                print(f"Епізод {minute+1}/{total_chances} | Рахунок {my_goals}:{opp_goals}")
                print(f"  Моя фіза: {my_stam_drop*100:.1f}% (Пресинг: {self.t_my['press']})")
                print(f"  Їхня фіза: {opp_stam_drop*100:.1f}% (Пресинг: {self.t_opp['press']})")
                print("-" * 30)

            # 2. ЦЕНТР ПОЛЯ: Володіння
            my_mid = my_poss * m_pass_m * m_strat_m * my_stam_drop * rps_my
            opp_mid = opp_poss * o_pass_m * o_strat_m * opp_stam_drop * rps_opp

            my_pass_bonus = 1.0
            opp_pass_bonus = 1.0

            # Логіка для НАШОЇ команди
            if self.t_my['pass_type'] == 'Короткі':
                if self.t_opp['pass_type'] == 'Змішані': my_pass_bonus = 1.1
                elif self.t_opp['pass_type'] == 'Дальні': my_pass_bonus = 0.92
                
            elif self.t_my['pass_type'] == 'Змішані':
                if self.t_opp['pass_type'] == 'Дальні': my_pass_bonus = 1.1
                elif self.t_opp['pass_type'] == 'Короткі': my_pass_bonus = 0.92
                
            elif self.t_my['pass_type'] == 'Дальні':
                if self.t_opp['pass_type'] == 'Короткі': my_pass_bonus = 1.1
                elif self.t_opp['pass_type'] == 'Змішані': my_pass_bonus = 0.92

            # Логіка для СУПЕРНИКА (дзеркальна)
            if self.t_opp['pass_type'] == 'Короткі':
                if self.t_my['pass_type'] == 'Змішані': opp_pass_bonus = 1.1
                elif self.t_my['pass_type'] == 'Дальні': opp_pass_bonus = 0.92
                
            elif self.t_opp['pass_type'] == 'Змішані':
                if self.t_my['pass_type'] == 'Дальні': opp_pass_bonus = 1.1
                elif self.t_my['pass_type'] == 'Короткі': opp_pass_bonus = 0.92
                
            elif self.t_opp['pass_type'] == 'Дальні':
                if self.t_my['pass_type'] == 'Короткі': opp_pass_bonus = 1.1
                elif self.t_my['pass_type'] == 'Змішані': opp_pass_bonus = 0.92

            # --- ВПЛИВ ПРЕСИНГУ (Множник ризику) ---
            # Якщо ти виграв дуель пасів, пресинг добиває суперника (+0.10)
            # Якщо програв дуель, пресинг погіршує твою ситуацію (-0.10)
            
            if self.t_my['press'] == 'ТАК':
                if my_pass_bonus > 1.0: my_pass_bonus += 0.09  
                elif my_pass_bonus < 1.0: my_pass_bonus -= 0.09 

            if self.t_opp['press'] == 'ТАК':
                if opp_pass_bonus > 1.0: opp_pass_bonus += 0.09
                elif opp_pass_bonus < 1.0: opp_pass_bonus -= 0.09

            # Застосовуємо фінальні бонуси до центру поля
            my_mid *= my_pass_bonus
            opp_mid *= opp_pass_bonus

            if my_mid + opp_mid == 0:
                attacker = 'me' if random.random() < 0.5 else 'opp'
            else:
                attacker = 'me' if random.random() < (my_mid / (my_mid + opp_mid)) else 'opp'

            # 3. АТАКА vs ЗАХИСТ
            if attacker == 'me':
                # --- ЛОГІКА ФОЛІВ ---
                # Якщо суперник пресингує, він фолить частіше (x1.5)
                opp_foul_chance = opp_base_foul_chance * 1.19 if opp_is_pressing_now else opp_base_foul_chance
                
                if random.random() < opp_foul_chance: 
                    if random.random() < 0.25: # 25% фолів - небезпечний штрафний
                        shot = my_shot * m_shot_boost * my_stam_drop * 1.1 
                        gk = (opp_gk * 0.25) * opp_stam_drop
                        if (shot + gk > 0) and random.random() < (shot / (shot + gk)):
                            my_goals += 1
                        continue # Епізод завершено
                    else:
                        foul_def_penalty = 0.92 # Тактичний фол: захист не встиг повернутись
                else:
                    foul_def_penalty = 1.0

                # --- СТАНДАРТНА АТАКА ---
                if self.t_my['strat'] == 'Технічна гра': atk_stat = my_tech
                elif self.t_my['strat'] == 'Гра в пас': atk_stat = my_poss
                else: atk_stat = (my_tech + my_poss) * 0.56
                
                atk_pow = atk_stat * m_atk_w * m_strat_m * my_stam_drop * rps_my
                def_pow = opp_tack * o_def_w * opp_stam_drop * foul_def_penalty 

                if self.t_my['strat'] == 'Дальні удари': def_pow *= 0.92
                if self.t_my['press'] == 'ТАК': atk_pow *= my_press_bonus
                
                if (atk_pow + def_pow > 0) and random.random() < (atk_pow / (atk_pow + def_pow)):
                    shot = my_shot * m_shot_boost * my_stam_drop
                    gk = (opp_gk * 0.25) * opp_stam_drop
                    if self.t_my['strat'] == 'Дальні удари': gk *= 1.1 
                    
                    if (shot + gk > 0) and random.random() < (shot / (shot + gk)):
                        my_goals += 1
                        
            else:
                # --- ЛОГІКА ФОЛІВ (Атакує суперник) ---
                my_foul_chance = my_base_foul_chance * 1.19 if my_is_pressing_now else my_base_foul_chance
                
                if random.random() < my_foul_chance: 
                    if random.random() < 0.25:
                        shot = opp_shot * o_shot_boost * opp_stam_drop * 1.1 
                        gk = (my_gk * 0.25) * my_stam_drop
                        if (shot + gk > 0) and random.random() < (shot / (shot + gk)):
                            opp_goals += 1
                        continue 
                    else:
                        foul_def_penalty = 0.85 
                else:
                    foul_def_penalty = 1.0

                # --- СТАНДАРТНА АТАКА ---
                if self.t_opp['strat'] == 'Технічна гра': atk_stat = opp_tech
                elif self.t_opp['strat'] == 'Гра в пас': atk_stat = opp_poss
                else: atk_stat = (opp_tech + opp_poss) * 0.56
                
                atk_pow = atk_stat * o_atk_w * o_strat_m * opp_stam_drop * rps_opp
                def_pow = my_tack * m_def_w * my_stam_drop * foul_def_penalty

                if self.t_opp['strat'] == 'Дальні удари': def_pow *= 0.92
                if self.t_opp['press'] == 'ТАК': atk_pow *= opp_press_bonus
                
                if (atk_pow + def_pow > 0) and random.random() < (atk_pow / (atk_pow + def_pow)):
                    shot = opp_shot * o_shot_boost * opp_stam_drop
                    gk = (my_gk * 0.25) * my_stam_drop
                    if self.t_opp['strat'] == 'Дальні удари': gk *= 1.1
                    
                    if (shot + gk > 0) and random.random() < (shot / (shot + gk)):
                        opp_goals += 1

        return my_goals, opp_goals

    def run_monte_carlo(self, iterations=3):
        wins, draws, losses = 0, 0, 0
        my_total, opp_total = 0, 0
        score_counts = {}

        for _ in range(iterations):
            g_m, g_o = self.simulate_match()
            my_total += g_m
            opp_total += g_o
            
            if g_m > g_o: wins += 1
            elif g_m == g_o: draws += 1
            else: losses += 1

            score_str = f"{g_m}:{g_o}"
            score_counts[score_str] = score_counts.get(score_str, 0) + 1

        return {
            'wins': wins, 'draws': draws, 'losses': losses,
            'my_goals': my_total, 'opp_goals': opp_total,
            'score_counts': score_counts,
            'iterations': iterations
        }

class TacticsOptimizer:
    # ТЕПЕР ВІН ПРИЙМАЄ 3 АРГУМЕНТИ (третій - необов'язковий)
    def __init__(self, my_stats, opp_stats, opp_tactics_input=None, min_c=2, max_c=20, tourn_coef=0.5, my_fouls_avg=3.0, opp_fouls_avg=3.0):
        self.my = my_stats
        self.opp = opp_stats
        self.min_c = min_c
        self.max_c = max_c
        self.tourn_coef = tourn_coef
        self.my_fouls_avg = my_fouls_avg   # [НОВЕ]
        self.opp_fouls_avg = opp_fouls_avg # [НОВЕ]
        
        # Обробляємо те, що ви передали з app.py
        if opp_tactics_input is not None:
            if isinstance(opp_tactics_input, dict):
                # Якщо передали одну тактику (від Тренера)
                self.opp_tactics_list = [opp_tactics_input]
            else:
                # Якщо передали свій ручний список
                self.opp_tactics_list = opp_tactics_input
        else:
            # Якщо нічого не передали (opp_tactics_input=None) - ГЕНЕРУЄМО 3000 ВАРІАНТІВ
            opp_passes = ['Короткі', 'Змішані', 'Дальні']
            opp_strats = ['Нормальна', 'Гра в пас', 'Технічна гра', 'Дальні удари']
            opp_press = ['ТАК', 'НІ']
            opp_tac_opts = [11, 31, 51, 71, 91]
            opp_din_opts = [11, 31, 51, 71, 91]
            opp_dbt_opts = [11, 31, 51, 71, 91]

            opp_all_combos = list(itertools.product(opp_passes, opp_strats, opp_press, opp_tac_opts, opp_din_opts, opp_dbt_opts))
            self.opp_tactics_list = []
            for combo in opp_all_combos:
                self.opp_tactics_list.append({
                    'pass_type': combo[0], 'strat': combo[1], 'press': combo[2],
                    'tactic_val': combo[3], 'dens_in': combo[4], 'dens_btwn': combo[5]
                })

    def find_best_tactic(self):
        # 1. 3000 ВАШИХ КОМБІНАЦІЙ
        my_passes = ['Короткі', 'Змішані', 'Дальні']
        my_strats = ['Нормальна', 'Гра в пас', 'Технічна гра', 'Дальні удари']
        my_press = ['ТАК', 'НІ']
        my_tac_opts = [11, 31, 51, 71, 91]
        my_din_opts = [11, 31, 51, 71, 91]
        my_dbt_opts = [11, 31, 51, 71, 91]

        my_all_combos = list(itertools.product(my_passes, my_strats, my_press, my_tac_opts, my_din_opts, my_dbt_opts))

        # 2. ДИНАМІЧНА КІЛЬКІСТЬ ІТЕРАЦІЙ
        # Якщо тестуємо проти 1 тактики Тренера, треба багато матчів (200) для точності.
        # Якщо тестуємо проти 3000 тактик, достатньо 2 матчів (бо 3000*2 = 6000 матчів сумарно).
        iters_per_opp = 200 if len(self.opp_tactics_list) == 1 else 1

        # 3. ПІДГОТОВКА ДАНИХ ДЛЯ ЯДЕР ПРОЦЕСОРА
        worker_args = []
        for my_combo in my_all_combos:
            my_t = {
                'pass_type': my_combo[0], 'strat': my_combo[1], 'press': my_combo[2],
                'tactic_val': my_combo[3], 'dens_in': my_combo[4], 'dens_btwn': my_combo[5]
            }
            worker_args.append((my_t, self.opp_tactics_list, self.my, self.opp, iters_per_opp, self.min_c, self.max_c, self.tourn_coef, self.my_fouls_avg, self.opp_fouls_avg))
        
        # [ОПТИМІЗАЦІЯ 2]: Запуск через Joblib (Безпечно для Streamlit!)
        cores_to_use = max(1, os.cpu_count() - 1) 
        
        # Joblib автоматично обійде всі проблеми з пам'яттю і GIL
        results = Parallel(n_jobs=cores_to_use)(
            delayed(evaluate_tactic_worker)(arg) for arg in worker_args
        )

        # Сортуємо: 1) Вінрейт 2) Голи
        results.sort(key=lambda x: (round(x['winrate'] * 2) / 2, x['avg_goals']), reverse=True)
        return results[:3]
