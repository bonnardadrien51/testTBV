import datetime
import json
import os
import re
import unicodedata
import pytz
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager

# Épreuves du classement (comptent dans le Score Total / Score Final)
COURSES = [
    {'url': 'https://www.iorienteering.com/dashboard/results/51894', 'hid': 'PlDVta', 'name': 'Garde les pieds sur terre'},
    {'url': 'https://www.iorienteering.com/dashboard/results/61985', 'hid': '7xX4ug', 'name': 'En avant les checkpoints'},
    {'url': 'https://www.iorienteering.com/dashboard/results/48831', 'hid': '9NjwIz', 'name': 'Vise la cible ou bien'},
    {'url': 'https://www.iorienteering.com/dashboard/results/61984', 'hid': 'OdKdfL', 'name': 'LaMaltournée'},
    {'url': 'https://www.iorienteering.com/dashboard/results/49685', 'hid': '7aWvUg', 'name': 'Planoise'},
]

# Épreuve bonus (hors classement) : ajoute des points au Score Final sans compter
# dans le nombre d'épreuves ni être multipliée.
BONUS_COURSE = {
    'url': 'https://www.iorienteering.com/dashboard/results/81603',
    'hid': 'k8eyTz',
    'name': 'Déguisement',
}

# Page de test : liste des pilotes (nom, club, sexe) sans notion de score
PILOTS_TEST_COURSE = {
    'url': 'https://www.iorienteering.com/dashboard/results/62018',
}


def extract_scores_from_url(url, event_id, event_name, debug_path=None):
    """Récupère les scores d'une épreuve iOrienteering.

    event_id / event_name sont fournis explicitement (plutôt que déduits de
    l'URL) car les URLs de type /dashboard/results/<id> ne contiennent pas le
    paramètre course_hid et faisaient planter l'extraction précédente.

    Si debug_path est fourni, un fichier texte est écrit avec le détail brut
    des lignes trouvées dans le tableau de résultats, pour diagnostiquer les
    cas où le format de page diffère (ex: nombre de colonnes différent).
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)

    scores = {}
    debug_lines = [] if debug_path else None
    try:
        wait = WebDriverWait(driver, 20)
        tbody = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#results_table > tbody")))
        rows = tbody.find_elements(By.TAG_NAME, 'tr')

        if debug_lines is not None:
            debug_lines.append(f"URL: {url}")
            debug_lines.append(f"Nombre de lignes trouvées dans #results_table > tbody : {len(rows)}")

        for i, row in enumerate(rows):
            cols = row.find_elements(By.TAG_NAME, 'td')

            if debug_lines is not None:
                debug_lines.append(f"--- Ligne {i} : {len(cols)} colonnes ---")
                for j, col in enumerate(cols):
                    debug_lines.append(f"  col[{j}] = {col.get_attribute('innerHTML').strip()!r}")

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

                    scores[username]['scores'].setdefault(event_name, []).append({
                        "score": main_score,
                        "penalite": penalite
                    })

    except Exception as e:
        print(f"Erreur sur {url} ({event_id}): {e}")
        if debug_lines is not None:
            debug_lines.append(f"EXCEPTION: {e}")
    finally:
        driver.quit()

    if debug_path:
        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write("\n".join(debug_lines) if debug_lines else "(aucune ligne de debug)")

    return scores


GENDER_HOMME = {'homme', 'male', 'h', 'm'}
GENDER_FEMME = {'femme', 'female', 'f'}


def is_homme(sexe):
    return str(sexe).strip().lower() in GENDER_HOMME


def is_femme(sexe):
    return str(sexe).strip().lower() in GENDER_FEMME


def normalize_sexe(sexe):
    """Affiche toujours Homme/Femme, quel que soit le libellé renvoyé par
    iOrienteering (Male/Female, H/F, etc.). Tout le reste (Other, vide...)
    devient 'Non défini'."""
    if is_homme(sexe):
        return 'Homme'
    elif is_femme(sexe):
        return 'Femme'
    else:
        return 'Non défini'


def style_sex(row):
    if is_homme(row['Sexe']):
        return ['background-color: #d4edda'] * len(row)
    elif is_femme(row['Sexe']):
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
                        <th>Bonus Déguisement</th>
                        <th>Score Final</th>
                        <th>Nombre d'épreuves</th>
                        <th>Détails La Maltournée - Planoise</th>
                    </tr>
                </thead>
                <tbody>
    """

    for index, row in df.iterrows():
        row_class = "table-success" if is_homme(row['Sexe']) else "table-info"
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
                <td>{row['Bonus Déguisement']}</td>
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


def slugify(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_').lower()
    return text


def generate_event_html(rows, filename, title):
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
                        <th>Score</th>
                        <th>Autres tentatives</th>
                    </tr>
                </thead>
                <tbody>
    """

    for index, row in enumerate(rows):
        row_class = "table-success" if is_homme(row['Sexe']) else "table-info"
        html_string += f"""
            <tr class="{row_class}">
                <td>{index + 1}</td>
                <td>{row['Participant']}</td>
                <td>{row['Sexe']}</td>
                <td>{row['Club']}</td>
                <td><b>{row['Score']}</b></td>
                <td>{row['Autres']}</td>
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


def extract_participants_from_url(url):
    """Récupère juste la liste des participants (nom, club, sexe) d'une page
    iOrienteering, sans exiger qu'ils aient un score enregistré. Utile pour
    une page qui liste les pilotes inscrits plutôt qu'un classement."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(url)

    participants = []
    try:
        wait = WebDriverWait(driver, 20)
        tbody = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#results_table > tbody")))
        rows = tbody.find_elements(By.TAG_NAME, 'tr')

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if len(cols) > 3:
                username = cols[1].text.strip()
                clubname = cols[2].text.strip()
                gender = cols[3].text.strip()
                if username:
                    participants.append({
                        'Participant': username,
                        'Club': clubname,
                        'Sexe': normalize_sexe(gender),
                    })
    except Exception as e:
        print(f"Erreur sur {url}: {e}")
    finally:
        driver.quit()
    return participants


def generate_pilots_html(participants, filename, title):
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
                        <th>Participant</th>
                        <th>Club</th>
                        <th>Sexe</th>
                    </tr>
                </thead>
                <tbody>
    """

    for p in participants:
        row_class = "table-success" if is_homme(p['Sexe']) else ("table-info" if is_femme(p['Sexe']) else "")
        html_string += f"""
            <tr class="{row_class}">
                <td>{p['Participant']}</td>
                <td>{p['Club']}</td>
                <td>{p['Sexe']}</td>
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


def generate_simple_html(df, filename, title):
    """Classement simplifié (Nom, Club, Sexe, Score Total, Nombre d'épreuves)
    avec un design plus sobre et moderne que le tableau détaillé."""
    paris_tz = pytz.timezone("Europe/Paris")
    generation_time = datetime.datetime.now(paris_tz).strftime("%d/%m/%Y %H:%M:%S")
    os.makedirs("docs", exist_ok=True)
    filepath = os.path.join("docs", filename)

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    html_string = f"""
    <html>
    <head>
        <title>{title}</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                margin: 0;
                font-family: 'Poppins', sans-serif;
                background: linear-gradient(135deg, #1f2933 0%, #2d3b45 100%);
                min-height: 100vh;
                padding: 40px 16px;
                color: #1f2933;
            }}
            .wrapper {{
                max-width: 820px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                margin-bottom: 28px;
                color: #f5f7fa;
            }}
            .header h1 {{
                margin: 0 0 6px 0;
                font-weight: 700;
                font-size: 2rem;
                letter-spacing: 0.5px;
            }}
            .header p {{
                margin: 0;
                font-size: 0.85rem;
                opacity: 0.7;
            }}
            .card {{
                background: #ffffff;
                border-radius: 18px;
                overflow: hidden;
                box-shadow: 0 20px 45px rgba(0, 0, 0, 0.25);
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            thead th {{
                background: #10151a;
                color: #f5f7fa;
                text-transform: uppercase;
                font-size: 0.72rem;
                letter-spacing: 1px;
                font-weight: 600;
                padding: 16px 18px;
                text-align: left;
            }}
            tbody td {{
                padding: 14px 18px;
                font-size: 0.95rem;
                border-bottom: 1px solid #eef1f4;
            }}
            tbody tr:last-child td {{
                border-bottom: none;
            }}
            tbody tr:hover {{
                background: #f6f8fa;
            }}
            .rank {{
                font-weight: 700;
                width: 60px;
            }}
            .pos-1 {{ background: linear-gradient(90deg, #fff8e1, #ffffff); }}
            .pos-2 {{ background: linear-gradient(90deg, #f3f4f6, #ffffff); }}
            .pos-3 {{ background: linear-gradient(90deg, #fdece0, #ffffff); }}
            .badge {{
                display: inline-block;
                padding: 3px 10px;
                border-radius: 999px;
                font-size: 0.72rem;
                font-weight: 600;
            }}
            .badge-homme {{ background: #e3f2ed; color: #1e7a5f; }}
            .badge-femme {{ background: #eaf1fb; color: #245c9c; }}
            .badge-autre {{ background: #f1f1f1; color: #666; }}
            .score {{
                font-weight: 700;
                font-size: 1rem;
            }}
            .nb-epreuves {{
                color: #6b7280;
                font-size: 0.85rem;
            }}
            .footer {{
                text-align: center;
                margin-top: 22px;
                color: #cbd2d9;
                font-size: 0.75rem;
            }}
            .footer-logos {{
                margin-top: 18px;
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 24px;
                background: rgba(255, 255, 255, 0.92);
                border-radius: 14px;
                padding: 14px 24px;
            }}
            .footer-logos img {{
                height: 60px;
                width: auto;
                opacity: 0.95;
            }}
            .footer-logos img.logo-etabli {{
                height: 100px;
            }}
            .table-scroll {{
                overflow-x: auto;
            }}
            @media (max-width: 650px) {{
                body {{
                    padding: 24px 10px;
                }}
                .header h1 {{
                    font-size: 1.5rem;
                }}
                .header p {{
                    font-size: 0.75rem;
                }}
                .card {{
                    border-radius: 12px;
                }}
                thead th, tbody td {{
                    padding: 10px 10px;
                    font-size: 0.78rem;
                    white-space: nowrap;
                }}
                .badge {{
                    font-size: 0.65rem;
                    padding: 2px 8px;
                }}
                .footer-logos {{
                    flex-direction: column;
                    gap: 10px;
                    padding: 12px 18px;
                }}
                .footer-logos img.logo-etabli {{
                    height: 70px;
                }}
                .footer-logos img {{
                    height: 42px;
                }}
            }}
        </style>
        <script>
            setTimeout(function() {{
                window.location.reload();
            }}, 300000);
        </script>
    </head>
    <body>
        <div class="wrapper">
            <div class="header">
                <h1>{title}</h1>
                <p>Généré le {generation_time} (heure de Paris)</p>
            </div>
            <div class="card">
                <div class="table-scroll">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Nom Prénom</th>
                            <th>Club</th>
                            <th>Sexe</th>
                            <th>Score Total</th>
                            <th>Épreuves</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    for index, row in df.iterrows():
        position = index + 1
        pos_class = f"pos-{position}" if position in medals else ""
        medal = medals.get(position, "")
        if is_homme(row['Sexe']):
            badge_class, badge_label = "badge-homme", "Homme"
        elif is_femme(row['Sexe']):
            badge_class, badge_label = "badge-femme", "Femme"
        else:
            badge_class, badge_label = "badge-autre", "Non défini"

        html_string += f"""
                        <tr class="{pos_class}">
                            <td class="rank">{medal or position}</td>
                            <td>{row['Participant']}</td>
                            <td>{row['Club']}</td>
                            <td><span class="badge {badge_class}">{badge_label}</span></td>
                            <td class="score">{row['Score Total']}</td>
                            <td class="nb-epreuves">{row["Nombre d'épreuves"]}</td>
                        </tr>
        """

    html_string += """
                    </tbody>
                </table>
                </div>
            </div>
            <p class="footer">Classement généré par L'établi ludique</p>
            <div class="footer-logos">
                <img class="logo-etabli" src="logo_etabli.png" alt="Logo L'Établi Ludique">
                <img src="logo_bvl.png" alt="Logo Besançon Vol Libre">
            </div>
        </div>
    </body>
    </html>
    """

    with open(filepath, "w", encoding="utf-8") as file:
        file.write(html_string)


def generate_pilots_grid_html(df, filename, title):
    """Page grille compacte (cartes carrées) pensée pour afficher une
    quarantaine de pilotes sans avoir à défiler sur un écran de PC classique,
    avec leur classement (position, score total, nombre d'épreuves)."""
    paris_tz = pytz.timezone("Europe/Paris")
    generation_time = datetime.datetime.now(paris_tz).strftime("%d/%m/%Y %H:%M:%S")
    os.makedirs("docs", exist_ok=True)
    filepath = os.path.join("docs", filename)

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    html_string = f"""
    <html>
    <head>
        <title>{title}</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                margin: 0;
                font-family: 'Poppins', sans-serif;
                background: linear-gradient(135deg, #1f2933 0%, #2d3b45 100%);
                min-height: 100vh;
                padding: 24px 32px;
                color: #1f2933;
            }}
            .header {{
                text-align: center;
                margin-bottom: 20px;
                color: #f5f7fa;
            }}
            .header h1 {{
                margin: 0 0 4px 0;
                font-weight: 700;
                font-size: 1.6rem;
                letter-spacing: 0.5px;
            }}
            .header p {{
                margin: 0;
                font-size: 0.78rem;
                opacity: 0.7;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                gap: 12px;
                max-width: 1500px;
                margin: 0 auto;
            }}
            .pilot-card {{
                background: #ffffff;
                border-radius: 12px;
                padding: 10px 8px;
                text-align: center;
                box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
                aspect-ratio: 1 / 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 4px;
                position: relative;
            }}
            .pilot-card.pos-1 {{ background: linear-gradient(160deg, #fff8e1, #ffffff); }}
            .pilot-card.pos-2 {{ background: linear-gradient(160deg, #f3f4f6, #ffffff); }}
            .pilot-card.pos-3 {{ background: linear-gradient(160deg, #fdece0, #ffffff); }}
            .pilot-rank {{
                position: absolute;
                top: 6px;
                left: 8px;
                font-size: 0.68rem;
                font-weight: 700;
                color: #9aa5b1;
            }}
            .pilot-name {{
                font-weight: 600;
                font-size: 0.8rem;
                line-height: 1.15;
                margin-top: 8px;
            }}
            .pilot-club {{
                font-size: 0.68rem;
                color: #6b7280;
                line-height: 1.15;
            }}
            .pilot-score {{
                font-weight: 700;
                font-size: 0.95rem;
                color: #10151a;
            }}
            .pilot-nb {{
                font-size: 0.65rem;
                color: #9aa5b1;
            }}
            .badge {{
                display: inline-block;
                padding: 1px 8px;
                border-radius: 999px;
                font-size: 0.6rem;
                font-weight: 600;
            }}
            .badge-homme {{ background: #e3f2ed; color: #1e7a5f; }}
            .badge-femme {{ background: #eaf1fb; color: #245c9c; }}
            .badge-autre {{ background: #f1f1f1; color: #666; }}
            .footer {{
                text-align: center;
                margin-top: 22px;
                color: #cbd2d9;
                font-size: 0.75rem;
            }}
            .footer-logos {{
                margin-top: 16px;
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 24px;
                background: rgba(255, 255, 255, 0.92);
                border-radius: 14px;
                padding: 12px 24px;
                max-width: 320px;
                margin-left: auto;
                margin-right: auto;
            }}
            .footer-logos img {{
                height: 50px;
                width: auto;
                opacity: 0.95;
            }}
            .footer-logos img.logo-etabli {{
                height: 80px;
            }}
            @media (max-width: 700px) {{
                body {{
                    padding: 16px 12px;
                }}
                .header h1 {{
                    font-size: 1.25rem;
                }}
                .grid {{
                    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
                    gap: 8px;
                }}
                .pilot-name {{
                    font-size: 0.72rem;
                }}
                .pilot-club, .pilot-nb {{
                    font-size: 0.6rem;
                }}
                .pilot-score {{
                    font-size: 0.85rem;
                }}
                .footer-logos {{
                    flex-direction: column;
                    gap: 8px;
                }}
                .footer-logos img.logo-etabli {{
                    height: 60px;
                }}
                .footer-logos img {{
                    height: 36px;
                }}
            }}
        </style>
        <script>
            setTimeout(function() {{
                window.location.reload();
            }}, 300000);
        </script>
    </head>
    <body>
        <div class="header">
            <h1>{title}</h1>
            <p>Généré le {generation_time} (heure de Paris)</p>
        </div>
        <div class="grid">
    """

    for index, row in df.iterrows():
        position = index + 1
        pos_class = f"pos-{position}" if position in medals else ""
        medal = medals.get(position, "")
        if is_homme(row['Sexe']):
            badge_class, badge_label = "badge-homme", "H"
        elif is_femme(row['Sexe']):
            badge_class, badge_label = "badge-femme", "F"
        else:
            badge_class, badge_label = "badge-autre", "?"

        html_string += f"""
            <div class="pilot-card {pos_class}">
                <div class="pilot-rank">{medal or ('#' + str(position))}</div>
                <div class="pilot-name">{row['Participant']}</div>
                <div class="pilot-club">{row['Club']}</div>
                <span class="badge {badge_class}">{badge_label}</span>
                <div class="pilot-score">{row['Score Total']} pts</div>
                <div class="pilot-nb">{row["Nombre d'épreuves"]} épreuve(s)</div>
            </div>
        """

    html_string += """
        </div>
        <p class="footer">Classement généré par L'établi ludique</p>
        <div class="footer-logos">
            <img class="logo-etabli" src="logo_etabli.png" alt="Logo L'Établi Ludique">
            <img src="logo_bvl.png" alt="Logo Besançon Vol Libre">
        </div>
    </body>
    </html>
    """

    with open(filepath, "w", encoding="utf-8") as file:
        file.write(html_string)


PREVIOUS_POSITIONS_PATH = "docs/previous_positions_test.json"


def load_previous_positions(path):
    """Charge les positions du run précédent (participant -> position),
    utilisées pour calculer l'évolution du classement."""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_positions(path, df):
    """Sauvegarde les positions actuelles pour comparaison au prochain run."""
    positions = {row['Participant']: index + 1 for index, row in df.iterrows()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def generate_evolution_html(df, filename, title, previous_positions):
    """Page de test : classement condensé avec une flèche indiquant
    l'évolution de position par rapport au run précédent (vert = progression,
    rouge = recul, tiret gris = stable ou nouvel arrivant)."""
    paris_tz = pytz.timezone("Europe/Paris")
    generation_time = datetime.datetime.now(paris_tz).strftime("%d/%m/%Y %H:%M:%S")
    os.makedirs("docs", exist_ok=True)
    filepath = os.path.join("docs", filename)

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    html_string = f"""
    <html>
    <head>
        <title>{title}</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                box-sizing: border-box;
            }}
            body {{
                margin: 0;
                font-family: 'Poppins', sans-serif;
                background: linear-gradient(135deg, #1f2933 0%, #2d3b45 100%);
                min-height: 100vh;
                padding: 40px 16px;
                color: #1f2933;
            }}
            .wrapper {{
                max-width: 860px;
                margin: 0 auto;
            }}
            .header {{
                text-align: center;
                margin-bottom: 28px;
                color: #f5f7fa;
            }}
            .header h1 {{
                margin: 0 0 6px 0;
                font-weight: 700;
                font-size: 2rem;
                letter-spacing: 0.5px;
            }}
            .header p {{
                margin: 0;
                font-size: 0.85rem;
                opacity: 0.7;
            }}
            .card {{
                background: #ffffff;
                border-radius: 18px;
                overflow: hidden;
                box-shadow: 0 20px 45px rgba(0, 0, 0, 0.25);
            }}
            .table-scroll {{
                overflow-x: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            thead th {{
                background: #10151a;
                color: #f5f7fa;
                text-transform: uppercase;
                font-size: 0.72rem;
                letter-spacing: 1px;
                font-weight: 600;
                padding: 16px 18px;
                text-align: left;
            }}
            tbody td {{
                padding: 14px 18px;
                font-size: 0.95rem;
                border-bottom: 1px solid #eef1f4;
            }}
            tbody tr:last-child td {{
                border-bottom: none;
            }}
            tbody tr:hover {{
                background: #f6f8fa;
            }}
            .rank {{
                font-weight: 700;
                width: 60px;
            }}
            .pos-1 {{ background: linear-gradient(90deg, #fff8e1, #ffffff); }}
            .pos-2 {{ background: linear-gradient(90deg, #f3f4f6, #ffffff); }}
            .pos-3 {{ background: linear-gradient(90deg, #fdece0, #ffffff); }}
            .badge {{
                display: inline-block;
                padding: 3px 10px;
                border-radius: 999px;
                font-size: 0.72rem;
                font-weight: 600;
            }}
            .badge-homme {{ background: #e3f2ed; color: #1e7a5f; }}
            .badge-femme {{ background: #eaf1fb; color: #245c9c; }}
            .badge-autre {{ background: #f1f1f1; color: #666; }}
            .score {{
                font-weight: 700;
                font-size: 1rem;
            }}
            .evo {{
                font-weight: 700;
                font-size: 0.85rem;
                display: inline-flex;
                align-items: center;
                gap: 4px;
            }}
            .evo-up {{ color: #1e9e5a; }}
            .evo-down {{ color: #d64545; }}
            .evo-same {{ color: #9aa5b1; }}
            .evo-new {{
                color: #245c9c;
                font-size: 0.68rem;
                font-weight: 600;
                background: #eaf1fb;
                padding: 2px 8px;
                border-radius: 999px;
            }}
            .footer {{
                text-align: center;
                margin-top: 22px;
                color: #cbd2d9;
                font-size: 0.75rem;
            }}
            .footer-logos {{
                margin-top: 18px;
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 24px;
                background: rgba(255, 255, 255, 0.92);
                border-radius: 14px;
                padding: 14px 24px;
            }}
            .footer-logos img {{
                height: 60px;
                width: auto;
                opacity: 0.95;
            }}
            .footer-logos img.logo-etabli {{
                height: 100px;
            }}
            @media (max-width: 650px) {{
                body {{ padding: 24px 10px; }}
                .header h1 {{ font-size: 1.5rem; }}
                thead th, tbody td {{ padding: 10px 10px; font-size: 0.78rem; white-space: nowrap; }}
                .footer-logos {{ flex-direction: column; gap: 10px; padding: 12px 18px; }}
                .footer-logos img.logo-etabli {{ height: 70px; }}
                .footer-logos img {{ height: 42px; }}
            }}
        </style>
        <script>
            setTimeout(function() {{
                window.location.reload();
            }}, 300000);
        </script>
    </head>
    <body>
        <div class="wrapper">
            <div class="header">
                <h1>{title}</h1>
                <p>Généré le {generation_time} (heure de Paris)</p>
            </div>
            <div class="card">
                <div class="table-scroll">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th></th>
                            <th>Nom Prénom</th>
                            <th>Club</th>
                            <th>Sexe</th>
                            <th>Score Total</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    for index, row in df.iterrows():
        position = index + 1
        pos_class = f"pos-{position}" if position in medals else ""
        medal = medals.get(position, "")
        if is_homme(row['Sexe']):
            badge_class, badge_label = "badge-homme", "Homme"
        elif is_femme(row['Sexe']):
            badge_class, badge_label = "badge-femme", "Femme"
        else:
            badge_class, badge_label = "badge-autre", "Non défini"

        old_position = previous_positions.get(row['Participant'])
        if old_position is None:
            evo_html = '<span class="evo-new">NOUVEAU</span>'
        elif old_position > position:
            gain = old_position - position
            evo_html = f'<span class="evo evo-up">▲ {gain}</span>'
        elif old_position < position:
            perte = position - old_position
            evo_html = f'<span class="evo evo-down">▼ {perte}</span>'
        else:
            evo_html = '<span class="evo evo-same">▬</span>'

        html_string += f"""
                        <tr class="{pos_class}">
                            <td class="rank">{medal or position}</td>
                            <td>{evo_html}</td>
                            <td>{row['Participant']}</td>
                            <td>{row['Club']}</td>
                            <td><span class="badge {badge_class}">{badge_label}</span></td>
                            <td class="score">{row['Score Total']}</td>
                        </tr>
        """

    html_string += """
                    </tbody>
                </table>
                </div>
            </div>
            <p class="footer">Classement généré par L'établi ludique — Test évolution</p>
            <div class="footer-logos">
                <img class="logo-etabli" src="logo_etabli.png" alt="Logo L'Établi Ludique">
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

    # Épreuves du classement
    for course in COURSES:
        scores = extract_scores_from_url(course['url'], course['hid'], course['name'])
        for participant, data in scores.items():
            if participant not in all_scores:
                all_scores[participant] = {'gender': data['gender'], 'clubname': data['clubname'], 'scores': {}}
            for event_name, score_list in data['scores'].items():
                all_scores[participant]['scores'].setdefault(event_name, []).extend(score_list)

    # Épreuve bonus déguisement (ne compte pas dans le nombre d'épreuves,
    # simplement ajoutée au Score Final)
    bonus_scores = extract_scores_from_url(
        BONUS_COURSE['url'], BONUS_COURSE['hid'], BONUS_COURSE['name'],
        debug_path="docs/debug_deguisement.txt"
    )
    for participant, data in bonus_scores.items():
        if participant not in all_scores:
            all_scores[participant] = {'gender': data['gender'], 'clubname': data['clubname'], 'scores': {}}
        for event_name, score_list in data['scores'].items():
            all_scores[participant]['scores'].setdefault(event_name, []).extend(score_list)

    final_scores = []

    for participant, data in all_scores.items():
        row = {
            'Participant': participant,
            'Sexe': normalize_sexe(data['gender']),
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
        row['Détails La Maltournée - Planoise'] = f"LaMaltournée: { [calcul_valeur(s) for s in mal_scores] } Planoise: { [calcul_valeur(s) for s in pl_scores] }"

        # Bonus déguisement : simple addition au score final, hors classement
        # des épreuves (ne compte pas dans "Nombre d'épreuves" et n'est pas
        # multiplié).
        deguisement_scores = data['scores'].get('Déguisement', [])
        bonus = 0
        if deguisement_scores:
            bonus = max(calcul_valeur(s) for s in deguisement_scores)
        row['Bonus Déguisement'] = bonus

        # Score Total affiché = score des épreuves + bonus déguisement
        row['Score Total'] = total_score + bonus

        row['Score Final'] = total_score * num_events + bonus

        final_scores.append(row)

    df = pd.DataFrame(final_scores).sort_values(by="Score Final", ascending=False).reset_index(drop=True)

    # Génération des fichiers HTML
    generate_html(df, "classement_general.html", "Classement Général")
    generate_html(df[df['Sexe'].apply(is_homme)], "classement_hommes.html", "Classement Hommes")
    generate_html(df[df['Sexe'].apply(is_femme)], "classement_femmes.html", "Classement Femmes")
    generate_simple_html(df, "classement_simple.html", "Classement Général")
    generate_pilots_grid_html(df, "pilotes_grille.html", "Classement — Pilotes")

    # Page de test : évolution du classement (flèches vs run précédent)
    previous_positions = load_previous_positions(PREVIOUS_POSITIONS_PATH)
    generate_evolution_html(df, "classement_evolution_test.html", "Classement — Évolution (test)", previous_positions)
    save_positions(PREVIOUS_POSITIONS_PATH, df)

    # Une page de classement par épreuve individuelle (en plus du classement général)
    for course in COURSES + [BONUS_COURSE]:
        event_name = course['name']
        rows = []
        for participant, data in all_scores.items():
            scores = data['scores'].get(event_name, [])
            if not scores:
                continue
            valeurs = [calcul_valeur(s) for s in scores]
            best_score = max(valeurs)
            autres = [str(v) for v in valeurs if v != best_score]
            rows.append({
                'Participant': participant,
                'Sexe': normalize_sexe(data['gender']),
                'Club': data['clubname'],
                'Score': best_score,
                'Autres': ', '.join(autres),
            })
        rows.sort(key=lambda r: r['Score'], reverse=True)
        generate_event_html(rows, f"classement_epreuve_{slugify(event_name)}.html", f"Classement — {event_name}")

    # Page de test : liste des pilotes (nom, club, sexe)
    pilotes = extract_participants_from_url(PILOTS_TEST_COURSE['url'])
    pilotes.sort(key=lambda p: p['Participant'])
    generate_pilots_html(pilotes, "liste_pilotes_test.html", "Liste des pilotes (test)")


if __name__ == "__main__":
    main()
