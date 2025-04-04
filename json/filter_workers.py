from pyspark.sql import SparkSession
import requests
import json
import os
from data import countries

# Папка з текстовими файлами
input_folder = "json/responses"
output_folder = "json/cleaned_responses"

# Створюємо папку для очищених файлів
os.makedirs(output_folder, exist_ok=True)


def clean_json_file(file_path, output_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Перевіряємо, чи це валідний JSON
        data = json.loads(content)
        # Якщо JSON валідний, зберігаємо його в очищену папку
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Файл {file_path} успішно очищено та збережено.")
    except json.JSONDecodeError as e:
        print(f"Помилка при розборі JSON у файлі {file_path}: {e}")
        # Зберігаємо некоректний файл для подальшого аналізу
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Некоректний файл збережено без змін у {output_path}.")


# Перевіряємо всі файли в папці
for file_name in os.listdir(input_folder):
    if file_name.endswith(".txt"):
        input_path = os.path.join(input_folder, file_name)
        output_path = os.path.join(output_folder, file_name)
        clean_json_file(input_path, output_path)

# Ініціалізація SparkSession
spark = SparkSession.builder.appName("Process Cleaned JSON Data").getOrCreate()

# Папка з очищеними файлами
cleaned_folder = "json/cleaned_responses"

# Завантаження даних у Spark
data_list = []

for file_name in os.listdir(cleaned_folder):
    if file_name.endswith(".txt"):
        file_path = os.path.join(cleaned_folder, file_name)
        try:
            with open(file_path, "r") as f:
                data = json.load(f)  # Завантажуємо JSON
                # Додаємо гравців до списку
                for team_id, team_data in data.get("teams", {}).items():
                    for player_id, player_data in team_data.get("players", {}).items():
                        player_data["team_id"] = (
                            f"https://www.butsa.ru/roster/{team_id}"
                        )
                        player_data["country_id"] = data["id"]
                        player_data["country_name"] = countries.get(
                            player_data["country"]["id"]
                        )
                        player_data["club"] = team_data["name"]
                        del player_data["country"]
                        data_list.append(player_data)
        except json.JSONDecodeError as e:
            print(f"Пропускаємо файл {file_path} через помилку JSON: {e}")

# Створюємо DataFrame зі списку гравців
players_df = spark.createDataFrame(data_list)

# Фільтруємо гравців за критеріями
filtered_players = players_df.filter(
    (players_df.aspectName == "Работяга")
    & (players_df.age == 16)
    & (players_df.talent == 4)
)

# Виводимо результати
filtered_players.printSchema()

# Зберігаємо результати у файл
filtered_players.write.json("json/filtered_players.json")

# Завершуємо роботу Spark
spark.stop()
