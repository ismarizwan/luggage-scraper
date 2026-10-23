
import csv
import json
import logging
import random
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from curl_cffi import requests



# --- Amazon ---
AMAZON_KEYWORD = "luggage cover"
AMAZON_PAGES = 2


DARAZ_LINKS = [
    "https://www.daraz.pk/products/-i1963789132-s14041827533.html",
    "https://www.daraz.pk/products/18-30-i1953879256-s14015340501.html",
    "https://www.daraz.pk/products/1pc-20-30-i1953873367-s14015167451.html",
    "https://www.daraz.pk/products/-i1965792903-s14047056841.html",
]


SAMSONITE_LINKS = [
    "https://shop.samsonite.com/accessories/printed-luggage-cover---xl/91247XXXX.html",
]

RUN_AMAZON = True
RUN_DARAZ = True
RUN_SAMSONITE = True

CSV_FILE = "luggage_products.csv"
EXCEL_FILE = "luggage_report.xlsx"


TIMEOUT = 20
MAX_TRIES = 3
WAIT_BETWEEN_PAGES = (5, 10)
WAIT_BEFORE_RETRY = (10, 20)



logger = logging.getLogger("tracker")

FIELDS = [
    "date", "site", "item_id", "name", "brand",
    "price", "currency", "rating", "stock",
    "image_url", "product_url",
]

def wait_randomly(delay_range):
    seconds = random.uniform(*delay_range)
    logger.info("Waiting %.1f seconds...", seconds)
    time.sleep(seconds)

def to_number(text):
    if text is None: return None
    match = re.search(r"[\d,]+\.?\d*", str(text))
    if not match: return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None

def to_rating(text):
    if text is None: return None
    match = re.search(r"\d+(\.\d+)?", str(text))
    return float(match.group()) if match else None

def guess_currency(text, default="USD"):
    if not text: return default
    text = str(text).strip()
    code_match = re.match(r"([A-Za-z]{3})\b", text)
    if code_match: return code_match.group(1).upper()
    if text.startswith("$"): return "USD"
    if text.startswith("£"): return "GBP"
    if text.startswith("€"): return "EUR"
    if text.startswith("Rs"): return "PKR"
    return default

def download(url, check_function=None):
    for attempt in range(1, MAX_TRIES + 1):
        try:
            response = requests.get(url, impersonate="chrome", timeout=TIMEOUT)
            if response.status_code == 200:
                if check_function is None or check_function(response):
                    return response
            elif response.status_code in (401, 403):
                return None
        except Exception:
            pass
        if attempt < MAX_TRIES:
            wait_randomly(WAIT_BEFORE_RETRY)
    return None

def find_product_json(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "Product":
                return item
    return None

def get_offers(product):
    offers = product.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return offers if isinstance(offers, dict) else {}

def stock_from_offer(offer):
    availability = str(offer.get("availability", ""))
    if "InStock" in availability: return "In stock"
    if "OutOfStock" in availability: return "Out of stock"
    return None

def make_product(site, item_id, name, brand, price, currency, rating, stock, image_url, product_url):
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "site": site,
        "item_id": item_id,
        "name": name or "N/A",
        "brand": brand or "N/A",
        "price": price,
        "currency": currency,
        "rating": rating,
        "stock": stock or "Not shown",
        "image_url": image_url or "N/A",
        "product_url": product_url,
    }


def parse_amazon_product(product_div):
    asin = product_div.get("data-asin", "").strip()
    if not asin: return None

    title_tag = product_div.select_one("h2")
    name = title_tag.get_text(strip=True) if title_tag else None

    brand_tag = product_div.select_one("h5 span, span.a-size-base-plus.a-color-base")
    brand = brand_tag.get_text(strip=True) if brand_tag else None

    price_text = None
    price_tag = product_div.select_one("span.a-price span.a-offscreen")
    if price_tag:
        price_text = price_tag.get_text(strip=True)
    else:
        for tag in product_div.select("span.a-offscreen"):
            text = tag.get_text(strip=True)
            if re.search(r"\d", text):
                price_text = text
                break

    rating_tag = product_div.select_one("span.a-icon-alt")
    rating = to_rating(rating_tag.get_text(strip=True)) if rating_tag else None

    img_tag = product_div.select_one("img.s-image")
    image_url = img_tag.get("src") if img_tag else None

    text = product_div.get_text(" ", strip=True).lower()
    stock = "Not shown"
    if "currently unavailable" in text: stock = "Out of stock"
    else:
        match = re.search(r"only (\d+) left in stock", text)
        if match: stock = f"Only {match.group(1)} left"

    return make_product(
        site="amazon", item_id=asin, name=name, brand=brand,
        price=to_number(price_text), currency=guess_currency(price_text, "USD"),
        rating=rating, stock=stock, image_url=image_url,
        product_url=f"https://www.amazon.com/dp/{asin}",
    )

def scrape_amazon(keyword, pages):
    products = []
    seen_asins = set()
    for page in range(1, pages + 1):
        url = f"https://www.amazon.com/s?k={keyword.replace(' ', '+')}&page={page}"
        logger.info("Amazon page %d: %s", page, url)
        response = download(url, check_function=lambda r: "s-search-result" in r.text)
        if response is None: break
        soup = BeautifulSoup(response.text, "html.parser")
        for block in soup.select("div[data-component-type='s-search-result']"):
            product = parse_amazon_product(block)
            if product and product["item_id"] not in seen_asins:
                seen_asins.add(product["item_id"])
                products.append(product)
        if page < pages: wait_randomly(WAIT_BETWEEN_PAGES)
    return products



def daraz_item_id(url):
    match = re.search(r"-i(\d+)", url)
    return match.group(1) if match else "N/A"

def parse_daraz_product(product_data, url):
    offer = get_offers(product_data)
    brand = product_data.get("brand")
    if isinstance(brand, dict): brand = brand.get("name")
    image = product_data.get("image")
    if isinstance(image, list): image = image[0] if image else None
    
    rating = None
    rating_data = product_data.get("aggregateRating")
    if isinstance(rating_data, dict): rating = to_rating(rating_data.get("ratingValue"))

    price = to_number(offer.get("price", offer.get("lowPrice")))
    if price is None:
        price_str = str(product_data)
        match = re.search(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', price_str)
        if match: price = float(match.group(1))

    return make_product(
        site="daraz", item_id=daraz_item_id(url), name=product_data.get("name"),
        brand=brand, price=price, currency=offer.get("priceCurrency", "PKR"),
        rating=rating, stock=stock_from_offer(offer), image_url=image, product_url=url,
    )

def scrape_daraz(links):
    products = []
    for index, url in enumerate(links, start=1):
        logger.info("Daraz product %d/%d: %s", index, len(links), url)
        response = download(url)
        if response:
            soup = BeautifulSoup(response.text, "html.parser")
            product_data = find_product_json(soup)
            if product_data:
                products.append(parse_daraz_product(product_data, url))
        if index < len(links): wait_randomly(WAIT_BETWEEN_PAGES)
    return products


def scrape_samsonite(links):
    products = []
    for index, url in enumerate(links, start=1):
        logger.info("Samsonite product %d/%d: %s", index, len(links), url)
        response = download(url)
        
        if response:
            soup = BeautifulSoup(response.text, "html.parser")
            
            name_tag = soup.select_one("h1")
            name = name_tag.get_text(strip=True) if name_tag else None
            
            price = None
            product_json = find_product_json(soup)
            if product_json:
                offer = get_offers(product_json)
                price = to_number(offer.get("price", offer.get("lowPrice")))
            
            if price is None:
                price_tag = soup.select_one("span.price, div.price, .product-price")
                if price_tag:
                    price = to_number(price_tag.get_text(strip=True))

            image_url = None
            img_tag = soup.select_one("img.product-image, .gallery img")
            if img_tag:
                image_url = img_tag.get("src") or img_tag.get("data-src")
                
            item_id_match = re.search(r'/([^/]+)\.html', url)
            item_id = item_id_match.group(1) if item_id_match else "N/A"
            
            products.append(make_product(
                site="samsonite", item_id=item_id, name=name, brand="Samsonite",
                price=price, currency="USD", rating=None, stock="In stock", 
                image_url=image_url, product_url=url
            ))
            
        if index < len(links): wait_randomly(WAIT_BETWEEN_PAGES)
    return products


def show_table(products):
    if not products: return print("\nKoi data nahi mila.")
    header = f"{'SITE':<12}{'NAME':<42}{'PRICE':>17}{'RATING':>8}  {'STOCK':<16}"
    print("\n" + header + "\n" + "-" * len(header))
    for p in products:
        price_str = f"{p['price']:,.2f} {p['currency']}" if p['price'] is not None else "N/A"
        rating_str = p['rating'] if p['rating'] is not None else "N/A"
        print(f"{p['site']:<12}{p['name'][:40]:<42}{price_str:>17}{str(rating_str):>8}  {p['stock']:<16}")
    print("-" * len(header) + f"\nTotal products: {len(products)}")

def save_csv(products, filename):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(products)
    logger.info("%d products '%s' mein save ho gaye.", len(products), filename)

def save_excel(products, filename):
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Products"
        ws.append([field.replace("_", " ").title() for field in FIELDS])
        for p in products: ws.append([p[f] for f in FIELDS])
        wb.save(filename)
        logger.info("Excel report '%s' mein save ho gayi.", filename)
    except ImportError:
        logger.warning("openpyxl install nahi hai.")

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
    
    all_products = []
    

    if RUN_AMAZON:
        logger.info("===== AMAZON shuru =====")
        all_products.extend(scrape_amazon(AMAZON_KEYWORD, AMAZON_PAGES))
        
    
    if RUN_DARAZ:
        logger.info("===== DARAZ shuru =====")
        all_products.extend(scrape_daraz(DARAZ_LINKS))

    
    if RUN_SAMSONITE:
        logger.info("===== SAMSONITE shuru =====")
        all_products.extend(scrape_samsonite(SAMSONITE_LINKS))

    if all_products:
        show_table(all_products)
        save_csv(all_products, CSV_FILE)
        save_excel(all_products, EXCEL_FILE)
    else:
        logger.warning("Koi data nahi mila.")

if __name__ == "__main__":
    main()