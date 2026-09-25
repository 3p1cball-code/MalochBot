# MalochBot — Arbeitsprobe

**Vom Skript zur Anwendung: eine Arbeitsprobe über Denken, Prozess und Produkt.**

Alexander Riedel · September 2026 · https://github.com/3p1cball-code/MalochBot

---

## Worum es hier geht

Diese Arbeitsprobe beschreibt kein Codeprojekt, sondern eine Denkweise. Es geht nicht darum,
ob jemand eine Anwendung bauen kann — das kann mit einem guten Sprachmodell und dem
passenden Werkzeug heute fast jeder. Es geht um die Frage, die danach kommt: Welches
Problem lohnt es, in eine Maschine zu gießen, und wie weit trägt der Gedanke, wenn man ihn
zu Ende denkt?

MalochBot ist auf dem Papier ein Werkzeug für die Jobsuche. Tatsächlich ist es das
Ergebnis einer Kette von Entscheidungen, Beobachtungen und bewusst gezogenen Grenzen. Genau
diese Kette möchte ich hier sichtbar machen.

## Die Ausgangsbeobachtung

Die erste Stufe kennt inzwischen jeder: einen Lebenslauf mit einem Sprachmodell erzeugen,
ein Anschreiben formulieren lassen, ein wenig polieren. Das ist Routine geworden. Die
Werkzeuge sind so gut, dass das Ergebnis für sich genommen kaum noch ein Unterschied ist.

Der eigentliche Wert liegt deshalb nicht in dem, was die Maschine ausgibt, sondern darin,
welchen Prozess man um sie herum baut. Ein einzelner guter Handgriff ist kein Vorsprung.
Ein System, das denselben Handgriff zuverlässig, wiederholbar und im Überblick
organisierbar macht, ist einer.

## Prozessstufe eins: Der Bot, der sucht

Der naheliegende nächste Schritt war ein kleiner Bot, der Stellenanzeigen sucht. Als
Einzelaktion beeindruckend, in der Wiederholung aber wertlos: Ohne Gedächtnis findet er
beim nächsten Lauf dieselben Stellen wieder, die man beim letzten Mal schon gesehen hat.
Ohne einen ehrlichen Umgang mit dem, was bereits bekannt ist, verliert ein Suchlauf sofort
seinen Sinn. Die erste echte Erkenntnis war daher unscheinbar und zentral: Ein Suchlauf
braucht ein Gedächtnis, sonst ist er nur beim ersten Mal nützlich.

## Prozessstufe zwei: Suchen und Schreiben verbinden

Mein eigenes Skript hat diesen Schritt bereits gemacht: Es suchte, verwarf Bekanntes und
legte für die besten Treffer gleich ein Anschreiben dazu. Damit war es dem reinen Suchen
einen Schritt voraus, weil es zwei Tätigkeiten verband, die sonst getrennt bleiben. Das
ist die Stufe, auf der die meisten aufhören — und auf der andere gerade erst anfangen.

## Prozessstufe drei: Der Moment, in dem die Übersicht kippt

Der Bot lief zuverlässig, die Ergebnisse stapelten sich in Ordnern. Nach mehreren Läufen
passierte, was immer passiert: Ab dem zehnten Durchlauf verliert man den Überblick. Welche
Stelle war das noch? Worauf habe ich mich beworben? Was ist daraus geworden? Kam überhaupt
eine Antwort? Der Nutzen war da — aber er versteckte sich in einer wachsenden Zahl von
Dateien.

## Prozessstufe vier: Erst Ordnung schaffen — Tabelle und Skript

Der erste Reflex war nicht Technik, sondern Ordnung. Ein kleines Aufräumskript sammelte die
verstreuten Ergebnisse ein und goss sie in eine einzige Tabelle: jede Bewerbung mit Firma,
Position, Datum und Stand. Auf einen Blick ließ sich nun sehen, wo man sich beworben hatte
und was daraus geworden war. Das war ein echter Fortschritt — aber es blieb eine Tabelle,
die man pflegen muss, und daneben lagen die Ordner, die Skripte und die Dateien unverändert
herum. Die Ordnung betraf die Bewerbungen, nicht das Werkzeug selbst.

## Prozessstufe fünf: Eine Anwendung, die zusammenführt

Jetzt wird der eigentliche Engpass sichtbar: Nicht die Jobs und nicht die Statusangaben
waren das Problem, sondern der Ordner selbst, die Skripte und die Dateien darin. Das Ganze
funktionierte, aber es war nur für jemanden geeignet, der selbst technisch denkt. Für alle
anderen war es eine Sammlung von Dateien, in denen niemand etwas findet.

MalochBot ist die Antwort darauf. Es zieht alle Teile des Prozesses an eine Stelle: gefundene
Stellen, Bewerbungen, Unterlagen, die Verbindung zum eigenen Postfach und den jeweils
aktuellen Stand. Es sortiert nicht nur, es erzählt. Zu jeder Stelle lässt sich der Verlauf
nachlesen — wann sie gefunden wurde, welcher Kontakt kam, wann sich etwas geändert hat. Aus
einer Dateiablage wird eine übersichtliche, filterbare Oberfläche, die man auch dann noch
versteht, wenn man wochenlang nicht hineingeschaut hat.

Der entscheidende Sprung ist nicht die zusätzliche Funktion, sondern die veränderte
Perspektive: vom Werkzeug für einen Techniker zu einem Produkt für einen Menschen.

## Prozessstufe sechs: Auslagern und veröffentlichen

Die nächste Stufe ist keine neue Funktion, sondern eine Frage der Verantwortung. Zugangsdaten
und Unterlagen gehören nicht in ein Projekt, das man weitergibt; sie werden sauber getrennt
und geschützt abgelegt. Der Quelltext wird offen veröffentlicht. Damit verlässt das Projekt
den privaten Rechner und wird nachvollziehbar, prüfbar und für andere nutzbar. Das ist keine
technische Notwendigkeit, sondern eine bewusste Haltung: Wer etwas baut, das mit persönlichen
Daten umgeht, sollte es so bauen, dass man ihm nachsehen kann.

## Die bewusste Grenze

Der letzte denkbare Schritt wäre eine öffentlich gehostete Webseite, bei der niemand mehr
etwas installieren muss. Ich habe mich bewusst dagegen entscheiden — vorerst. Nicht, weil
es technisch nicht ginge, sondern weil damit Käufe, fremde Nutzerdaten und die volle
Verantwortung für deren Sicherheit einhergingen. Diese Verantwortung bin ich derzeit nicht
bereit, leichtfertig zu tragen. Zu erkennen, wo ein Projekt enden sollte, gehört zum
Produktdenken genauso wie das Hinzufügen von Funktionen. Ein bewusster Schlusspunkt ist
eine Entscheidung, kein Versäumnis.

## Full Circle

Und dann schließt sich der Kreis: Diese Arbeitsprobe wird selbst wieder zu einem Dokument in
MalochBot. Sie wird zu einer Unterlage, die der nächste Suchlauf mit einbezieht und aus der
künftige Anschreiben schöpfen. Das Projekt beschreibt sich nicht nur — es benutzt sich
selbst. Damit ist die Arbeitsprobe nicht länger ein Anhängsel, sondern ein Teil des Systems,
das sie erklärt.

## Die eigentliche Motivation

Der Anlass für all das ist persönlich. Die Berliner CGI-Szene, in der ich mich bewege, ist
vertraut und überschaubar — und genau deshalb zu klein geworden. Man wechselt von einem
kleinen Studio, in dem man schon einige kennt, in das nächste, in dem man die Hälfte kennt.
Irgendwann stößt dieser Kreis an seine Grenzen.

Für einen möglichen neuen Weg muss ich diese Komfortzone verlassen. Draußen liegt ein für
mich unbekannter, riesiger Markt an Möglichkeiten. Ohne Systematik würde ich in diesem Markt
umherirren; mit einem Werkzeug wie MalochBot kann ich ihn strukturiert bearbeiten und das
Beste aus meiner Situation herausholen. MalochBot ist damit kein Selbstzweck. Es führt
zusammen, was sonst verstreut bleibt: Suchen, Bewerten, Bewerben, Nachhalten, Unterlagen
und die eigenen Stärken.

## Der Pipeline-Gedanke

MalochBot ist als Pipeline gebaut, nicht als Sammlung von Einzelfunktionen. Jeder Schritt
liefert ein Ergebnis, das der nächste weiterverwendet:

- Die Suche erzeugt Kandidaten und ein Gedächtnis darüber, was bereits bekannt ist.
- Die Bewertung erzeugt eine Rangfolge und eine Begründung.
- Die Unterlagen liefern die Grundlage: Lebenslauf, Referenzen, Referenzanschreiben.
- Das Anschreiben entsteht daraus und wird als Dokument abgelegt.
- Das Postfach liefert die Fakten zum Status: jede Mail wird einzeln bewertet, daraus entsteht der Verlauf.
- Diese Arbeitsprobe fließt als Unterlage zurück in die Suche.

Jede Stufe ist einzeln prüfbar, jede ist austauschbar — anderes Modell, anderes Postfach,
andere Engine — und nichts geht verloren, weil alles an einer Stelle zusammenläuft. Das ist
derselbe Gedanke wie in einer 3D-Pipeline: reproduzierbare Schritte, klare Schnittstellen,
ein durchgehender Datenfluss und die Möglichkeit, an genau einer Stelle etwas zu verbessern,
ohne den Rest neu zu bauen. An Produktionen gehe ich seit jeher so heran — ob es um CGI,
generative KI oder einen Bewerbungsprozess geht.

## Ein Blick in die Anwendung

Die folgenden Ansichten sind anonymisiert; Firmennamen und personenbezogene Inhalte sind
unkenntlich gemacht. MalochBot gibt es in Hell und Dunkel — hier in Dunkel.

![MalochBot — Jobliste mit Filterleiste und Detailfenster](screenshots/02-jobs-dark-detail.png)

![MalochBot — Jobsuche-Filter (nur Remote, ab Fit 70)](screenshots/03-jobs-dark-filter-remote.png)

![MalochBot — Auswertung über alle Jobs und Bewerbungen](screenshots/06-stats-dark.png)

![MalochBot — zentrale Unterlagen mit Bewertung und Versionen](screenshots/08-documents-dark.png)

![MalochBot — Hilfe und Projektziel in der Anwendung](screenshots/12-about-light.png)

## Der technische Aufbau

Damit die Pipeline nicht nur ein Gedanke bleibt, hier der tatsächliche Aufbau.

**Anwendung.** Python mit FastAPI und Uvicorn als Server; Jinja2-Templates und
handgeschriebenes CSS und JavaScript im Frontend, ohne Build-Schritt und ohne externe
CDNs. SQLite als einzige Datenbank, portabel als eine Datei. Alle Analysen laufen über die
opencode-CLI mit frei wählbarem Modell.

**Direkte Abhängigkeiten (requirements.txt):** fastapi, uvicorn[standard], jinja2,
python-multipart, keyring, cryptography, pypdf, fpdf2, pillow. Das ist bewusst schlank — die
gesamte Oberfläche und alle Engines kommen ohne zusätzliche Frameworks aus.

**Werkzeuge außerhalb des Codes:** opencode als LLM-Harness; systemd für den Dauerbetrieb;
git und gh für Versionierung und Deployment. LibreOffice ist ausdrücklich nicht nötig,
die PDF-Erzeugung passiert direkt in Python.

**Umfang (Code-Zeilen):**

- Python (Backend, Engines, Adapter): 2.685
- Templates (Jinja2/HTML): 679
- CSS und JavaScript: 1.183
- Tooling (Markdown-zu-PDF, Mail-Suche, Tracking-Test): 374
- Gesamt: rund 4.900 Zeilen

Die größeren Module: main.py (644 Zeilen, Routen und API), engines/documents.py (420,
Unterlagen und Anschreiben), engines/tracking.py (311, Postfach-Auswertung), db.py (237,
Schema und Migrationen), i18n.py (219, zweisprachige Oberfläche), opencode_adapter.py (126),
secrets.py (113, Keyring und verschlüsselte Ablage), engines/tracking_mail.py (112,
mail-zentrische Auswertung), config.py (105), engines/search.py (95).

---

**Projekt:** MalochBot — automatisierte Jobsuche und Bewerbungsverwaltung
**Repository:** https://github.com/3p1cball-code/MalochBot
**Lizenz:** MIT
