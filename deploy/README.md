# MalochBot dauerhaft auf einem Server betreiben (z. B. VEGA)

Ziel: Dienst läuft permanent, erreichbar im LAN/Tailnet, Datenbank und Unterlagen
werden migriert.

## 1. Voraussetzungen auf dem Server

- Python 3.10+
- `opencode` installiert und für den Dienst-User konfiguriert (`opencode auth`,
  damit das gewählte Modell funktioniert)
- optional LibreOffice (`soffice`) für PDF-Erzeugung

## 2. Programm auf den Server kopieren

```bash
# auf VEGA, z. B. nach /opt/MalochBot (systemweit) oder ~/MalochBot (User-Dienst)
sudo mkdir -p /opt/MalochBot
rsync -a --exclude '.venv' --exclude 'data' \
  ~/Dokumente/jobsuche/neue_jobs_bot/MalochBot/ vega:/opt/MalochBot/
```

## 3. Installation

```bash
cd /opt/MalochBot
./install.sh        # legt .venv an, installiert Abhängigkeiten, prüft opencode
```

## 4. Datenbank & Unterlagen migrieren

Den kompletten Datenordner mitnehmen (enthält DB, Dokumente, generierte Dateien und
den verschlüsselten Secret-Store):

```bash
# vom Client zum Server
rsync -a ~/Dokumente/jobsuche/neue_jobs_bot/MalochBot/data/ vega:/opt/MalochBot/data/
```

Enthalten: `malochbot.sqlite3`, `documents/`, `generated/`, `secrets.enc`, `key.bin`.

**Zugangsdaten:** Der Secret-Store nutzt bevorzugt das OS-Keyring. Auf einem Headless-
Server ist meist kein Keyring vorhanden – dann greift automatisch die verschlüsselte
Datei (`data/secrets.enc` + `data/key.bin`). Diese beiden Dateien unbedingt mitkopieren
oder das Mailpasswort nach dem Start erneut in den Einstellungen setzen.

## 5. systemd-Dienst einrichten

**Variante A – systemweit** (`/opt/MalochBot`):

```bash
sudo cp deploy/malochbot-system.service /etc/systemd/system/malochbot.service
# ggf. User= und Pfade in der Datei anpassen
sudo systemctl daemon-reload
sudo systemctl enable --now malochbot
sudo systemctl status malochbot
```

**Variante B – Benutzerdienst** (`~/MalochBot`):

```bash
mkdir -p ~/.config/systemd/user
cp deploy/malochbot.service ~/.config/systemd/user/malochbot.service
systemctl --user daemon-reload
systemctl --user enable --now malochbot
loginctl enable-linger "$USER"     # läuft auch ohne Login
```

## 6. Netzwerk / Härtung

- `MALOCHBOT_HOST=0.0.0.0` lässt den Dienst im Netz lauschen. Zugriff am besten nur
  über Tailscale; kein Port-Forwarding.
- Optional firewall (VEGA hat firewalld):
  ```bash
  sudo firewall-cmd --permanent --add-port=8765/tcp
  sudo firewall-cmd --reload
  ```
- Es gibt **keine Benutzeranmeldung** in MalochBot. Im offenen LAN also nur hinter
  Tailscale/Firewall betreiben.

## 7. Updates

```bash
cd /opt/MalochBot
git pull            # bzw. neues rsync
./install.sh
sudo systemctl restart malochbot
```

Die Datenbank bleibt bei Updates unverändert (Schema-Migration läuft automatisch beim
Start).
