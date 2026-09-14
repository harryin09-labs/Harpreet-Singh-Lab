import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GitHubTrendingReporter/1.0)"
}


def fetch_url(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def get_trending(period):
    url = f"https://github.com/trending?since={period}"
    soup = BeautifulSoup(fetch_url(url), "html.parser")

    repositories = []

    for row in soup.select("article.Box-row")[:5]:
        heading = row.select_one("h2")
        if not heading:
            continue

        link = heading.select_one("a")
        if not link:
            continue

        description = row.select_one("p")
        language = row.select_one(
            "span[itemprop='programmingLanguage']"
        )
        stars = row.select_one("a[href$='/stargazers']")

        row_text = " ".join(row.get_text(" ", strip=True).split())
        growth_match = re.search(
            r"([\d,]+) stars today",
            row_text
        )

        repositories.append({
            "name": " ".join(
                heading.get_text(" ", strip=True).split()
            ),
            "url": "https://github.com" + link.get("href", ""),
            "description": (
                description.get_text(" ", strip=True)
                if description
                else "No description"
            ),
            "language": (
                language.get_text(" ", strip=True)
                if language
                else "—"
            ),
            "stars": (
                stars.get_text(" ", strip=True)
                if stars
                else "—"
            ),
            "growth": (
                growth_match.group(1)
                if growth_match
                else "—"
            ),
        })

    return repositories


def make_section(title, repositories):
    lines = [title]

    for number, repository in enumerate(repositories, start=1):
        description = repository["description"][:180]

        lines.extend([
            f"{number}. {repository['name']} "
            f"— {repository['language']}",
            (
                f"   Stars: {repository['stars']} | "
                f"Today: {repository['growth']} stars"
            ),
            f"   {description}",
            f"   {repository['url']}",
        ])

    return "\n".join(lines)


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": "true",
    }).encode()

    request = urllib.request.Request(
        url,
        data=data,
        headers=HEADERS,
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )


def main():
    current_time = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    report_header = (
        "GitHub Trending Report\n"
        f"{current_time.strftime('%d %b %Y, %I:%M %p IST')}\n\n"
    )

    sections = [
        make_section("DAILY", get_trending("daily")),
        make_section("WEEKLY", get_trending("weekly")),
        make_section("MONTHLY", get_trending("monthly")),
    ]

    report = (
        report_header
        + "\n\n".join(sections)
        + "\n\nSource: https://github.com/trending"
        + "\n\nPrepared by : mindshub.ai"
    )

    # Telegram messages have a length limit. Send the report in
    # safe chunks if necessary.
    max_length = 3900

    chunks = [
        report[position:position + max_length]
        for position in range(0, len(report), max_length)
    ]

    for chunk in chunks:
        send_telegram_message(chunk)

    print("Telegram report sent successfully")


if __name__ == "__main__":
    main()
