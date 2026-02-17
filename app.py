from flask import Flask, render_template_string, request
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
import re
import logging

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Мониторинг отключений</title>
</head>
<body style="font-family:Arial;padding:40px;max-width:900px;">

<h2>Мониторинг отключений (Всі оголошення)</h2>

<form method="post">
<label>Дата:</label><br>
<input type="date" name="date" value="{{ date }}" required><br><br>

<label>Улица:</label><br>
<input type="text" name="street" value="{{ street }}" required style="width:400px;"><br><br>

<label>Дом:</label><br>
<input type="text" name="house" value="{{ house }}" required><br><br>

<button type="submit">Проверить</button>
</form>

{% if result %}
<hr>
<h3>Результат:</h3>
<div style="background:#f5f5f5;padding:15px;">
{{ result|safe }}
</div>
{% endif %}

</body>
</html>
"""

# Полный serialized как у сайта (Всі оголошення)
def build_serialized(date_site):
    return f"""from={date_site}&to={date_site}&streetid=&skyscraperid=&street=&house=&radio1580works=1&radio1580datetype=2&
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
DistributionPoint[]=6&DistributionPoint[]=3&DistributionPointCountAll=9""".replace("\n", "").strip()


def check_power(date_str, street_input, house_input):

    logging.info("==========================================")
    logging.info(f"Дата: {date_str}")
    logging.info(f"Улица: {street_input}")
    logging.info(f"Дом: {house_input}")

    scraper = cloudscraper.create_scraper()

    date_site = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y/%m/%d")
    date_search = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%y")

    serialized = build_serialized(date_site)

    payload = {
        "data": serialized,
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

    logging.info(f"HTTP статус: {response.status_code}")
    logging.info(f"Размер HTML: {len(response.text)}")

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all("div", class_="panelinform")

    logging.info(f"Найдено карточек: {len(cards)}")

    if not cards:
        return "Карточки не найдены"

    results = []

    for i, card in enumerate(cards, 1):

        text = card.get_text(" ", strip=True)

        logging.info(f"--- Карточка {i} ---")
        logging.info(text)

        # Проверка даты
        if date_search not in text:
            continue

        # Проверка улицы (без учета регистра)
        if street_input.lower() not in text.lower():
            continue

        # Точное совпадение дома
        pattern = rf"буд\.\s*{re.escape(house_input)}(?![-А-Яа-яA-Za-z])"
        if not re.search(pattern, text):
            continue

        logging.info("✔ Найдено совпадение!")

        # --- ИЗВЛЕЧЕНИЕ ДАННЫХ ---

        # Заголовок
        title = ""
        h5 = card.find("h5")
        if h5:
            title = h5.get_text(" ", strip=True).replace("~", "—")

        # Причина
        reason = ""
        reason_tag = card.find("pre")
        if reason_tag:
            reason = reason_tag.get_text(strip=True)

        start = re.search(r"Початок\s*(\d{2}\.\d{2}\.\d{2}\s*\d{2}:\d{2})", text)
        end = re.search(r"(Кінець|Заплановано)\s*(\d{2}\.\d{2}\.\d{2}\s*\d{2}:\d{2})", text)
        modified = re.search(r"Дата модифікації\s*(\d{2}\.\d{2}\.\d{4}\s*\d{2}:\d{2})", text)
        executor = re.search(r'Виконавець\s*(.+?)(?=Початок|$)', text)

        result_block = "<b>Найдено отключение:</b><br><br>"

        if title:
            result_block += f"<b>Тип:</b> {title}<br><br>"

        if reason:
            result_block += f"<b>Причина:</b> {reason}<br><br>"

        if start:
            result_block += f"<b>Початок:</b> {start.group(1)}<br>"

        if end:
            result_block += f"<b>{end.group(1)}:</b> {end.group(2)}<br>"

        if modified:
            result_block += f"<b>Дата модифікації:</b> {modified.group(1)}<br>"

        if executor:
            result_block += f"<b>Виконавець:</b> {executor.group(1).strip()}<br>"

        results.append(result_block)

    if not results:
        return "Отключений по указанному адресу не найдено"

    return "<hr>".join(results)


@app.route("/", methods=["GET", "POST"])
def index():
    date = datetime.now().strftime("%Y-%m-%d")
    street = "Соборності України"
    house = "228"
    result = None

    if request.method == "POST":
        date = request.form["date"]
        street = request.form["street"]
        house = request.form["house"]
        result = check_power(date, street, house)

    return render_template_string(
        HTML,
        date=date,
        street=street,
        house=house,
        result=result
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
