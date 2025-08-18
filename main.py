import datetime
import os
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager

# URLs et noms d'épreuves
urls = [
    'https://www.iorienteering.com/dashboard/results?course_hid=PlDVta&lang=fr',
    'https://www.iorienteering.com/dashboard/results?course_hid=7xX4ug&lang=fr',
    'https://www.iorienteering.com/dashboard/results?course_hid=9NjwIz&lang=fr',
    'https://www.iorienteering.com/dashboard/results?course_hid=OdKdfL&lang=fr',
    'https://www.iorienteering.com/dashboard/results?course_hid=7aWvUg&lang=fr'
]

event_names = {
    'PlDVta': 'Garde les pieds sur terre',
    '7xX4ug': 'En avant les checkpoints',
    '9NjwIz': 'Vise la cible ou bien',
    'OdKdfL': 'LaMaltournée',
    '7aWvUg': 'Planoise'
}

def extract_scores_from_url(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)

    scores = {}
    try:
        wait = WebDriverWait(driver, 20)
        tbody = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#results_table > tbody")))
        rows = tbody.find_elements(By.TAG_NAME, 'tr')

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if len(cols) > 6:
                username = cols[1].text
                gender = cols[3].text
                clubname = cols[2].text
                score_text = cols[6].get_attribute('innerHTML')
                if '<b>' in score_text:
                    score = int(score_text.split('<b>')[1].split('</b>')[0])
                    if username not in scores:
                        scores[username] = {'gender': gender, 'clubname': clubname, 'scores': {}}
                    event_id = url.split('course_hid=')[1].split('&')[0]
                    event_name = event_names.get(event_id, event_id)
                    scores[username]['scores'].setdefault(event_name, []).append(score)
    except Exception as e:
        print(f"Erreur sur {url}: {e}")
    finally:
        driver.quit()
    return scores

def generate_html(df, filename, title):
    # Heure de Paris
    paris_tz = pytz.timezone("Europe/Paris")
    generation_time = datetime.datetime.now(paris_tz).strftime("%d/%m/%Y %H:%M:%S")

    # Assurer que le dossier docs existe
    os.makedirs("docs", exist_ok=True)
    filepath = os.path.join("docs", filename)

    # Colonnes d'épreuves (affichage)
    event_columns = [
        'Garde les pieds sur terre',
        'En avant les checkpoints',
        'Vise la cible ou bien',
        'Remonte la pente a patte'
    ]

    # Début HTML
    html_string = f"""
    <html>
    <head>
        <title>{title}</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootswatch/4.5.2/sketchy/bootstrap.min.css">
        <style>
            table {{
                width: 100%;
                margin: 20px 0;
                border-collapse: collapse;
            }}
            th, td {{
                padding: 8px;
                text-align: left;
                border: 1px solid #ddd;
            }}
            th {{
                background-color: #f4f4f4;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            tr:hover {{
                filter: brightness(95%);
            }}
            .footer {{
                margin-top: 24px;
                text-align: center;
                color: #555;
                font-size: 0.95em;
            }}
            .footer-logos {{
                margin-top: 10px;
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 20px;
            }}
            .footer-logos img {{
                max-height: 70px;
                max-width: 200px;
                opacity: 0.95;
            }}
        </style>
        <script>
            // Actualiser la pa
