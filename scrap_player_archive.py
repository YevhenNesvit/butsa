from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import os
import dotenv
from bs4 import BeautifulSoup

dotenv.load_dotenv()


def get_players_row_data(age_from, age_to, talent_from, talent_to, date_from):

    service = Service("/home/yevhen/chromedriver-linux64/chromedriver")

    driver = webdriver.Chrome(service=service)

    driver.get(
        "https://www.butsa.ru/xml/players/transfer.php?&type=players/transfer&act=history"
    )

    username_input = driver.find_element(By.NAME, "auth_name")
    password_input = driver.find_element(By.NAME, "auth_pass")

    username_input.send_keys(os.getenv("USERNAME"))
    password_input.send_keys(os.getenv("PASSWORD"))

    login_button = driver.find_element(By.NAME, "imageField")
    login_button.click()

    age_from_input = driver.find_element(By.NAME, "Age_1")
    age_from_input.send_keys(age_from)

    age_to_input = driver.find_element(By.NAME, "Age_2")
    age_to_input.send_keys(age_to)

    talent_from_input = driver.find_element(By.NAME, "Talent_1")
    talent_from_input.send_keys(talent_from)

    talent_to_input = driver.find_element(By.NAME, "Talent_2")
    talent_to_input.send_keys(talent_to)

    date_from_input = driver.find_element(By.NAME, "lottime")
    date_from_input.send_keys(date_from)

    button = driver.find_element(By.CLASS_NAME, "button")
    button.click()

    result = driver.page_source

    driver.quit()

    return result


def get_players_clean_data(age_from, age_to, talent_from, talent_to, date_from):
    row_data = get_players_row_data(age_from, age_to, talent_from, talent_to, date_from)
    soup = BeautifulSoup(row_data, "html.parser")

    players_data = []

    # Збираємо дані для кожної команди
    players_td = soup.find("td", id="mainarea_rigth")
    players_table = players_td.find("table", class_="maintable")
    players_thead = players_table.find("tbody")

    for row in players_thead.find_all("tr"):
        tds = row.find_all("td")
        td_links = [td.find("a")["href"] if td.find("a") else None for td in tds]
        td_texts = [td.get_text(strip=True) for td in tds]

        players_data.append(td_texts + td_links[0:1])

    return players_data[:-1]


print(get_players_clean_data("16", "16", "4", "4", "2024-12-13"))
