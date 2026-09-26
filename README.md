<p align="center"><img src="assets/logo-wordmark.png" width="340" alt="MalochBot"></p>

# MalochBot

> Job hunting is a grind. MalochBot takes it off your plate.

MalochBot is a local, open-source web app that bundles **job search, application
tracking and career documents** in one place. All analysis runs through
[opencode](https://opencode.ai) with a freely chosen LLM.

## Project goal — job hunting, thought through

Job hunting is draining: postings spread across many portals, applications by email,
replies buried in your inbox, documents in several folders. MalochBot takes that whole
process seriously and brings it together in **one** place — **locally on your own
machine**, no cloud required. Search, tracking and documents share the same data, and
every assessment runs through opencode with a freely chosen LLM. The goal is not to
replace the human, but to **automate the routine** so more time is left for the
decisions that actually matter: which job, which cover letter, which interview.

## Features

- **Find jobs** – start a search with one button; new postings are found, de-duplicated
  and stored in the database.
- **One view for everything** – a filterable list of all jobs on the left (live filters),
  the detail panel on the right with fit rationale, description, location/remote, status,
  links to the posting and company, plus the related emails.
- **Track applications** – connect a mailbox (Gmail, Outlook, GMX, WEB.DE, STRATO, IONOS,
  mailbox.org, Posteo, Yahoo, iCloud, Zoho, Fastmail or your own server); mail is read
  read-only via IMAP and the status is assessed by the LLM.
- **Documents** – keep CV, references, work samples and reference cover letters in one
  place, have them reviewed/improved by the LLM and generate cover letters.
- **Model choice** – dropdown of every model available in opencode; analysis always runs
  through opencode.
- **Live log** – every process step in real time, with logs you can debug.
- **Analytics** – hits per search day, funnel (found → applied → response → interview → offer), fit distribution.
- **Two themes** – light and dark (toggle top right), minimal and calm.
- **Help built in** – "About & Donate" explains the project goal, how to use it and security.
- **Secure** – credentials in the OS keyring, no secrets in the repository, no telemetry.

## Documentation

- [Technical documentation (German)](docs/DOKUMENTATION.md)

## Screenshots

> Company names in the screenshots are blurred out (see `tools/shots.js`).

**Job list with detail panel (dark)**
![Job list](docs/screenshots/02-jobs-dark-detail.png)

**Filtered job list (dark)**
![Filtered list](docs/screenshots/03-jobs-dark-filter-remote.png)

**Analytics (dark)**
![Statistics](docs/screenshots/06-stats-dark.png)

**Documents (dark)**
![Documents](docs/screenshots/08-documents-dark.png)

**Help & project goal (light)**
![About & help](docs/screenshots/12-about-light.png)

More views (light/dark, filtered) live in [`docs/screenshots/`](docs/screenshots/).

**Mobile** — on small screens the layout is rebuilt: the job list becomes tappable cards, the filters collapse behind a toggle, the detail opens as a full-screen sheet (with back/gesture support), and documents/log render as cards instead of horizontally scrolling tables. `tools/shots.js` also produces mobile screenshots (`*-mobile-*`).

## Installation

### Linux / macOS
```bash
cd MalochBot
./install.sh     # installs opencode (if needed), Python deps, database
./run.sh         # starts the server and opens http://127.0.0.1:8765
```

### Windows
```bat
cd MalochBot
install.bat
run.bat
```

The installers check/install **opencode**, set up the **web search (MCP)** servers, create
a virtual environment and initialise the database. Then, in the browser under **Settings**,
pick a model and connect your mailbox (one-time setup).

## Web search (MCP) — required for job search

The job search asks the model to research the web. For that, opencode needs the MCP servers
**brave-search** (web search) and **fetch**. Without them the search finds nothing and fails
with "no parseable JSON response".

- `scripts/setup_opencode_mcp.sh` (Linux/macOS) or `scripts/setup_opencode_mcp.bat`
  (Windows) register the MCP servers in `~/.config/opencode/opencode.json` — the installer
  runs this automatically.
- Requires **Node.js 20+** (for `npx`/brave-search) and **uv** (for `uvx`/fetch). If missing,
  the script attempts to install them into `~/.local/tools` (via micromamba or the uv
  installer); otherwise please install [Node.js](https://nodejs.org) and
  [uv](https://docs.astral.sh/uv/) yourself.
- A **Brave API key** (free tier at https://brave.com/search/api/) is requested during setup
  and stored locally in the opencode config (0600). Without a key, web search stays disabled.
- If MalochBot runs as a **systemd service**, the service PATH must include the binaries,
  e.g. `Environment=PATH=/home/USER/.opencode/bin:/home/USER/.local/tools/bin:/usr/local/bin:/usr/bin:/bin`.

## Running

- `run.sh`/`run.bat` stop any running instance and start the server again (no duplicate
  instances). For always-on operation on a server, a systemd service is a good fit
  (see below).
- **Stop manually:** Settings → "Stop server".
- The **model list** is loaded live from the system (`opencode models`), grouped by provider.

## Always-on operation (server)

For permanent operation (e.g. on a home server) set `MALOCHBOT_HOST=0.0.0.0` so the service
is reachable on the network. A systemd unit lives at `deploy/malochbot.service` (user-scoped,
`systemctl --user`) and `deploy/malochbot-system.service` (system-wide).

## Requirements

- Python 3.10+
- [opencode](https://opencode.ai) (the installers try to install it)
- **Node.js 20+** and **uv** for the web-search MCPs (brave-search/fetch; see above)
- Optional LibreOffice for PDF export of cover letters (not required — PDFs are produced in Python)

## Architecture

```
MalochBot/
  app/
    main.py          FastAPI app, routes, SSE log stream
    db.py            SQLite schema and access (all job data)
    secrets.py       Secret store (keyring / encrypted file)
    logbus.py        Live logs + persistence
    opencode_adapter.py  Calls the opencode CLI
    providers.py     Mail provider presets
    import_legacy.py Import existing data
    engines/         search, tracking, documents
    templates/       UI
    static/          CSS/JS
  data/              Runtime data (DB, uploads, logs) – not in the repo
```

## Security

See [SECURITY.md](SECURITY.md). Mail passwords and keys are never stored in the repository.
The code is fully auditable and no telemetry is sent.

## License

MIT – see [LICENSE](LICENSE).

## Support

If MalochBot saves you time:
**PayPal: [alexander.riedel@eyedea3d.com](https://www.paypal.com/donate?business=alexander.riedel%40eyedea3d.com&item_name=MalochBot)** ❤️
