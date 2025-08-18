import datetime
import os
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

    # Selenium détecte automatiquement ChromeDriver et Chrome
    driver = webdriver.Chrome(options=chrome_options)
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
    paris_tz = pytz.timezone("Europe/Paris")
    generation_time = datetime.datetime.now(paris_tz).strftime("%d/%m/%Y %H:%M:%S")
    os.makedirs("docs", exist_ok=True)
    filepath = os.path.join("docs", filename)

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
            .footer-logos {{
                margin-top: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 20px;
            }}
            .footer-logos img {{
                height: 120px;
                auto: width;
                opacity: 0.9;
            }}
        </style>
        <script>
            setTimeout(function() {{
                window.location.reload();
            }}, 300000);
        </script>
    </head>
    <body>
        <div class="container">
            <h1>{title}</h1>
            <p><small>Généré le {generation_time} (heure de Paris)</small></p>
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Position</th>
                        <th>Participant</th>
                        <th>Sexe</th>
                        <th>Club</th>
                        <th>Garde les pieds sur terre</th>
                        <th>En avant les checkpoints</th>
                        <th>Vise la cible ou bien</th>
                        <th>Remonte la pente a patte</th>
                        <th>Score Total</th>
                        <th>Score Final</th>
                        <th>Nombre d'épreuves</th>
                        <th>Détails La Maltournée - Planoise</th>
                    </tr>
                </thead>
                <tbody>
    """
    for index, row in df.iterrows():
        row_class = "table-success" if row['Sexe'] == 'Homme' else "table-info"
        html_string += f"""
            <tr class="{row_class}">
                <td>{index + 1}</td>
                <td>{row['Participant']}</td>
                <td>{row['Sexe']}</td>
                <td>{row['Club']}</td>
                <td>{row.get('Garde les pieds sur terre', 0)}</td>
                <td>{row.get('En avant les checkpoints', 0)}</td>
                <td>{row.get('Vise la cible ou bien', 0)}</td>
                <td>{row.get('Remonte la pente a patte', 0)}</td>
                <td>{row['Score Total']}</td>
                <td>{row['Score Final']}</td>
                <td>{row["Nombre d'épreuves"]}</td>
                <td>{row['Détails La Maltournée - Planoise']}</td>
            </tr>
        """
    html_string += """
                </tbody>
            </table>
        </div>
        <div class="footer">
            <p>Classement généré par L'établi ludique</p>
            <div class="footer-logos">
                <img src="logo_etabli.png" alt="Logo L'Établi Ludique">
                <img src="logo_bvl.png" alt="Logo Besançon Vol Libre">
            </div>
        </div>
    </body>
    </html>
    """
    with open(filepath, "w", encoding="utf-8") as file:
        file.write(html_string)

def main():
    import pandas as pd

    all_scores = {}
    for url in urls:
        scores = extract_scores_from_url(url)
        for participant, data in scores.items():
            if participant not in all_scores:
                all_scores[participant] = {'gender': data['gender'], 'clubname': data['clubname'], 'scores': {}}
            for event_name, score_list in data['scores'].items():
                all_scores[participant]['scores'].setdefault(event_name, []).extend(score_list)

    # Préparer le DataFrame final
    df_rows = []
    for participant, data in all_scores.items():
        row = {
            "Participant": participant,
            "Sexe": data['gender'],
            "Club": data['clubname'],
            "Score Total": sum(sum(v) for v in data['scores'].values()),
            "Score Final": sum(sum(v) for v in data['scores'].values()),  # Ici tu peux appliquer ta formule
            "Nombre d'épreuves": len(data['scores']),
            "Détails La Maltournée - Planoise": data['scores'].get('LaMaltournée', []) + data['scores'].get('Planoise', [])
        }
        for event in ['Garde les pieds sur terre', 'En avant les checkpoints', 'Vise la cible ou bien', 'Remonte la pente a patte']:
            row[event] = sum(data['scores'].get(event, [0]))
        df_rows.append(row)

    df = pd.DataFrame(df_rows)
    df = df.sort_values(by="Score Final", ascending=False).reset_index(drop=True)
    generate_html(df, "classement.html", "Classement Tout Besançon Vole")

if __name__ == "__main__":
    main()
