import asyncio
import pandas as pd
import re
from pathlib import Path
from playwright.async_api import async_playwright

CSV_FILE = "dataset.csv"
URL_COLUMN = "video_url"
OUT_DIR = Path("doms1")


def make_safe_filename(url: str, index: int) -> str:
    """
    Делает безопасное имя файла из URL.
    """
    # Берем кусок после /video/ если получится
    match = re.search(r"/video/(\d+)", url)
    if match:
        return f"{index}_{match.group(1)}.html"

    # Запасной вариант
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", url)
    return f"{index}_{safe[:80]}.html"


async def scrape_html(page, url: str, out_file: Path) -> None:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=90000)

        # Ждем, пока TikTok прогрузит страницу
        await page.wait_for_timeout(25000)

        possible_selectors = [
            "video",
            '[data-e2e="browse-video-desc"]',
            '[data-e2e="like-count"]',
            "h1",
            "main",
        ]

        found_selector = None
        for selector in possible_selectors:
            try:
                await page.locator(selector).first.wait_for(timeout=10000)
                found_selector = selector
                print(f"Found selector for {url}: {selector}")
                break
            except Exception:
                pass

        if not found_selector:
            print(f"No target selector found for {url}. Saving DOM anyway.")

        # Ленивая подгрузка
        await page.mouse.wheel(0, 3000)
        await page.wait_for_timeout(3000)

        # Сохраняем только основной DOM
        dom = await page.evaluate("document.documentElement.outerHTML")
        out_file.write_text(dom, encoding="utf-8")
        print(f"Saved DOM to {out_file}")

    except Exception as e:
        print(f"Failed for {url}: {e}")


async def main():
    OUT_DIR.mkdir(exist_ok=True)

    df = pd.read_csv(CSV_FILE)

    if URL_COLUMN not in df.columns:
        raise ValueError(f"В файле {CSV_FILE} нет столбца '{URL_COLUMN}'")

    urls = df[URL_COLUMN].dropna().astype(str).tolist()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1400, "height": 1000})

        for i, url in enumerate(urls, start=1):
            url = url.strip()
            if not url:
                continue

            filename = make_safe_filename(url, i)
            out_file = OUT_DIR / filename

            # Если файл уже существует — пропускаем
            if out_file.exists():
                print(f"Skipping existing file: {out_file}")
                continue

            print(f"[{i}/{len(urls)}] Processing: {url}")
            await scrape_html(page, url, out_file)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())