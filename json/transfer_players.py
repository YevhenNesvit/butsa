from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import os
import dotenv
import pandas as pd
import time
import json

dotenv.load_dotenv()

# 1. Ініціалізація браузера
service = Service("/home/yevhen/chromedriver-linux64/chromedriver")
driver = webdriver.Chrome(service=service)
url = "https://butsa.pro/xml/players/transfer.php"

# 2. Логін (як у тебе)
def login(driver):
    driver.get(url)
    username_input = driver.find_element(By.NAME, "auth_name")
    password_input = driver.find_element(By.NAME, "auth_pass")
    username_input.send_keys(os.getenv("USERNAME"))
    password_input.send_keys(os.getenv("PASSWORD"))
    login_button = driver.find_element(By.NAME, "imageField")
    login_button.click()
    time.sleep(3)

# 3. Збір гравців — поліпшена версія з надійними умовами зупинки
def scrape_players(driver, save_every=1):
    all_players = []
    seen_ids = set()            # всі зібрані id
    page = 1
    empty_page_streak = 0       # підряд порожніх сторінок
    repeat_page_streak = 0      # підряд сторінок без НОВИХ id
    max_pages = 2000            # жорсткий ліміт (постав менше, якщо хочеш)
    retries_on_error = 0
    max_retries = 3

    os.makedirs("json/responses", exist_ok=True)

    while True:
        if page > max_pages:
            print(f"🚫 Досягнуто max_pages ({max_pages}) — зупинка.")
            break

        url_page = f"https://butsa.pro/xml/players/transfer.php?page={page}&type=players/transfer&act=select"
        print(f"🔍 Обробка сторінки {page} -> {url_page}")
        try:
            driver.get(url_page)
            time.sleep(1.5)  # даємо сторінці підвантажитись

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            table = soup.find("table", class_="maintable")
            if not table:
                print("⚠️ Таблиця не знайдена на сторінці.")
                empty_page_streak += 1
                repeat_page_streak += 1
            else:
                # знаходимо лише <a href="/players/...">
                links = table.find_all("a", href=True)
                page_players = []
                for a in links:
                    href = a["href"]
                    if href.startswith("/players/"):
                        pid = href.split("/players/")[-1].strip("/")
                        name = a.get_text(strip=True)
                        page_players.append({"id": pid, "name": name})

                # Якщо на сторінці немає ні одного такого лінку:
                if not page_players:
                    print("📭 На сторінці немає записів з /players/.")
                    empty_page_streak += 1
                    repeat_page_streak += 1
                else:
                    # відфільтровуємо тільки нові id
                    new_players = [p for p in page_players if p["id"] not in seen_ids]

                    if not new_players:
                        # Є записи, але всі вони вже зібрані раніше
                        repeat_page_streak += 1
                        empty_page_streak = 0
                        print(f"ℹ️ На сторінці {page} немає НОВИХ id (repeat streak {repeat_page_streak}).")
                    else:
                        # Додати нові
                        for p in new_players:
                            all_players.append(p)
                            seen_ids.add(p["id"])
                        print(f"✅ Знайдено {len(page_players)} на сторінці, нових {len(new_players)}. Всього зібрано: {len(all_players)}")
                        # скидаємо лічильники
                        empty_page_streak = 0
                        repeat_page_streak = 0

            # Умови зупинки:
            # - якщо X порожніх сторінок підряд
            # - або Y сторінок підряд без нових id (повторення)
            if empty_page_streak >= 2:
                print(f"🚫 {empty_page_streak} порожніх сторінки(ів) підряд — припиняю.")
                break
            if repeat_page_streak >= 3:
                print(f"🚫 {repeat_page_streak} сторінки(ів) підряд без нових id — припиняю.")
                break

            # Збереження прогресу після кожної сторінки (контролюється save_every)
            if page % save_every == 0:
                tmp_path = f"json/responses/transfer_players_progress_page_{page}.json"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(all_players, f, ensure_ascii=False, indent=2)
                print(f"💾 Проміжне збереження: {tmp_path}")

            # інкремент і невелика затримка
            page += 1
            time.sleep(1.0)
            retries_on_error = 0  # успішна сторінка — скидаємо лічильник ретраїв

        except Exception as e:
            print(f"⚠️ Помилка при обробці сторінки {page}: {e}")
            retries_on_error += 1
            if retries_on_error > max_retries:
                print("🚫 Перевищено max retries — зупинка.")
                break
            else:
                wait = 3 * retries_on_error
                print(f"⏳ Чекаю {wait}s і пробую ще раз ({retries_on_error}/{max_retries})...")
                time.sleep(wait)
                continue

    # фінальне збереження
    print(f"✅ Завершено. Збережено {len(all_players)} гравців.")
    return all_players

# Запуск
if __name__ == "__main__":
    login(driver)
    players = scrape_players(driver, save_every=1)
    # також можна зберегти у CSV
    df = pd.DataFrame(players)
    df = df.drop_duplicates(subset=['id'])
    df.to_csv("json/responses/transfer_players.csv", index=False, encoding="utf-8-sig")
    driver.quit()
