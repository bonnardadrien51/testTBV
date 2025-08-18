from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import os

def extract_scores_from_url(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")          # Mode headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    # Indique à Selenium où trouver le Chromedriver
    driver_path = "/usr/bin/chromedriver"
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.get(url)
    time.sleep(2)  # attendre le chargement de la page

    scores = []

    # Exemple de récupération de scores depuis des éléments avec classe "score"
    # à adapter selon ta page
    score_elements = driver.find_elements(By.CLASS_NAME, "score")
    for el in score_elements:
        scores.append(el.text)

    driver.quit()
    return scores

def main():
    urls = [
        "https://exemple.com/page1",
        "https://exemple.com/page2",
        # ajoute tes URLs ici
    ]

    all_scores = {}
    for url in urls:
        print(f"Extraction de : {url}")
        scores = extract_scores_from_url(url)
        all_scores[url] = scores
        print(scores)

    # Exemple : écrire dans un fichier HTML pour GitHub Pages
    output_path = os.path.join("docs", "classement.html")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("<html><body>\n")
        for url, scores in all_scores.items():
            f.write(f"<h2>{url}</h2>\n<ul>\n")
            for score in scores:
                f.write(f"<li>{score}</li>\n")
            f.write("</ul>\n")
        f.write("</body></html>")

if __name__ == "__main__":
    main()
