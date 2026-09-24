# Sicherheitsrichtlinie

## Umgang mit Zugangsdaten

- **Es liegen keine Geheimnisse im Repository.** `.gitignore` schließt `data/`,
  `secrets.enc`, `key.bin` und `*.env` aus.
- Zugangsdaten (Mailpasswort, API-Keys) werden über den **Secret-Store** verwaltet:
  1. Bevorzugt das Betriebssystem-Keyring (KWallet, GNOME Secret Service,
     Windows Credential Manager).
  2. Fallback: eine mit `Fernet` verschlüsselte Datei (`data/secrets.enc`); der
     Schlüssel wird mit Rechten `0600` in `data/key.bin` abgelegt.
- Welcher Backend aktiv ist, zeigt die App unter *Über & Spenden* sowie in
  `/api/health`.

## Mailzugriff

- Ausschließlich **IMAP read-only**. Nachrichten werden nicht verändert oder gelöscht.
- Der Scan ist **inkrementell** (nur neue Mails seit dem letzten Lauf).

## Netzwerk & Telemetrie

- Kein Telemetrie-Versand, kein Tracking.
- Analysen laufen lokal über die **opencode**-CLI und das konfigurierte Modell. Welche
  Daten dabei an den Modellanbieter gehen, hängt vom gewählten Modell ab und ist über
  opencode konfigurierbar.

## Schwachstelle melden

Bitte vertraulich an **alexander.riedel@eyedea3d.com** – mit Reproduktionsschritten.
Keine öffentlichen Issues für Sicherheitslücken, bis ein Fix verfügbar ist.
