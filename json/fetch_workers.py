import requests
import os
import re
from data import countries


# Створюємо папку для збереження відповідей
os.makedirs("json/responses", exist_ok=True)


def fetch_and_save_country_data(country_id):
    url = f"https://www.butsa.ru/stats/countries_{country_id}.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text  # Отримуємо відповідь як текст

        # Заміна порожніх значень "nextBonusPoints" на 0
        # Шукаємо: "nextBonusPoints": null або відсутнє значення
        content = re.sub(r'"nextBonusPoints"\s*:\s*,', '"nextBonusPoints": 0,', content)

        # Зберігаємо оновлений текст у файл
        with open(
            f"json/responses/country_{country_id}.txt", "w", encoding="utf-8"
        ) as f:
            f.write(content)
        print(f"Дані для країни {country_id} збережено")
    except requests.exceptions.RequestException as e:
        print(f"Помилка при отриманні даних для країни {country_id}: {e}")


# Приклад: зберігаємо дані для кількох країн
for country_id in countries.keys():
    fetch_and_save_country_data(country_id)
