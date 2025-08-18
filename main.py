import datetime
import os
import pytz
import requests
from bs4 import BeautifulSoup
import pandas as pd

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
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    scores = {}
    tbody = soup.select_one("#results_table > tbody")
    if not tbody:
        print(f"⚠️ Pas de tableau trouvé sur {url}")
        return scores

    rows = tbody.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) > 6:
            username = cols[1].get_text(strip=True)
            gender = cols[3].get_text(strip=True)
            clubname = cols[2].get_text(strip=True)

            score_text = cols[6].decode_contents()
            if "<b>" in score_text:
                try:
                    score = int(score_text.split("<b>")[1].split("</b>")[0])
                except ValueError:
                    score = 0

                if username not in scores:
                    scores[username] = {
                        "gender": gender,
                        "clubname": clubname,
                        "scores": {}
                    }
                event_id = url.split("course_hid=")[1].split("&")[0]
                event_name = event_names.get(event_id, event_id)
                scores[username]["scores"].setdefault(event_name, []).append(score)

    return scores

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
            table {{ width: 100%; margin: 20px 0; border-collapse: collapse; }}
            th, td {{ padding: 8px; text-align: left; border: 1px solid #ddd; }}
            th {{ background-color: #f4f4f4; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            tr:hover {{ filter: brightness(95%); }}
            .footer-logos {{ margin-top: 20px; display: flex; justify-content: center; align-items: center; gap: 20px; }}
            .footer-logos img {{ height: 120px; auto: width; opacity: 0.9; }}
        </style>
        <script>
            setTimeout(function() {{ window.location.reload(); }}, 300000);
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
            html_string += f"<td>{row.get(event_name, '0')}</td>"

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

def main():
    all_scores = {}
    for url in urls:
        scores = extract_scores_from_url(url)
        for participant, data in scores.items():
            if participant not in all_scores:
                all_scores[participant] = {
                    'gender': data['gender'],
                    'clubname': data['clubname'],
                    'scores': {}
                }
            for event_name, score_list in data['scores'].items():
                all_scores[participant]['scores'].setdefault(event_name, []).extend(score_list)

    # Transformation des données pour le DataFrame
    rows = []
    for participant, data in all_scores.items():
        row = {
            "Participant": participant,
            "Sexe": data['gender'],
            "Club": data['clubname'],
            "Score Total": sum(sum(scores) for scores in data['scores'].values()),
            "Score Final": sum(sum(scores) for scores in data['scores'].values()),  # Peut être modifié si règles spéciales
            "Nombre d'épreuves": sum(len(scores) for scores in data['scores'].values()),
            "Détails La Maltournée - Planoise": " / ".join(
                f"{k}: {v}" for k, v in data['scores'].items() if k in ["LaMaltournée", "Planoise"]
            )
        }
        for event_name in event_names.values():
            row[event_name] = sum(data['scores'].get(event_name, [0]))
        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values(by="Score Final", ascending=False).reset_index(drop=True)

    generate_html(df, "classement.html", "Classement Général")

if __name__ == "__main__":
    main()
