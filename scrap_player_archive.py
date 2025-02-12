from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
import time

def get_players_archive_data(age_from, age_to, talent_from, talent_to):

    service = Service('/home/yevhen/chromedriver-linux64/chromedriver')

    # Створюємо екземпляр WebDriver з переданим сервісом
    driver = webdriver.Chrome(service=service)

    # Завантаження сторінки
    driver.get('https://www.butsa.ru/xml/players/transfer.php?page=all&type=players/transfer&act=history')

    username_input = driver.find_element(By.NAME, 'auth_name')  # Замість 'username' вказати правильний атрибут або id
    password_input = driver.find_element(By.NAME, 'auth_pass')  # Замість 'password' вказати правильний атрибут або id

    # Введемо логін і пароль
    username_input.send_keys('Yevhen')  # Замість 'your_username' вказати ваш логін
    password_input.send_keys('treize')

    login_button = driver.find_element(By.NAME, 'imageField')  # Замість 'login_button' вказати правильний id або клас
    login_button.click()

    # Якщо потрібно заповнити перше текстове поле:
    age_from = driver.find_element(By.NAME, 'Age_1')
    age_from.send_keys(age_from)

    # Якщо потрібно заповнити друге текстове поле:
    age_to = driver.find_element(By.NAME, 'Age_2')  # Замість 'search_input_2_id' вказуєте правильний id
    age_to.send_keys(age_to)

    talent_from = driver.find_element(By.NAME, 'Talent_1')  # Замість 'search_input_2_id' вказуєте правильний id
    talent_from.send_keys(talent_from)

    talent_to = driver.find_element(By.NAME, 'Talent_2')  # Замість 'search_input_2_id' вказуєте правильний id
    talent_to.send_keys(talent_to)

    # Знайдемо кнопку фільтрації і натискаємо її
    button = driver.find_element(By.CLASS_NAME, 'button')
    button.click()

    # Закриваємо браузер
    driver.quit()

    return driver.page_source

print(get_players_archive_data('16', '16', '4', '4'))
