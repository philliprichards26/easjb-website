name: 🏀 Fetch FFBB Data

on:
  schedule:
    # Toutes les heures (minute 15 pour éviter les pics)
    - cron: '15 * * * *'
  # Permet de lancer manuellement depuis l'onglet Actions
  workflow_dispatch:
  # Lance aussi à chaque push (pratique pour tester)
  push:
    branches: [main]
    paths:
      - 'fetch_ffbb.py'
      - '.github/workflows/fetch-ffbb.yml'

jobs:
  fetch:
    name: Fetch & Deploy
    runs-on: ubuntu-latest
    permissions:
      contents: write   # Pour pouvoir pusher data.json

    steps:
      # 1. Checkout du repo
      - name: ⬇️ Checkout
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      # 2. Python
      - name: 🐍 Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip

      # 3. Installation des dépendances
      - name: 📦 Install dependencies
        run: pip install ffbb-api-client-v2

      # 4. Exécution du script
      - name: 🏀 Fetch FFBB data
        run: python fetch_ffbb.py

      # 5. Commit + push si data.json a changé
      - name: 💾 Commit data.json
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add public/data.json
          # Ne commit que si le fichier a vraiment changé
          if git diff --staged --quiet; then
            echo "Aucun changement dans data.json — rien à commiter."
          else
            git commit -m "🏀 Update FFBB data $(date -u '+%Y-%m-%d %H:%M UTC')"
            git push
          fi
