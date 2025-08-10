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
    'PlDVta': 'SOLO-GardeLesPiedsSurTerre',
    '7xX4ug': 'SOLO-EnAvantLesCheckPoints',
    '9NjwIz': 'SOLO-ViseLaCibleOuBien',
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

def style_sex(row):
    if row['Sexe'] == 'Homme':
        return ['background-color: #d4edda'] * len(row)  # vert clair
    elif row['Sexe'] == 'Femme':
        return ['background-color: #d1ecf1'] * len(row)  # bleu clair
    else:
        return [''] * len(row)

def generate_html(df, filename, title):
    paris_tz = pytz.timezone('Europe/Paris')
    now_paris = datetime.datetime.now(paris_tz).strftime("%Y-%m-%d %H:%M:%S")

    css = """
    <style>
      table.dataframe {
        border-collapse: collapse;
        width: 100%;
      }
      table.dataframe, table.dataframe th, table.dataframe td {
        border: 1px solid #ddd;
      }
      table.dataframe tr:hover {
        background-color: #f5f5f5;
      }
      table.dataframe th, table.dataframe td {
        padding: 8px;
        text-align: left;
      }
    </style>
    """

    html_string = f"""<html><head><title>{title}</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootswatch/4.5.2/sketchy/bootstrap.min.css">
    {css}
    </head>
    <body><div class="container">
    <h1>{title}</h1><p><small>Généré le {now_paris} (heure de Paris)</small></p>
    {df.to_html(escape=False, index=False, classes='dataframe table table-hover')}
    </div></body></html>"""

    os.makedirs("docs", exist_ok=True)
    with open(f"docs/{filename}", "w", encoding="utf-8") as f:
        f.write(html_string)


def main():
    all_scores = {}
    for url in urls:
        scores = extract_scores_from_url(url)
        for participant, data in scores.items():
            if participant not in all_scores:
                all_scores[participant] = {'gender': data['gender'], 'clubname': data['clubname'], 'scores': {}}
            for event_name, score_list in data['scores'].items():
                all_scores[participant]['scores'].setdefault(event_name, []).extend(score_list)

    solo_events = ['SOLO-GardeLesPiedsSurTerre', 'SOLO-EnAvantLesCheckPoints', 'SOLO-ViseLaCibleOuBien']
    combined_event = 'RemonteLaPenteAPatte'
    event_columns = solo_events + [combined_event]

    final_scores = []
    for participant, data in all_scores.items():
        scores = data['scores']
        formatted_scores = {}
        for event in solo_events:
            if event in scores:
                best_score = max(scores[event])
                other_scores = sorted(scores[event], reverse=True)[1:]
                formatted_scores[event] = f"<b>{best_score}</b>" + (f" ({'; '.join(map(str, other_scores))})" if other_scores else "")
            else:
                formatted_scores[event] = "0"
        maltournee_score = scores.get('LaMaltournée', [])
        planoise_score = scores.get('Planoise', [])
        best_score = max(maltournee_score + planoise_score) if (maltournee_score or planoise_score) else 0
        formatted_scores[combined_event] = f"<b>{best_score}</b>"
        maltournee_best = max(maltournee_score) if maltournee_score else 0
        planoise_best = max(planoise_score) if planoise_score else 0
        detail_scores = f"La Maltournée: {maltournee_best} ; Planoise: {planoise_best}"
        total_score = sum(int(s.split('<b>')[1].split('</b>')[0]) if '<b>' in s else int(s) for s in formatted_scores.values())
        number_of_events = sum(1 for s in formatted_scores.values() if s != "0")
        final_score = total_score * number_of_events
        final_scores.append({
            'Participant': participant,
            'Sexe': data['gender'],
            'Club': data['clubname'],
            **formatted_scores,
            'Score Total': total_score,
            'Score Final': final_score,
            'Nombre d\'épreuves': number_of_events,
            'Détails La Maltournée - Planoise': detail_scores
        })

    df = pd.DataFrame(final_scores).sort_values(by="Score Final", ascending=False).reset_index(drop=True)
    generate_html(df, "classement_general.html", "Classement Général")
    generate_html(df[df['Sexe'] == 'Homme'], "classement_hommes.html", "Classement Hommes")
    generate_html(df[df['Sexe'] == 'Femme'], "classement_femmes.html", "Classement Femmes")

if __name__ == "__main__":
    main()
