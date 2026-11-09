# Brazil Creative Tech Radar

New Brazilian companies where technology meets the creative industries, spotted every week from the official company registry (Receita Federal open CNPJ data).

---

## En bref (pour Livia)

Chaque lundi matin, GitHub lance le robot tout seul :

1. **Registre :** il vérifie si la Receita Federal a publié un nouveau mois de données. Si oui, il télécharge les fichiers officiels (plusieurs Go) et garde les entreprises ouvertes depuis 12 mois qui combinent tech et créatif. Cette étape peut durer une à deux heures.
2. **Sites web :** il visite le site des entreprises récentes (quand leur email est à leur propre nom de domaine) et note s'il est en ligne, et s'il renvoie vers Instagram ou LinkedIn.
3. **Note sur 10 :** il classe chaque entreprise selon ces signaux publics.
4. **Publication :** il met à jour le site.

Tu n'as rien à faire, sauf si tu veux ajouter ta sélection du mois.

## Ajouter ta sélection (« Editor's picks »)

1. Sur GitHub, ouvre le fichier `picks.yaml` et clique sur le crayon (Edit).
2. Copie l'exemple en enlevant les `#`, remplis le nom, le secteur, ta note et le lien.
3. Clique sur **Commit changes**. Le site se met à jour en quelques minutes.

## Changer le nom, la phrase d'accroche ou ta signature

Modifie `config.yaml` de la même façon (section `site`).

## Lancer une mise à jour sans attendre lundi

Onglet **Actions**, puis **Weekly update**, puis **Run workflow**. Coche « Rescan the registry » seulement si tu veux tout recalculer.

## Si quelque chose ne marche pas

- GitHub t'envoie un email quand une mise à jour échoue. Le site garde alors les données de la semaine précédente.
- **« Could not list … »** : la Receita a probablement changé l'adresse de ses fichiers. Va sur https://arquivos.receitafederal.gov.br, ouvre Dados > Cadastros > CNPJ, copie le code qui suit `/index.php/s/` dans la barre d'adresse et colle-le dans `config.yaml` à la ligne `share_token`.
- Après chaque nouveau mois, `data/cnae_rules.md` liste toutes les activités retenues, avec leur description officielle. Pratique pour vérifier que rien d'inattendu n'est entré.

## Activer les descriptions écrites par IA (optionnel, payant)

1. Crée une clé sur console.anthropic.com.
2. Sur GitHub : Settings > Secrets and variables > Actions > New repository secret. Nom : `ANTHROPIC_API_KEY`, valeur : ta clé.
3. Dans `config.yaml`, passe `ai: enabled` à `true`.

---

## For developers

```
pipeline/
  rules.py    CNAE classes, keywords, legal forms, excluded email domains
  receita.py  WebDAV listing and resumable downloads from the Receita share
  ingest.py   monthly scan: Estabelecimentos -> Empresas -> Simples (MEI), selection, merge
  enrich.py   website checks (known domain, or name-based guess verified by CNPJ on the page)
  score.py    0-10 score from public signals
  ai.py       optional one-line descriptions (Anthropic API)
  geo.py      places each company at its city (name + state, then official code)
  geo/br_places.csv  Brazilian municipalities with coordinates (kelvins/municipios-brasileiros, MIT)
  build.py    public JSON for the site (no emails, phones, partners or addresses)
  run.py      orchestration: python -m pipeline.run [--force-ingest|--build-only]
site/         static site (GitHub Pages); site/geo/<cc>.json = country outline (Code for America, MIT)
data/         internal store, history, last scan report
tests/        invented sample data + local fake websites: bash tests/run_tests.sh
```

Adding a country later: write an ingest module that outputs the same company records with
`cc` set to the country code, add `pipeline/geo/<cc>_places.csv` and `site/geo/<cc>.json`.
The map fits itself to every country listed in `meta.countries`.

Data: Receita Federal do Brasil, Dados Abertos CNPJ.
