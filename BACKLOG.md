# Backlog — testTBV

Suivi des tâches en cours ou en attente. Mis à jour au fil des échanges.

## En attente (à ne traiter qu'après la manif, semaine du 24/08)

Consigne d'Adrien : la manif TBV démarre le 22/08/2026, donc **aucune
modification pouvant avoir un impact sur les pages officielles/live n'est à
faire avant la semaine prochaine**. Les items ci-dessous sont prêts à être
propagés sur les pages officielles une fois la manif passée, en attendant ils
restent cantonnés aux pages de test.

- **Surcharge manuelle du sexe des pilotes** : actuellement disponible via
  `admin_pilotes.html`, propagée uniquement sur `pilotes_grille_test.html`.
  À terme : proposer de l'appliquer aussi au classement général / grille
  pilotes officielle (`classement_general.html`, `pilotes_grille.html`) si
  souhaité.
- **Bonus déguisement manuel (ajout/modification)** : actuellement
  disponible via `admin_deguisement.html`, propagé uniquement sur
  `classement_epreuve_deguisement_test.html`. À terme : proposer de
  l'appliquer aussi à la page officielle `classement_epreuve_deguisement.html`
  et donc au Score Final du classement général, si souhaité.
- **Déclencheur externe fiable** (cron-job.org ou équivalent) pour appeler
  `workflow_dispatch` à intervalle garanti, en complément (ou remplacement)
  du cron GitHub Actions natif (`*/15 * * * *`) qui peut être retardé de
  façon importante en cas de forte charge sur la plateforme. Nécessite la
  création d'un compte par Adrien sur le service choisi (Claude ne peut pas
  le faire seul, ça demande un email/vérification).

## Pages de test actives

- `admin_pilotes.html` → propage vers `pilotes_grille_test.html`
  (fichier de données : `gender_overrides.json`)
- `admin_deguisement.html` → propage vers
  `classement_epreuve_deguisement_test.html`
  (fichier de données : `deguisement_overrides.json`)
- `classement_evolution_test.html` : flèches d'évolution du classement
  (dernier changement significatif connu, fichier `evolution_state_test.json`)
- `liste_pilotes_test.html` / `pilotes_liste_test.json` : liste brute des
  pilotes d'une page de test iOrienteering (`PILOTS_TEST_COURSE`)

## Fait

- Bonus déguisement intégré au Score Final officiel
- Classement trié par Score Final (épreuves × nb épreuves + bonus)
- Pages responsive (classement, pilotes, partenaires)
- Pages "écran" fixes pour pisignage (partenaires + partenaires financiers)
- Planning bénévoles (organisation + public), mis à jour au fil des
  inscriptions/annulations
- Page d'accueil (`index.html`) avec liens vers toutes les pages publiques
- Reformatage de `concoursphoto.md`
