import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
import random


class KitkaParserFinal:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
        self.data = []

        if not os.path.exists('images'):
            os.makedirs('images')

    def get_soup(self, url):
        try:
            time.sleep(random.uniform(0.5, 1.0))
            response = self.session.get(url, timeout=15)
            # Якщо сторінки немає (404), повертаємо None - це сигнал для зупинки
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException:
            # Будь-яка помилка запиту теж може означати кінець
            return None

    def clean_text(self, text):
        if text:
            text = text.replace('\xa0', ' ').replace('\n', ' ')
            return ' '.join(text.split())
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
            safe_name = re.sub(r'[\\/*?:"<>|]', "", product_name).replace(" ", "_")[:50]

            # Формат: "Індекс_Назва.jpg"
            filename = f"images/{index}_{safe_name}.jpg"

            if os.path.exists(filename):
                return filename

            response = self.session.get(img_url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                return filename
        except Exception:
            return None
        return None

    def get_product_details(self, product_url):
        info = {
            "attributes": {},
            "description": None,
            "stock_quantity": 0,
            "breadcrumbs": [],
            "gallery_urls": []
        }

        if not product_url:
            return info

        soup = self.get_soup(product_url)
        if not soup:
            return info

        # Характеристики
        attributes_table = soup.find('table', class_='shop_attributes')
        if attributes_table:
            rows = attributes_table.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    info["attributes"][self.clean_text(th.text)] = self.clean_text(td.text)

        # Опис
        desc_div = soup.find('div', class_='woocommerce-Tabs-panel--description')
        if desc_div:
            info["description"] = self.clean_text(desc_div.text)

        # Сток
        stock_p = soup.find('p', class_='stock')
        if stock_p:
            numbers = re.findall(r'\d+', stock_p.text)
            if numbers:
                info["stock_quantity"] = int(numbers[0])

        # Хлібні крихти
        breadcrumb_div = soup.find('div', class_='breadcrumb')
        if breadcrumb_div:
            links = breadcrumb_div.find_all('a')
            info["breadcrumbs"] = [self.clean_text(link.text) for link in links if link.text]

        # Галерея (посилання)
        gallery_slider = soup.find(class_='image-additional')
        if gallery_slider:
            images = gallery_slider.find_all('a', href=True)
            for img in images:
                url = img['href']
                if url.endswith(('.jpg', '.png', '.jpeg', '.webp')):
                    info["gallery_urls"].append(url)

        return info

    def parse_price(self, price_html):
        price_data = {"price": 0, "sale_price": None, "currency": "UAH"}
        if not price_html:
            return price_data

        ins_tag = price_html.find('ins')
        del_tag = price_html.find('del')

        def get_digits(t):
            clean = ''.join(re.findall(r'[\d.,]+', t))
            return float(clean.replace(',', '.')) if clean else 0

        if ins_tag and del_tag:
            price_data['price'] = get_digits(del_tag.text)
            price_data['sale_price'] = get_digits(ins_tag.text)
        else:
            price_data['price'] = get_digits(price_html.text)

        return price_data

    def run(self):
        page = 1
        global_index = 0

        print(f">>> Старт парсингу...")

        while True:
            url = f"{self.base_url}page/{page}/" if page > 1 else self.base_url
            print(f"\n--- Обробка сторінки № {page} ---")

            soup = self.get_soup(url)

            # --- ПЕРЕВІРКА НА КІНЕЦЬ СТОРІНОК ---
            if not soup:
                print(f"\n>>> Це була остання сторінка. Роботу завершено.")
                break

            products = soup.find_all(class_=lambda x: x and 'product' in x.split() and 'type-product' in x.split())

            if not products:
                print(f"\n>>> Це була остання сторінка (товарів більше немає). Роботу завершено.")
                break

            print(f"Знайдено товарів: {len(products)}")

            for product in products:
                global_index += 1
                try:
                    title_el = product.find('h2') or product.find('h3') or product.find(
                        class_='woocommerce-loop-product__title')
                    title = self.clean_text(title_el.text) if title_el else f"Product_{global_index}"

                    link_el = product.find('a', href=True)
                    product_link = link_el['href'] if link_el else None

                    prices = self.parse_price(product.find(class_='price'))

                    rating = 0.0
                    star_rating = product.find(class_='star-rating')
                    if star_rating:
                        rating_text = star_rating.get('aria-label') or star_rating.text
                        digits = re.findall(r"[\d\.]+", rating_text)
                        if digits: rating = float(digits[0])

                    details = self.get_product_details(product_link)

                    main_img_path = None
                    img_el = product.find('img')
                    if img_el:
                        img_url = img_el.get('data-lazy-src') or img_el.get('src')
                        main_img_path = self.download_image(img_url, title, global_index)

                    item = {
                        "id": global_index,
                        "name": title,
                        "category_path": details["breadcrumbs"],
                        "price_info": prices,
                        "stock_quantity": details["stock_quantity"],
                        "rating": rating,
                        "url": product_link,
                        "description": details["description"],
                        "specifications": details["attributes"],
                        "images": {
                            "main_image_path": main_img_path,
                            "gallery_urls": details["gallery_urls"]
                        }
                    }

                    self.data.append(item)
                    print(f" [{global_index}] + {title}")

                except Exception as e:
                    print(f"Помилка товару: {e}")
                    continue

            self.save_json()
            page += 1
            time.sleep(1)

        # Фінальне збереження після виходу з циклу
        self.save_json()

    def save_json(self):
        with open('products_data.json', 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    BASE_URL = "https://kitka-sonya.com/shop/"
    parser = KitkaParserFinal(BASE_URL)
    try:
        parser.run()
    except KeyboardInterrupt:
        print("\nРоботу зупинено користувачем. Дані збережено.")
        parser.save_json()