import streamlit as st
import json
import os
import pandas as pd
from fetcher import scrape_roster
import tactics_logic as lg  # Імпортуємо оновлений модуль логіки
import match_engine as me

# ==============================================================================
# НАЛАШТУВАННЯ
# ==============================================================================

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "cookie": "", "my_roster_url": "", 
        "cap": 0, "tourn": "Коммерческие турниры"
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

st.set_page_config(page_title="Butsa Tactics Pro", layout="wide")
st.title("⚽ Butsa.pro Tactical Assistant (Squad Builder)")

# Session State
if 'my_roster' not in st.session_state: st.session_state.my_roster = []
if 'opp_roster' not in st.session_state: st.session_state.opp_roster = []
if 'my_team_name' not in st.session_state: st.session_state.my_team_name = ""
if 'opp_team_name' not in st.session_state: st.session_state.opp_team_name = ""

config = load_config()

# ==============================================================================
# БІЧНА ПАНЕЛЬ
# ==============================================================================
with st.sidebar:
    st.header("⚙️ Налаштування")
    
    cookie_input = st.text_input("PHPSESSID (Cookie)", value=config.get("cookie", ""), type="password")
    
    st.subheader("Параметри Матчу")
    cap_input = st.number_input("Ліміт сили (Cap)", value=config.get("cap", 0))
    tourn_input = st.text_input("Назва турніру", value=config.get("tourn", "Коммерческие турниры"))
    opponent_home = st.checkbox("Суперник грає вдома?", value=False)
    
    i_am_home = not opponent_home

    st.divider()
    st.caption("Опції аналізу")
    # ТЕПЕР МИ БЕРЕМО СХЕМИ З ЛОГІКИ
    formation_options = ["Авто (Підібрати найкращу)"] + list(lg.ALL_FORMATIONS.keys())
    selected_formation_name = st.selectbox("Схема суперника:", formation_options)
    
    if st.button("💾 Зберегти налаштування"):
        new_conf = {
            "cookie": cookie_input,
            "cap": cap_input, 
            "tourn": tourn_input,
            "my_roster_url": st.session_state.get('my_url_input', config.get('my_roster_url', ''))
        }
        save_config(new_conf)
        st.success("Збережено!")

# ==============================================================================
# ОСНОВНИЙ ЕКРАН
# ==============================================================================

col_me, col_opp = st.columns([1, 1])

# --- МОЯ КОМАНДА ---
with col_me:
    header_text = f"🟢 Моя Команда: {st.session_state.my_team_name}" if st.session_state.my_team_name else "🟢 Моя Команда"
    st.header(header_text)

    if 'flash_msg_me' in st.session_state:
        st.success(st.session_state.flash_msg_me)
        del st.session_state.flash_msg_me

    my_roster_url = st.text_input("URL мого ростера", value=config.get("my_roster_url", ""), key="my_url_input")
    
    if st.button("📥 Завантажити мій склад"):
        if not cookie_input:
            st.error("Потрібен Cookie!")
        else:
            with st.spinner("Завантаження..."):
                team_name, roster = scrape_roster(my_roster_url, cookie_input, tourn_input)
                if roster:
                    st.session_state.my_team_name = team_name
                    for p in roster:
                        p['nominal_power'] = lg.calculate_nominal_power(p, i_am_home)
                        p['real_power'] = lg.calculate_real_power(p, i_am_home)
                    st.session_state.my_roster = roster
                    st.session_state.flash_msg_me = f"Завантажено {len(roster)} гравців!"
                    st.rerun()
                else:
                    st.error("Помилка завантаження.")

    if st.session_state.my_roster:
        st.divider()
        st.subheader("🛠️ Конструктор")
        
        # Функція форматування: показуємо і Номінал, і Реал
        def format_func(player):
            return f"{player['name']} [{player['pos'][0]} | Nom:{player['nominal_power']:.1f} Real:{player['real_power']:.1f}]"

        all_players = st.session_state.my_roster
        
        gks = [p for p in all_players if 'GK' in p['pos']]
        defs = [p for p in all_players if any(x in p['pos'] for x in lg.get_valid_pos_list('def'))]
        mids = [p for p in all_players if any(x in p['pos'] for x in lg.get_valid_pos_list('mid'))]
        atts = [p for p in all_players if any(x in p['pos'] for x in lg.get_valid_pos_list('att'))]

        sel_gk = st.selectbox("Воротар (GK)", gks, format_func=format_func)
        sel_defs = st.multiselect("Захист (DEF)", defs, format_func=format_func)
        sel_mids = st.multiselect("Півзахист (MID)", mids, format_func=format_func)
        sel_atts = st.multiselect("Напад (ATT)", atts, format_func=format_func)

        # Рахуємо Номінал (для ліміту) і Реал (для тактики)
        my_nom_total = (sum(p['nominal_power'] for p in sel_defs + sel_mids + sel_atts) + (sel_gk['nominal_power'] if sel_gk else 0))
        
        my_gk_pow = sel_gk['real_power'] if sel_gk else 0
        my_def_pow = lg.calculate_line_power(sel_defs) + my_gk_pow
        my_mid_pow = lg.calculate_line_power(sel_mids)
        my_att_pow = lg.calculate_line_power(sel_atts)
        
        count_players = 1 + len(sel_defs) + len(sel_mids) + len(sel_atts)

        my_squad_dict = {
            'gk': [sel_gk] if sel_gk else [],
            'def': sel_defs,
            'mid': sel_mids,
            'att': sel_atts
        }

        st.info(f"""
        **Гравців:** {count_players}/11
        
        📊 **NOMINAL (Cap):** {my_nom_total:.1f} / {cap_input}
        💪 **REAL POWER:** {(my_def_pow + my_mid_pow + my_att_pow):.1f}
        
        🛡️ **DEF:** {my_def_pow:.1f}  
        ⚙️ **MID:** {my_mid_pow:.1f}  
        ⚔️ **ATT:** {my_att_pow:.1f}
        """)
        
        my_team_stats = {'def': my_def_pow, 'mid': my_mid_pow, 'att': my_att_pow, 'stamina': 100, 'squad_dict': my_squad_dict}
    else:
        st.warning("Спочатку завантажте свою команду.")
        my_team_stats = None


# --- СУПЕРНИК ---
with col_opp:
    header_text_opp = f"🔴 Суперник: {st.session_state.opp_team_name}" if st.session_state.opp_team_name else "🔴 Суперник"
    st.header(header_text_opp)

    if 'flash_msg' in st.session_state:
        st.success(st.session_state.flash_msg)
        del st.session_state.flash_msg

    opp_roster_url = st.text_input("URL ростера суперника")
    
    if st.button("🕵️ Аналізувати Суперника", type="primary"):
        if not opp_roster_url or not cookie_input:
            st.error("Потрібен URL та Cookie!")
        else:
            with st.spinner("Шпигуємо..."):
                team_name, raw_roster = scrape_roster(opp_roster_url, cookie_input, tourn_input)
                if raw_roster:
                    # Попередній розрахунок Nom/Real для суперника
                    st.session_state.opp_team_name = team_name
                    for p in raw_roster:
                        p['nominal_power'] = lg.calculate_nominal_power(p, opponent_home)
                        p['real_power'] = lg.calculate_real_power(p, opponent_home)
                    st.session_state.opp_roster = raw_roster
                    st.session_state.flash_msg = f"Завантажено {len(raw_roster)} гравців!"
                    st.rerun()
                else:
                    st.error("Помилка збору даних.")

# ==============================================================================
# АНАЛІЗ
# ==============================================================================

if st.session_state.opp_roster and my_team_stats:
    st.divider()
    st.header("🧠 Тактичний Аналіз")
    
    raw_roster = st.session_state.opp_roster
    formations_to_analyze = (lg.ALL_FORMATIONS if selected_formation_name == "Авто (Підібрати найкращу)" 
                             else {selected_formation_name: lg.ALL_FORMATIONS[selected_formation_name]})

    results = []
    for fname, fstruct in formations_to_analyze.items():
        res = lg.solve_cap_puzzle(raw_roster, fstruct, cap_input)
        if len(res['squad_list']) < 11: continue
        c, w = lg.analyze_threats(res['squad_dict'])
        total_mins = sum(p['minutes'] for p in res['squad_list'])
        results.append({'name': fname, 'res': res, 'c': c, 'w': w, 'total_mins': total_mins})

    if not results:
        st.error("Не вдалося скласти склад суперника.")
    else:
        results.sort(key=lambda x: (x['total_mins'], x['res']['real_total']), reverse=True)
        best = results[0]
        opp_stats = best['res']

        # Отримуємо Diff та тишком генеруємо ймовірну тактику (тільки для консольного демо-матчу)
        advice = lg.get_tactical_advice(
            my_team_stats, 
            opp_stats, 
            {'c': best['c'], 'w': best['w']}, 
            opponent_home
        )
        opp_predicted = advice['opp_predicted_tactic'] # Зберігаємо для терміналу

        # Єдиний чистий блок інформації про суперника (без колонок)
        st.subheader(f"Прогноз: {best['name']}")
        if selected_formation_name != "Авто (Підібрати найкращу)": 
            st.caption("(Схема зафіксована)")
        
        s = opp_stats['squad_dict']
        st.write(f"**Nominal (Cap):** {opp_stats['nominal']:.1f} / {cap_input}")
        st.write(f"**Real Power:** {opp_stats['real_total']:.1f}")
        st.markdown(f"**Різниця в силі (Diff):** :violet[{advice['diff']:.1f}]") # Перенесли сюди і виділили кольором!
        st.write("---")
        
        st.write(f"**DEF ({opp_stats['def']:.1f}):** {', '.join([p['name'] for p in s['def']])}")
        st.write(f"**MID ({opp_stats['mid']:.1f}):** {', '.join([p['name'] for p in s['mid']])}")
        st.write(f"**ATT ({opp_stats['att']:.1f}):** {', '.join([p['name'] for p in s['att']])}")
        if s['gk']: 
            st.caption(f"GK ({s['gk'][0]['real_power']:.1f}): " + s['gk'][0]['name'])

        st.divider()
        st.subheader("🤖 ШІ-Оптимізатор (Monte Carlo Brute-Force)")
        st.write("Просимулювати всі можливі комбінації, щоб знайти 100% ідеальну тактику?")
        
        # ==========================================
        # НАЛАШТУВАННЯ СИМУЛЯТОРА
        # ==========================================
        st.markdown("---")
        st.subheader("⚙️ Режим симуляції")

        # --- ПОЧАТОК НОВОГО БЛОКУ ДЛЯ УДАРІВ ---
        st.write("**Темп гри (Активність команд)**")
        st.caption("Введіть середню кількість ударів за матч для кожної команди. Симулятор сам вирахує кількість ігрових епізодів.")
        
        col1, col2 = st.columns(2)
        with col1:
            my_shots = st.number_input("Ваші середні удари:", min_value=1, max_value=30, value=10, step=1)
        with col2:
            opp_shots = st.number_input("Удари суперника:", min_value=1, max_value=30, value=10, step=1)
            
        expected_total_shots = my_shots + opp_shots
        min_chances = int(expected_total_shots * 0.83)
        max_chances = int(expected_total_shots * 1.19)
        
        st.info(f"📊 Розрахований діапазон для рушія: від **{min_chances}** до **{max_chances}** ігрових епізодів.")

        st.markdown("---")
        st.write("**⚠️ Дисципліна (Середні порушення за матч)**")
        col_foul1, col_foul2 = st.columns(2)
        with col_foul1:
            my_fouls_input = st.number_input("Наші порушення:", min_value=0, value=3, step=1)
        with col_foul2:
            opp_fouls_input = st.number_input("Порушення суперника:", min_value=0, value=3, step=1)

        if st.button("🚀 Запустити Симуляцію", type="primary"):
            with st.spinner("Граємо віртуальні матчі... Це може зайняти деякий час ⏳"):
                
                my_eng, opp_eng, _, _ = lg.prepare_engine_stats(my_team_stats, opp_stats, i_am_home, opponent_home)
                
                if my_eng['possession'] == 0 or my_eng['shot_power'] == 0:
                    st.error(f"🚨 КРИТИЧНА ПОМИЛКА: Скіли гравців = 0! Парсер не зміг зайти в профілі.")
                    st.stop()
                
                opp_predicted = advice['opp_predicted_tactic']

                if "коммерч" in tourn_input.lower():
                    tourn_coef = 0.5
                else:
                    tourn_coef = 1.0

                # [ВИПРАВЛЕНО] Завжди використовуємо Тотальний Аналіз (4320 комбінацій)
                st.warning("⚠️ ШІ прораховує 4320 ваших комбінацій проти 4320 можливих тактик суперника. Зачекайте...")
                
                optimizer = me.TacticsOptimizer(
                    my_eng, opp_eng, 
                    opp_tactics_input=None, # None означає, що ШІ тестує проти всіх 4320 варіантів
                    min_c=min_chances, max_c=max_chances, 
                    tourn_coef=tourn_coef, 
                    my_fouls_avg=my_fouls_input, opp_fouls_avg=opp_fouls_input
                )

                # Запуск Монте-Карло
                top_tactics = optimizer.find_best_tactic()
                
                # ==========================================
                # ВИВІД РЕЗУЛЬТАТІВ ТОП-3
                # ==========================================
                cols = st.columns(3)
                for i, res in enumerate(top_tactics):
                    with cols[i]:
                        c = res['combo']
                        st.info(f"🏆 {i+1} МІСЦЕ\n\n**Шанс перемоги: {res['winrate']:.1f}%**")
                        st.markdown(f"🎯 **Прогноз рахунку: {res.get('most_likely_score', '0:0')}** *(ймовірність {res.get('score_prob', 0):.0f}%)*")
                        st.write(f"**Паси:** {c['pass_type']}")
                        st.write(f"**Стратегія:** {c['strat']}")
                        st.write(f"**Пресинг:** {c['press']}")
                        st.write(f"**В лінію:** {c['dens_in']}")
                        st.write(f"**Між лініями:** {c['dens_btwn']}")
                        st.write(f"**Тактика:** {c['tactic_val']}")
                        st.caption(f"Середні забиті голи: {res['avg_goals']:.2f}")

                best_tactic = top_tactics[0]['combo'] # Беремо знайдену ТОП-1 тактику
                
                print("\n" + "="*50)
                print("🏆 ПОКАЗОВИЙ МАТЧ ТОП-1 ТАКТИКИ ПРОТИ СУПЕРНИКА 🏆")
                print("="*50)
                
                # Створюємо стадіон на 1 матч
                demo_engine = me.ButsaMatchEngine(
                    my_eng, opp_eng, 
                    best_tactic, opp_predicted, 
                    min_chances, max_chances, tourn_coef,
                    my_fouls_avg=my_fouls_input,    # <--- [НОВЕ]
                    opp_fouls_avg=opp_fouls_input   # <--- [НОВЕ]
                )
                
                # Запускаємо з принтом у консоль!
                demo_engine.simulate_match(debug_mode=True)
                print("="*50 + "\n")
