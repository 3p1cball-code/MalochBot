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
Stelle war das noch? Was ist daraus geworden? Kam überhaupt eine Antwort? Ein Blick in den
Ordner machte das Problem schonungslos klar: Das Ganze funktioniert, aber es ist nur für
jemanden geeignet, der selbst technisch denkt. Für alle anderen ist es eine Sammlung von
Dateien, in denen niemand etwas findet. Der Nutzen war da — aber er war zu versteckt, um
wirklich nützlich zu sein.

Hier kippt die Aufgabenstellung. Es geht nicht mehr darum, noch eine Analyse hinzuzufügen.
Es geht darum, die Fäden zusammenzuziehen.

## Prozessstufe vier: Eine Anwendung, die zusammenführt

MalochBot ist die Antwort auf diesen Moment. Es zieht alle Teile des Prozesses an eine
Stelle: gefundene Stellen, Bewerbungen, Unterlagen, die Verbindung zum eigenen Postfach und
den jeweils aktuellen Stand. Es sortiert nicht nur, es erzählt. Zu jeder Stelle lässt sich
der Verlauf nachlesen — wann sie gefunden wurde, welcher Kontakt kam, wann sich etwas
geändert hat. Aus einer Dateiablage wird eine übersichtliche, filterbare Oberfläche, die
man auch dann noch versteht, wenn man wochenlang nicht hineingeschaut hat.

Der entscheidende Sprung ist nicht die zusätzliche Funktion, sondern die veränderte
Perspektive: vom Werkzeug für einen Techniker zu einem Produkt für einen Menschen.

## Prozessstufe fünf: Auslagern und veröffentlichen

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

## Was das über meine Arbeitsweise sagt

MalochBot ist datengetrieben, reproduzierbar und dokumentiert. Es trifft Entscheidungen
ehrlich, auch wenn sie unbequem sind — etwa, dass eine fehlende Rückmeldung niemals als
Bewerbung gezählt wird. Es hält seine Grenzen fest. Es trennt Bedienung von Technik, damit
ein Mensch es benutzen kann, ohne die Mechanik zu kennen. Und es schreibt nicht nur auf,
was funktioniert hat, sondern auch, was verworfen wurde und warum.

Das ist der eigentliche Inhalt dieser Arbeitsprobe: nicht die Zeilen, sondern das Denken
dahinter — und die Bereitschaft, einen Gedanken konsequent zu Ende zu führen und dann an der
richtigen Stelle anzuhalten.

---

**Projekt:** MalochBot — automatisierte Jobsuche und Bewerbungsverwaltung
**Repository:** https://github.com/3p1cball-code/MalochBot
**Lizenz:** MIT
