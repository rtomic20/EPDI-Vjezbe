import requests
from bs4 import BeautifulSoup

# Dodaj nove URL-ove koje želiš scrapati
new_urls = [
    "https://egradnja.hr/razgovor/kresimir-damjanovic-arhitektura-je-i-istrazivanje-ne-samo-gradnja-794"
]

def get_article_text(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Ne mogu dohvatiti {url}")
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    content_div = soup.find("body")
    if not content_div:
        print(f"Nije pronađen sadržaj za {url}")
        return ""

    paragraphs = content_div.find_all("p")
    article_text = "\n".join(p.get_text(strip=True) for p in paragraphs)
    return article_text

with open("architecture_context.md", "a", encoding="utf-8") as f:
    for url in new_urls:
        print(f"Scrapam: {url}")
        article = get_article_text(url)
        if article:
            f.write(f"\n\n--- Članak sa {url} ---\n\n")
            f.write(article)

print("Novi sadržaj dodan u architecture_context.md")
