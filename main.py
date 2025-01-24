import os
import time
from urllib.parse import urlparse, urlunparse
import requests
import telebot
from bs4 import BeautifulSoup
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Массив URL поиска на Авито
AVITO_URLS = [
    "https://www.avito.ru/all/tovary_dlya_kompyutera/komplektuyuschie/materinskie_platy-ASgBAgICAkTGB~pm7gnOZw?cd=1&q=am4&s=104",
    "https://www.avito.ru/all/tovary_dlya_kompyutera?f=ASgBAQECAUTyig6kgpQBAUCCoRI1DFJ5emVuIDUgMjYwMApyeXplbiAyNjAwBDI2MDABRcaaDBR7ImZyb20iOjUwMDAsInRvIjowfQ&s=104",
    "https://www.avito.ru/all/tovary_dlya_kompyutera/komplektuyuschie/videokarty-ASgBAgICAkTGB~pm7gmmZw?cd=1&f=ASgBAQICAkTGB~pm7gmmZwFAgqESJQxndHggMTA2MCA2Z2IEMTA2MA&s=104",
    "https://www.avito.ru/all/tovary_dlya_kompyutera/komplektuyuschie/videokarty-ASgBAgICAkTGB~pm7gmmZw?cd=1&f=ASgBAgECAkTGB~pm7gmmZwJFxpoMGHsiZnJvbSI6NTAwMCwidG8iOjE0MDAwfYKhEgYiMTY2MCI&s=104",
    "https://www.avito.ru/all/tovary_dlya_kompyutera?cd=1&f=ASgCAgECAkXGmgwYeyJmcm9tIjo1MDAwLCJ0byI6MTgwMDB9gqESCyJpMy0xMjEwMGYi&q=комплект+i3+12100f&s=104"
]

# Файл для хранения обработанных ссылок
LINKS_FILE = "processed_links.txt"

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Заготовленное сообщение продавцу
PREDEFINED_MESSAGE = "Здравствуйте! Меня заинтересовало ваше объявление. Оно ещё актуально?"

# Словарь для хранения данных объявлений
ad_data = {}


def load_processed_links():
    """
    Загружает уже обработанные ссылки из файла.
    """
    if not os.path.exists(LINKS_FILE):
        return set()

    with open(LINKS_FILE, "r") as file:
        links = file.read().splitlines()
    return set(links)


def save_processed_link(link):
    """
    Добавляет обработанную ссылку в файл.
    """
    with open(LINKS_FILE, "a") as file:
        file.write(link + "\n")


def normalize_url(url):
    """
    Убирает параметры из ссылки, чтобы избежать дубликатов.
    """
    parsed = urlparse(url)
    normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    return normalized

def extract_data(url):
    """
    Функция для извлечения данных с Avito.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers, timeout=50)
    if response.status_code != 200:
        raise Exception(f"HTTP ошибка {response.status_code}")

    soup = BeautifulSoup(response.content, "html.parser")
    items = []

    # Парсим товары с Avito
    for item in soup.find_all("div", {"data-marker": "item"})[:15]:
        try:
            title = item.find("h3", {"itemprop": "name"}).text.strip()
            price = item.find("meta", {"itemprop": "price"})["content"]
            link = "https://www.avito.ru" + item.find("a", {"itemprop": "url"})["href"]
            item_id = item["data-item-id"]
            normalized_link = normalize_url(link)  # Нормализуем ссылку

            # Извлечение даты публикации
            date_tag = item.find("p", {"data-marker": "item-date"})
            date_posted = date_tag.text.strip() if date_tag else "Дата не указана"

            # Извлечение рейтинга продавца
            seller_rating_tag = item.find("span", {"data-marker": "seller-rating/score"})
            seller_rating = seller_rating_tag.text.strip() if seller_rating_tag else "Рейтинг не указан"

            items.append({
                "id": item_id,
                "title": title,
                "price": f"{price} ₽",
                "link": normalized_link,
                "date_posted": date_posted,
                "seller_rating": seller_rating
            })
        except Exception as e:
            print(f"Ошибка парсинга элемента: {e}")
            continue

    return items


def send_telegram_message(item):
    """
    Функция для отправки сообщения в Telegram с кнопкой.
    """
    try:
        # Сохраняем данные объявления в глобальный словарь
        ad_data[item["id"]] = item["link"]

        # Создаём клавиатуру с кнопкой
        markup = InlineKeyboardMarkup()
        contact_button = InlineKeyboardButton(
            text="Написать продавцу",
            callback_data=f"contact_{item['id']}"  # Передаём только ID объявления
        )
        markup.add(contact_button)



        # Отправляем сообщение с кнопкой
        message = (
            f"*{item['title']}*\n"
            f"Цена: {item['price']}\n"
            f"Дата публикации: {item['date_posted']}\n"
            f"Рейтинг продавца: {item['seller_rating']}\n"
            f"[Ссылка на объявление]({item['link']})"
        )
        bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Ошибка отправки сообщения в Telegram: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("contact_"))
def handle_contact_button(call):
    """
    Обработчик нажатий на кнопку "Написать продавцу".
    """
    try:
        # Извлекаем ID объявления из callback_data
        ad_id = call.data.replace("contact_", "")
        ad_link = ad_data.get(ad_id, "Ссылка не найдена")

        # Формируем сообщение продавцу
        message = f"Предзаполненное сообщение: {PREDEFINED_MESSAGE}\nВы можете связаться с продавцом по ссылке: {ad_link}"

        # Отправляем сообщение пользователю
        bot.send_message(chat_id=call.message.chat.id, text=message)
        bot.answer_callback_query(call.id, "Сообщение отправлено!")
    except Exception as e:
        print(f"Ошибка обработки кнопки: {e}")


def main():
    """
    Основная логика работы скрипта.
    """
    print("Скрипт запущен. Ожидание новых объявлений...")
    processed_links = load_processed_links()  # Загружаем обработанные ссылки из файла

    url_index = 0  # Индекс для прохода по массиву ссылок
    while True:
        try:
            # Получаем текущую ссылку из массива
            current_url = AVITO_URLS[url_index]
            print(f"Обработка URL: {current_url}")

            # Извлекаем данные с Avito
            items = extract_data(current_url)

            for item in items:
                normalized_link = normalize_url(item["link"])  # Нормализуем ссылку
                if normalized_link not in processed_links:
                    send_telegram_message(item)  # Отправляем сообщение в Telegram
                    print(f"Запрос отправлен! Объявление: {item['title']}")
                    save_processed_link(normalized_link)  # Сохраняем нормализованную ссылку в файл
                    processed_links.add(normalized_link)  # Добавляем в локальный список

            # Переходим к следующей ссылке в массиве, если дошли до конца - начинаем с первой
            url_index = (url_index + 1) % len(AVITO_URLS)

            # Ждём 60 секунд перед следующим запросом
            time.sleep(60)

        except requests.exceptions.RequestException as e:
            print(f"Ошибка HTTP-запроса: {e}")
            time.sleep(60)  # Повторяем через 60 секунд
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            time.sleep(60)


if __name__ == "__main__":
    # Запускаем основную функцию парсинга в отдельном потоке
    import threading

    parser_thread = threading.Thread(target=main)
    parser_thread.start()

    # Запускаем обработку сообщений бота
    bot.polling(none_stop=True)