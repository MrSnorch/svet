import os
import logging
import re
from datetime import datetime

import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================
# НАСТРОЙКИ
# =========================

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

BASE_URL = "https://1562.kharkivrada.gov.ua/ajax/inform/informList-v2.php"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
telegram_app = ApplicationBuilder().token(TOKEN).build()

# =========================
# ЗАПРОС К САЙТУ
# =========================

def build_serialized(date_site):
    return f"""
from={date_site}&to={date_site}&streetid=&skyscraperid=&street=&house=&radio1580works=1&radio1580datetype=2&
organizationMultiSelect[]=184&organizationMultiSelect[]=148&organizationMultiSelect[]=155&organizationMultiSelect[]=171&organizationMultiSelect[]=167&
ServiceGroup[]=12&ServiceGroup[]=11&ServiceGroup[]=3&ServiceGroup[]=2&ServiceGroup[]=8&ServiceGroup[]=7&ServiceGroup[]=4&ServiceGroup[]=22&
InformType[]=878&InformType[]=801&InformType[]=849&InformType[]=797&InformType[]=867&InformType[]=803&InformType[]=897&InformType[]=889&
InformType[]=855&InformType[]=852&InformType[]=881&InformType[]=880&InformType[]=879&InformType[]=799&InformType[]=850&InformType[]=795&
InformType[]=802&InformType[]=851&InformType[]=805&InformType[]=882&InformType[]=861&InformType[]=807&InformType[]=868&InformType[]=884&
InformType[]=898&InformType[]=888&InformType[]=866&InformType[]=863&InformType[]=864&InformType[]=804&InformType[]=883&InformType[]=862&
InformType[]=806&InformType[]=865&InformType[]=885&InformType[]=844&InformType[]=834&InformType[]=815&InformType[]=902&InformType[]=904&
InformType[]=905&InformType[]=845&InformType[]=816&InformType[]=814&InformType[]=825&InformType[]=901&InformType[]=826&InformType[]=887&
InformType[]=873&InformType[]=874&InformType[]=800&InformType[]=796&InformType[]=859&InformType[]=896&InformType[]=860&InformType[]=857&
InformType[]=856&InformType[]=876&InformType[]=870&InformType[]=875&InformType[]=798&InformType[]=794&InformType[]=858&InformType[]=877&
InformType[]=820&InformType[]=818&InformType[]=900&InformType[]=819&InformType[]=817&InformType[]=824&InformType[]=822&InformType[]=899&
InformType[]=823&InformType[]=821&InformType[]=811&InformType[]=833&InformType[]=903&InformType[]=810&InformType[]=808&InformType[]=812&
InformType[]=809&
DistributionPoint[]=2&DistributionPoint[]=4&DistributionPoint[]=1&DistributionPoint[]=7&
DistributionPoint[]=8&DistributionPoint[]=5&DistributionPoint[]=9&
DistributionPoint[]=6&DistributionPoint[]=3&DistributionPointCountAll=9
""".replace("\n", "").strip()


def check_power(date_str, street_input, house_input):

    scraper = cloudscraper.create_scraper()

    date_site = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y/%m/%d")
    date_search = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%y")

    serialized = build_serialized(date_site)

    payload = {
        "data": serialized,
        "rn": "0",
        "all": "1",   # 🔥 грузим ВСЕ карточки
        "isFrame": "",
        "hr": "1",
        "ls": "0",
        "conf": "0",
        "frameJeoId": "0"
    }

    response = scraper.post(BASE_URL, data=payload)

    if "Оголошеня відсутні" in response.text:
        return "Оголошень немає"

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all("div", class_="panelinform")

    results = []

    for card in cards:

        text = card.get_text(" ", strip=True)

        if date_search not in text:
            continue

        if street_input.lower() not in text.lower():
            continue

        pattern = rf"буд\.\s*{re.escape(house_input)}(?![-А-Яа-яA-Za-z0-9])"
        if not re.search(pattern, text):
            continue

        # ----------- ПАРСИНГ ------------

        title = card.find("h5")
        title_text = title.get_text(" ", strip=True) if title else ""

        reason_tag = card.find("pre")
        reason = reason_tag.get_text(strip=True) if reason_tag else "—"

        start = re.search(r"Початок\s*(\d{2}\.\d{2}\.\d{2}\s*\d{2}:\d{2})", text)
        end = re.search(r"(Кінець|Заплановано)\s*(\d{2}\.\d{2}\.\d{2}\s*\d{2}:\d{2})", text)
        modified = re.search(r"Дата модифікації\s*(\d{2}\.\d{2}\.\d{4}\s*\d{2}:\d{2})", text)
        executor = re.search(r"Виконавець\s*(.+)", text)

        block = f"⚡ <b>{title_text}</b>\n"
        block += f"📄 Причина: {reason}\n\n"

        if start:
            block += f"🟢 Початок: {start.group(1)}\n"

        if end:
            block += f"🔵 {end.group(1)}: {end.group(2)}\n"

        if modified:
            block += f"✏ Дата модифікації: {modified.group(1)}\n"

        if executor:
            block += f"👷 Виконавець: {executor.group(1).strip()}\n"

        results.append(block)

    if not results:
        return "❌ Відключень за цією адресою не знайдено"

    return "\n\n------------------------\n\n".join(results)


# =========================
# TELEGRAM ОБРАБОТКА
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    try:
        date, street, house = text.split(",", 2)
        result = check_power(date.strip(), street.strip(), house.strip())
        await update.message.reply_text(result, parse_mode="HTML")
    except Exception:
        await update.message.reply_text(
            "Формат:\nYYYY-MM-DD, Улица, Дом\n\n"
            "Приклад:\n2026-02-17, Соборності України, 228"
        )


telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


# =========================
# WEBHOOK
# =========================

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "ok"


@app.route("/")
def home():
    return "Bot is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
