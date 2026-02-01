import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import os, dotenv

dotenv.load_dotenv()

session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
    "Referer": "https://butsa.pro/",
    "Origin": "https://butsa.pro"
}
session.headers.update(headers)

login_data = {
    "auth_name": os.getenv("USERNAME"),
    "auth_pass": os.getenv("PASSWORD"),
    "imageField": "Login"
}

resp = session.post(
    "https://butsa.pro/xml/players/transfer.php",
    data=login_data,
    allow_redirects=True
)

print("LOGIN STATUS:", resp.status_code)
print("COOKIES:", session.cookies)

# 3. Збір гравців — поліпшена версія з надійними умовами зупинки
def scrape_players(session, save_every=1):
    all_players = []
    seen_ids = set()
    page = 1
    empty_page_streak = 0
    repeat_page_streak = 0
    max_pages = 2000

    os.makedirs("json/responses", exist_ok=True)

    while True:
        if page > max_pages:
            print("🚫 max_pages досягнуто")
            break

        url_page = f"https://butsa.pro/xml/players/transfer.php?page={page}&type=players/transfer&act=select"
        print(f"🔍 Page {page}")

        r = session.get(url_page, timeout=15)

        if r.status_code != 200:
            print(f"⚠️ HTTP {r.status_code}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", class_="maintable")

        if not table:
            empty_page_streak += 1
            repeat_page_streak += 1
        else:
            links = table.find_all("a", href=True)
            page_players = []

            for a in links:
                href = a["href"]
                if href.startswith("/players/"):
                    pid = href.split("/players/")[-1].strip("/")
                    name = a.get_text(strip=True)
                    page_players.append({"id": pid, "name": name})

            if not page_players:
                empty_page_streak += 1
                repeat_page_streak += 1
            else:
                new_players = [p for p in page_players if p["id"] not in seen_ids]

                if not new_players:
                    repeat_page_streak += 1
                    empty_page_streak = 0
                else:
                    for p in new_players:
                        all_players.append(p)
                        seen_ids.add(p["id"])

                    empty_page_streak = 0
                    repeat_page_streak = 0
                    print(f"✅ Нових: {len(new_players)}, всього: {len(all_players)}")

        if empty_page_streak >= 2 or repeat_page_streak >= 3:
            print("🚫 Умова зупинки")
            break

        if page % save_every == 0:
            with open(f"json/responses/progress_{page}.json", "w", encoding="utf-8") as f:
                json.dump(all_players, f, ensure_ascii=False, indent=2)

        page += 1
        time.sleep(0.5)

    return all_players

# Запуск
if __name__ == "__main__":
    players = scrape_players(session)

    df = pd.DataFrame(players).drop_duplicates("id")
    df.to_csv("json/responses/transfer_players.csv", index=False, encoding="utf-8-sig")
