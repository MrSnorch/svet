import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
import re
import json
import requests
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADDRESSES_JSON = os.getenv("ADDRESSES_JSON")


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })


def build_serialized(date_site):
    return f"""from={date_site}&to={date_site}&streetid=&skyscraperid=&street=&house=&radio1580works=1&radio1580datetype=2&
organizationMultiSelect[]=184&organizationMultiSelect[]=148&organizationMultiSelect[]=155&organizationMultiSelect[]=171&organizationMultiSelect[]=167&
ServiceGroup[]=12&ServiceGroup[]=11&ServiceGroup[]=3&ServiceGroup[]=2&ServiceGroup[]=8&ServiceGroup[]=7&ServiceGroup[]=4&ServiceGroup[]=22&
DistributionPoint[]=2&DistributionPoint[]=4&DistributionPoint[]=1&DistributionPoint[]=7&
DistributionPoint[]=8&DistributionPoint[]=5&DistributionPoint[]=9&
DistributionPoint[]=6&DistributionPoint[]=3&DistributionPointCountAll=9""".replace("\n", "").strip()


def check_all_addresses():

    addresses = json.loads(ADDRESSES_JSON)

    today = datetime.now().strftime("%Y-%m-%d")
    date_site = datetime.strptime(today, "%Y-%m-%d").strftime("%Y/%m/%d")
    date_search = datetime.strptime(today, "%Y-%m-%d").strftime("%d.%m.%y")

    scraper = cloudscraper.create_scraper()

    payload = {
        "data": build_serialized(date_site),
        "rn": "0",
        "all": "1",
        "isFrame": "",
        "hr": "1",
        "ls": "0",
        "conf": "0",
        "frameJeoId": "0"
    }

    response = scraper.post(
        "https://1562.kharkivrada.gov.ua/ajax/inform/informList-v2.php",
        data=payload
    )

    if response.status_code != 200:
        print("Ошибка доступа:", response.status_code)
        return

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all("div", class_="panelinform")

    for address in addresses:
        street = address["street"]
        house = address["house"]

        for card in cards:
            text = card.get_text(" ", strip=True)

            if date_search not in text:
                continue

            if street.lower() not in text.lower():
                continue

            pattern = rf"буд\.\s*{re.escape(house)}(?![-А-Яа-яA-Za-z])"
            if not re.search(pattern, text):
                continue

            title = ""
            h5 = card.find("h5")
            if h5:
                title = h5.get_text(" ", strip=True)

            reason = ""
            reason_tag = card.find("pre")
            if reason_tag:
                reason = reason_tag.get_text(strip=True)

            start = re.search(r"Початок\s*(\d{2}\.\d{2}\.\d{2}\s*\d{2}:\d{2})", text)
            end = re.search(r"(Кінець|Заплановано)\s*(\d{2}\.\d{2}\.\d{2}\s*\d{2}:\d{2})", text)

            message = f"⚡ <b>Отключение найдено</b>\n\n"
            message += f"<b>Адрес:</b> {street} {house}\n\n"

            if title:
                message += f"<b>Тип:</b> {title}\n"
            if reason:
                message += f"<b>Причина:</b> {reason}\n"
            if start:
                message += f"<b>Початок:</b> {start.group(1)}\n"
            if end:
                message += f"<b>{end.group(1)}:</b> {end.group(2)}\n"

            send_telegram(message)
            print("Отправлено:", street, house)


if __name__ == "__main__":
    check_all_addresses()
