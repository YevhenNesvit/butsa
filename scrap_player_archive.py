from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import os
import dotenv
from bs4 import BeautifulSoup
import pandas as pd

dotenv.load_dotenv()

service = Service("/home/yevhen/chromedriver-linux64/chromedriver")
driver = webdriver.Chrome(service=service)
url = "https://www.butsa.ru/xml/players/transfer.php"


def login_and_get_cookies(driver, url):
    driver.get(url)

    username_input = driver.find_element(By.NAME, "auth_name")
    password_input = driver.find_element(By.NAME, "auth_pass")

    username_input.send_keys(os.getenv("USERNAME"))
    password_input.send_keys(os.getenv("PASSWORD"))

    login_button = driver.find_element(By.NAME, "imageField")
    login_button.click()

    # Отримуємо cookies після авторизації
    cookies = driver.get_cookies()

    return cookies


def get_players_row_data(
    url, driver, pages, age_from, age_to, talent_from, talent_to, date_from
):

    cookies = login_and_get_cookies(driver, url)

    result = ""

    # Додаємо cookies
    for cookie in cookies:
        driver.add_cookie(cookie)

    for i in range(pages):
        driver.get(
            f"{url}?page={i + 1}&type=players/transfer&act=history&Age_1={age_from}&Age_2={age_to}&Talent_1={talent_from}&Talent_2={talent_to}&lottime={date_from}"
        )

        result += driver.page_source

    return result


def get_players_clean_data(
    url, driver, pages, age_from, age_to, talent_from, talent_to, date_from
):
    row_data = get_players_row_data(
        url, driver, pages, age_from, age_to, talent_from, talent_to, date_from
    )

    soup = BeautifulSoup(row_data, "html.parser")

    players_data = []

    players_td_list = soup.find_all("td", id="mainarea_rigth")

    for players_td in players_td_list:
        players_table = players_td.find("table", class_="maintable")
        if not players_table:
            continue  # Якщо таблиці немає, пропускаємо

        players_thead = players_table.find("tbody")
        if not players_thead:
            continue

        for row in players_thead.find_all("tr"):
            tds = row.find_all("td")
            td_links = [td.find("a")["href"] if td.find("a") else None for td in tds]
            td_texts = [td.get_text(strip=True) for td in tds]

            players_data.append(td_texts + td_links[0:1])

    return players_data[:-1]


data = get_players_clean_data(url, driver, 15, "16", "16", "4", "4", "2024-11-12")


def get_players(driver, data):

    players = []

    for player in data:
        personal_url = "https://butsa.ru" + player[-1]
        driver.get(personal_url)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        worker_element = soup.find("a", class_="green-help")
        if worker_element and worker_element.get_text() == "Работяга":
            players.append(player)

    players.append(data[0])
    return sorted(players, key=lambda x: x[1])


def to_dataframe(driver, data):

    data = get_players(driver, data)

    df = pd.DataFrame(data=data[:-1], columns=data[-1])
    df = df.iloc[:, :-1]
    df.to_csv("worker_players_4.csv", index=False)


to_dataframe(driver, data)
