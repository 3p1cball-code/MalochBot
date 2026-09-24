# Mitwirken

Beiträge sind willkommen.

1. Fork + Branch (`feature/…` oder `fix/…`).
2. Code-Stil: Python mit 4 Leerzeichen, sprechende Namen, keine Secrets im Diff.
3. Vor dem PR lokal starten: `./install.sh && ./run.sh`, Seiten prüfen (`/`, `/jobs`,
   `/applications`, `/documents`, `/settings`, `/log`, `/about`) und `/api/health`.
4. Keine neuen Abhängigkeiten ohne kurze Begründung im PR-Text.
5. PR mit Beschreibung: Was, warum, wie getestet.

Neue Mail-Anbieter: einfach in `app/providers.py` ergänzen (Label, IMAP-Host, Port,
Hinweis zu App-Passwort).

Spenden: [PayPal](https://www.paypal.com/donate?business=alexander.riedel%40eyedea3d.com&item_name=MalochBot)
