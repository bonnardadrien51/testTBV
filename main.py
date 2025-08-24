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
                username = cols[1].text.strip()
                gender = cols[3].text.strip()
                clubname = cols[2].text.strip()
                score_text = cols[6].get_attribute('innerHTML').strip()

                if '<b>' in score_text:
                    # Score principal
                    main_score = int(score_text.split('<b>')[1].split('</b>')[0])

                    # Pénalité éventuelle (ex: "0 (-2)")
                    penalite = 0
                    if '(' in score_text and ')' in score_text:
                        try:
                            penalite_str = score_text.split('(')[1].split(')')[0]
                            penalite = int(penalite_str)
                        except:
                            penalite = 0

                    if username not in scores:
                        scores[username] = {
                            'gender': gender,
                            'clubname': clubname,
                            'scores': {}
                        }

                    event_id = url.split('course_hid=')[1].split('&')[0]
                    event_name = event_names.get(event_id, event_id)

                    scores[username]['scores'].setdefault(event_name, []).append({
                        "score": main_score,
                        "penalite": penalite
                    })

    except Exception as e:
        print(f"Erreur sur {url}: {e}")
    finally:
        driver.quit()
    return scores


def style_sex(row):
    if row['Sexe'] == 'Homme':
        return ['background-color: #d4edda'] * len(row)
    elif row['Sexe'] == 'Femme':
        return ['background-color: #d1ecf1'] * len(row)
    else:
        return [''] * len(row)


def generate_html(df, filename, title):
    paris_tz = pytz.timezone("Europe/Paris")
    generation_time = datetime.datetime.now(paris_tz).strftime("%d/%m/%Y %H:%M:%S")
    os.makedirs("docs", exist_ok=True)
    filepath = os.path.join("docs", filename)

    event_columns = [
        'Garde les pieds sur terre',
        'En avant les checkpoints',
        'Vise la cible ou bien',
        'Remonte la pente a patte'
    ]

    html_string = f"""
    <html>
    <head>
        <title>{title}</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootswatch/4.5.2/sketchy/bootstrap.min.css">
        <style>
            .container {{
                padding-left: 10px;
                padding-right: 10px;
            }}
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
        <div>
            <h1>{title}</h1>
            <p><small>Généré le {generation_time} (heure de Paris)</small></p>
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Position</th>
                        <th>Participant</th>
                        <th>Sexe</th>
                        <th>Club</th>
    """

    for event_name in event_columns:
        html_string += f"<th>{event_name}</th>"

    html_string += """
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
        """
        for event_name in event_columns:
            html_string += f"<td>{row.get(event_name, 0)}</td>"

        html_string += f"""
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


def calcul_valeur(score_dict):
    """Convertit un score {score, penalite} en valeur numérique"""
    score = score_dict["score"]
    penalite = score_dict["penalite"]
    if score > 0:
        return score
    elif score == 0 and penalite < 0:
        return 100 + penalite
    else:
        return 0


def main():
    all_scores = {}
    for url in urls:
        scores = extract_scores_from_url(url)
        for participant, data in scores.items():
            if participant not in all_scores:
                all_scores[participant] = {'gender': data['gender'], 'clubname': data['clubname'], 'scores': {}}
            for event_name, score_list in data['scores'].items():
                all_scores[participant]['scores'].setdefault(event_name, []).extend(score_list)

    final_scores = []

    for participant, data in all_scores.items():
        row = {
            'Participant': participant,
            'Sexe': data['gender'],
            'Club': data['clubname'],
        }

        total_score = 0
        num_events = 0

        # Solo events
        for event in ['Garde les pieds sur terre', 'En avant les checkpoints', 'Vise la cible ou bien']:
            scores = data['scores'].get(event, [])
            if scores:
                valeurs = [calcul_valeur(s) for s in scores]
                best_score = max(valeurs)
                if best_score > 0:
                    num_events += 1
                autres = [str(v) for v in valeurs if v != best_score]
                row[event] = f"<b>{best_score}</b>" + (f" ({', '.join(autres)})" if autres else "")
                total_score += best_score
            else:
                row[event] = 0

        # Combined event: La Maltournée / Planoise
        mal_scores = data['scores'].get('LaMaltournée', [])
        pl_scores = data['scores'].get('Planoise', [])
        combined_scores = mal_scores + pl_scores
        if combined_scores:
            valeurs = [calcul_valeur(s) for s in combined_scores]
            best_score = max(valeurs)
            if best_score > 0:
                num_events += 1
            autres = [str(v) for v in valeurs if v != best_score]
            row['Remonte la pente a patte'] = f"<b>{best_score}</b>" + (f" ({', '.join(autres)})" if autres else "")
            total_score += best_score
        else:
            row['Remonte la pente a patte'] = 0

        row['Nombre d\'épreuves'] = num_events
        row['Score Total'] = total_score
        row['Score Final'] = total_score * num_events
        row['Détails La Maltournée - Planoise'] = f"LaMaltournée: { [calcul_valeur(s) for s in mal_scores] } Planoise: { [calcul_valeur(s) for s in pl_scores] }"

        final_scores.append(row)

    df = pd.DataFrame(final_scores).sort_values(by="Score Final", ascending=False).reset_index(drop=True)

    # Génération des fichiers HTML
    generate_html(df, "classement_general.html", "Classement Général")
    generate_html(df[df['Sexe'] == 'Homme'], "classement_hommes.html", "Classement Hommes")
    generate_html(df[df['Sexe'] == 'Femme'], "classement_femmes.html", "Classement Femmes")


if __name__ == "__main__":
    main()
