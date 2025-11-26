import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re


class KitkaParser:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.data = []

        # Створення папки для картинок
        if not os.path.exists('images'):
            os.makedirs('images')

    def get_soup(self, url):
        try:
            response = self.session.get(url, timeout=10)
            # Якщо сторінки не існує (наприклад page/100), сервер може повернути 404
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            print(f"Сторінка недоступна або закінчилась ({url}): {e}")
            return None

    def clean_text(self, text):
        if text:
            return text.strip()
        return None

    def download_image(self, img_url, product_name, index):
        if not img_url:
            return None

        try:
            if not img_url.startswith('http'):
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                else:
                    return None

            # Очищення імені файлу
            safe_name = re.sub(r'[\\/*?:"<>|]', "", product_name).replace(" ", "_")[:30]
            # Додаємо індекс до назви, щоб уникнути дублікатів (image_1.jpg, image_2.jpg)
            filename = f"images/{index}_{safe_name}.jpg"

            if os.path.exists(filename):
                return filename

            response = self.session.get(img_url, stream=True)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                return filename
        except Exception:
            return None
        return None

    def get_product_details(self, product_url):
        details = {}
        if not product_url:
            return details

        soup = self.get_soup(product_url)
        if not soup:
            return details

        # Спроба знайти таблицю характеристик
        attributes_table = soup.find('table', class_='shop_attributes')
        if attributes_table:
            rows = attributes_table.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    key = self.clean_text(th.text)
                    value = self.clean_text(td.text)
                    details[key] = value

        return details

    def parse_price(self, price_html):
        price_data = {"price": "0", "sale_price": None, "currency": "UAH"}
        if not price_html:
            return price_data

        ins_tag = price_html.find('ins')
        del_tag = price_html.find('del')

        # Функція для витягування тільки цифр
        def get_digits(t):
            return ''.join(re.findall(r'[\d.,]+', t))

        if ins_tag and del_tag:
            price_data['price'] = get_digits(del_tag.text)
            price_data['sale_price'] = get_digits(ins_tag.text)
        else:
            price_data['price'] = get_digits(price_html.text)

        return price_data

    def run(self):
        page = 1
        global_index = 0  # Лічильник для унікальності картинок

        while True:
            # Формуємо посилання: page/1/, page/2/ ...
            url = f"{self.base_url}page/{page}/" if page > 1 else self.base_url
            print(f"\n>>> Парсинг сторінки № {page}...")

            soup = self.get_soup(url)

            # Якщо soup немає (наприклад, 404 помилка), виходимо
            if not soup:
                print("Сторінки закінчилися (отримано 404 або помилку).")
                break

            # Шукаємо товари.
            # На цьому сайті товари мають клас 'product'
            products = soup.find_all(class_=lambda x: x and 'product' in x.split() and 'type-product' in x.split())

            if not products:
                print("Товарів на сторінці не знайдено. Зупинка.")
                break

            print(f"Знайдено товарів: {len(products)}")

            for product in products:
                global_index += 1
                try:
                    # 1. Назва (шукаємо заголовки h2/h3 або клас title)
                    title_el = product.find('h2') or product.find('h3') or product.find(
                        class_='woocommerce-loop-product__title')
                    title = self.clean_text(title_el.text) if title_el else "Unknown Product"

                    # 2. Посилання
                    link_el = product.find('a', href=True)
                    product_link = link_el['href'] if link_el else None

                    # 3. Ціна
                    price_html = product.find(class_='price')
                    prices = self.parse_price(price_html)

                    # 4. Рейтинг
                    rating = "0"
                    star_rating = product.find(class_='star-rating')
                    if star_rating:
                        rating = star_rating.get('aria-label') or star_rating.text
                        rating = self.clean_text(rating)

                    # 5. Картинка
                    img_path = None
                    img_el = product.find('img')
                    if img_el:
                        # Перебір можливих атрибутів src
                        img_url = img_el.get('data-lazy-src') or img_el.get('data-src') or img_el.get('src')
                        # Передаємо global_index для унікальності імені файлу
                        img_path = self.download_image(img_url, title, global_index)

                    # 6. Деталі (Рівень 3)
                    additional_info = {}
                    if product_link:
                        additional_info = self.get_product_details(product_link)

                    item = {
                        "name": title,
                        "original_price": prices['price'],
                        "sale_price": prices['sale_price'],
                        "rating": rating,
                        "url": product_link,
                        "local_image_path": img_path,
                        "additional_info": additional_info
                    }

                    self.data.append(item)
                    print(f" [{global_index}] Оброблено: {title}")

                except Exception as e:
                    print(f"Помилка елементу: {e}")
                    continue

            # Перехід на наступну сторінку
            page += 1
            # Робимо паузу, щоб не блокували
            time.sleep(1)

        self.save_json()

    def save_json(self):
        with open('products_data.json', 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)
        print(f"\nРоботу завершено! Всього товарів: {len(self.data)}")


if __name__ == "__main__":
    BASE_URL = "https://kitka-sonya.com/shop/"
    parser = KitkaParser(BASE_URL)
    parser.run()