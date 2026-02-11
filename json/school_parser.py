import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import dotenv
import os
from tqdm import tqdm

dotenv.load_dotenv()

# --- Налаштування Selenium ---
driver = webdriver.Chrome()  # або Firefox, Edge
wait = WebDriverWait(driver, 10)  # чекати до 10 секунд

# --- Логін на сайті ---
BASE_URL = "https://www.butsa.pro"
driver.get(f"{BASE_URL}")

# Тут введи свої дані логіну
driver.find_element(By.NAME, "auth_name").send_keys(os.getenv("USERNAME"))
driver.find_element(By.NAME, "auth_pass").send_keys(os.getenv("PASSWORD"))
driver.find_element(By.NAME, "imageField").click()

# --- Зчитування team_id ---
df_all = pd.read_csv("json/responses/all_players.csv")  # колонка має назву 'team_id'
team_ids = df_all['team_id'].unique()    # унікальні ID команд

def parse_school_roster(driver, team_id, wait):
    url = f"https://www.butsa.pro/xml/school/roster.php?id={team_id}"
    driver.get(url)

    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "maintable")))
    tables = driver.find_elements(By.CLASS_NAME, "maintable")

    if len(tables) < 3:
        raise Exception("Немає таблиці ДЮСШ")

    table = tables[-1]  # ОСТАННЯ maintable
    tbody = table.find_element(By.TAG_NAME, "tbody")
    rows = tbody.find_elements(By.TAG_NAME, "tr")

    players = []

    for row in rows:
        tds = row.find_elements(By.TAG_NAME, "td")
        if len(tds) < 7:
            continue

        # імʼя
        name_el = tds[1].find_elements(By.TAG_NAME, "a")
        if not name_el:
            continue
        name = name_el[0].text.strip()
        if name == "Игрок":
            continue

        # громадянство (img title, але може бути відсутній)
        citizenship = ""
        imgs = tds[2].find_elements(By.TAG_NAME, "img")
        if imgs:
            citizenship = imgs[0].get_attribute("title").strip()

        position = tds[3].text.strip()
        age = tds[4].text.strip()
        skill = tds[5].text.strip().replace(",", ".")
        talent = tds[6].text.strip().replace(",", ".")

        players.append({
            "team_id": team_id,
            "name": name,
            "country": citizenship,
            "position": position,
            "age": age,
            "skill": skill,
            "talent": talent
        })

    return players

all_players = []

for team_id in tqdm(team_ids):
    try:
        players = parse_school_roster(driver, team_id, wait)
        all_players.extend(players)
        print(f"[{team_id}] OK: {len(players)} гравців")
    except Exception as e:
        print(f"[{team_id}] ❌ {e}")

driver.quit()

pd.DataFrame(all_players).to_csv(
    "json/responses/school_players.csv",
    index=False,
    encoding="utf-8"
)

