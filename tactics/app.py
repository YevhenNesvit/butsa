import streamlit as st
import json
import os
import pandas as pd
from fetcher import scrape_roster, get_soup
from tactics_logic import (
    calculate_real_power, 
    solve_cap_puzzle, 
    analyze_threats,
    calculate_tactics
)

# ==============================================================================
# НАЛАШТУВАННЯ ІНТЕРФЕЙСУ
# ==============================================================================

CONFIG_FILE = 'config.json'

def load_config():
    """Завантажує конфігурацію з файлу."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "cookie": "", "my_def": 0, "my_mid": 0, "my_att": 0, "my_stam": 100,
        "cap": 0, "tourn": "Коммерческие турниры"
    }

def save_config(config):
    """Зберігає конфігурацію у файл."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# Доступні формації
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

# ==============================================================================
# ГОЛОВНА СТОРІНКА
# ==============================================================================

st.set_page_config(page_title="Butsa.pro Tactics", layout="wide")
st.title("⚽ Butsa.pro Tactical Assistant")

config = load_config()

# --- БІЧНА ПАНЕЛЬ НАЛАШТУВАНЬ ---
with st.sidebar:
    st.header("⚙️ Налаштування")
    
    cookie_input = st.text_input("PHPSESSID (Cookie)", value=config.get("cookie", ""), type="password")
    
    st.subheader("Твоя Команда (Real Power)")
    col1, col2 = st.columns(2)
    my_def = col1.number_input("Defense", value=config.get("my_def", 0))
    my_mid = col2.number_input("Midfield", value=config.get("my_mid", 0))
    col3, col4 = st.columns(2)
    my_att = col3.number_input("Attack", value=config.get("my_att", 0))
    my_stam = col4.number_input("Stamina", value=config.get("my_stam", 100))
    
    st.subheader("Турнір")
    cap_input = st.number_input("Ліміт сили (Cap)", value=config.get("cap", 0))
    tourn_input = st.text_input("Назва турніру", value=config.get("tourn", "Коммерческие турниры"))
    
    opponent_home = st.checkbox("Суперник грає вдома?", value=False)

    st.write("---")
    st.caption("Примусовий вибір схеми")
    formation_options = ["Авто (Підібрати найкращу)"] + list(ALL_FORMATIONS.keys())
    selected_formation_name = st.selectbox("Схема суперника:", formation_options)
    
    if st.button("Зберегти налаштування"):
        new_conf = {
            "cookie": cookie_input, "my_def": my_def, "my_mid": my_mid, 
            "my_att": my_att, "my_stam": my_stam, "cap": cap_input, "tourn": tourn_input
        }
        save_config(new_conf)
        st.success("Налаштування збережено!")

# --- ОСНОВНА ЧАСТИНА ---

roster_url = st.text_input("🔗 Посилання на ростер суперника (https://butsa.pro/roster/ID/)", "")

if st.button("🚀 Аналізувати", type="primary"):
    if not roster_url or not cookie_input:
        st.error("Введіть URL ростера та Cookie!")
    else:
        progress_bar = st.progress(0, text="Починаємо...")
        
        # Callback для оновлення прогресу
        def update_progress(ratio, current, total):
            progress_bar.progress(ratio, text=f"Сканування гравців {current}/{total}")
        
        try:
            # 1. Скрапінг
            raw_roster = scrape_roster(roster_url, cookie_input, tourn_input, update_progress)
            
            if not raw_roster:
                st.error("Не вдалося отримати дані. Перевір Cookie або URL.")
            else:
                progress_bar.progress(100, text="Аналіз тактики...")
                
                # 2. Розрахунок Real Power для суперника
                for p in raw_roster:
                    p['real_power'] = calculate_real_power(p, opponent_home)

                formations_to_analyze = {}
                if selected_formation_name == "Авто (Підібрати найкращу)":
                    formations_to_analyze = ALL_FORMATIONS
                else:
                    formations_to_analyze = {selected_formation_name: ALL_FORMATIONS[selected_formation_name]}

                # 3. Підбір схеми
                results = []
                for fname, fstruct in formations_to_analyze.items():
                    res = solve_cap_puzzle(raw_roster, fstruct, cap_input)
                    c, w = analyze_threats(res['squad_dict'])
                    total_mins = sum(p['minutes'] for p in res['squad_list'])
                    results.append({'name': fname, 'res': res, 'c': c, 'w': w, 'total_mins': total_mins})

                results.sort(key=lambda x: (x['total_mins'], x['res']['real_total']), reverse=True)
                best = results[0]
                opp_stats = best['res']

                # 4. ВІЗУАЛІЗАЦІЯ
                st.divider()
                col_res1, col_res2 = st.columns(2)
                
                with col_res1:
                    st.success(f"🏆 Прогноз: **{best['name']}**")

                    if selected_formation_name != "Авто (Підібрати найкращу)":
                        st.caption("(Схему зафіксовано вручну)")

                    st.write(f"Досвід (хв): **{best['total_mins']}**")
                    st.write(f"Склад: **{opp_stats['nominal']}/{cap_input}** (Real: {opp_stats['real_total']:.1f})")
                    
                    st.write("---")
                    st.caption("Основа:")
                    s = opp_stats['squad_dict']
                    st.write(f"**GK:** {', '.join([p['name'] for p in s['gk']])}")
                    st.write(f"**DEF:** {', '.join([p['name'] for p in s['def']])}")
                    st.write(f"**MID:** {', '.join([p['name'] for p in s['mid']])}")
                    st.write(f"**ATT:** {', '.join([p['name'] for p in s['att']])}")

                # 5. ЛОГІКА ПОРАД
                my_team = {'def': my_def, 'mid': my_mid, 'att': my_att, 'stamina': my_stam}
                tactics = calculate_tactics(my_team, opp_stats, opponent_home, best)

                with col_res2:
                    st.info("🧠 Тренерські рішення")
                    st.markdown(f"**Баланс:** Ми {tactics['my_tot']} vs {tactics['opp_tot']:.0f} (Diff: {tactics['diff']:.1f})")
                    st.markdown(f"**Центр:** Ratio {tactics['mid_ratio']:.2f}")
                    
                    table_data = [
                        ["Стратегія", tactics['strat'].upper(), tactics['strat_reason']],
                        ["Паси", tactics['pass_type'].upper(), tactics['pass_reason']],
                        ["Тактика", f"{tactics['tactic_val']:.0f}", tactics['t_desc']],
                        ["Щільн. в лінії", f"{tactics['dens_in']:.0f}", tactics['dr_in_reason']],
                        ["Щільн. між лін.", f"{tactics['dens_btwn']:.0f}", tactics['dr_bt_reason']],
                        ["Пресинг", tactics['press'], tactics['press_reason']]
                    ]
                    df_advice = pd.DataFrame(table_data, columns=["Параметр", "Значення", "Логіка"])
                    st.table(df_advice)
                    
        except Exception as e:
            st.error(f"Помилка: {e}")
        finally:
            progress_bar.empty()
