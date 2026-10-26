"""
The simulated bank: its policies, how they changed over time, who may read them, and the true
value of every rule on every date.

Havelsee Bank AG is invented (havelsee-bank.example). Its policies are written the way German bank
policies are written: numbered paragraphs (Tz.), a header with document number, version, date of
effect and classification, and rules that change between versions. The truth (which value a rule
had on a date, in which paragraph) lives only here and in the questions built from it; the
platform under test (package `copilot`) never imports this package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Classification levels, lowest first. A user sees a document only with at least its level.
LEVELS = {1: "öffentlich", 2: "intern", 3: "vertraulich", 4: "streng vertraulich"}

DEPARTMENTS = {
    "ZV": "Zahlungsverkehr",
    "KR": "Kreditgeschäft",
    "RI": "Risikocontrolling",
    "CO": "Compliance",
    "IT": "IT und Informationssicherheit",
    "HR": "Personal",
    "TR": "Treasury",
    "VT": "Vertrieb",
    "EK": "Einkauf",
    "RV": "Interne Revision",
    "DS": "Datenschutz",
    "OR": "Organisation",
}


@dataclass(frozen=True)
class User:
    login: str
    name: str
    title: str
    departments: tuple[str, ...]
    clearance: int
    auditor: bool = False  # the internal audit may read every department's documents


USERS: tuple[User, ...] = (
    User("lena.vogt", "Lena Vogt", "Sachbearbeiterin Zahlungsverkehr", ("ZV",), 2),
    User("tobias.kern", "Tobias Kern", "Kreditanalyst", ("KR",), 3),
    User("miriam.haas", "Miriam Haas", "Compliance-Beauftragte", ("CO",), 4),
    User("jan.reuter", "Jan Reuter", "IT-Sicherheitsbeauftragter", ("IT",), 3),
    User("aylin.demir", "Aylin Demir", "Kundenberaterin", ("VT",), 2),
    User("felix.brandt", "Felix Brandt", "Händler Treasury", ("TR",), 4),
    User("sophie.lange", "Sophie Lange", "Referentin Personal", ("HR",), 2),
    User("paul.neumann", "Paul Neumann", "Auszubildender", ("VT",), 1),
    User("greta.wolf", "Greta Wolf", "Prüferin Interne Revision", ("RV",), 4, auditor=True),
)


@dataclass(frozen=True)
class Fact:
    """One rule with a value that may change from version to version."""

    id: str
    section: str  # section heading the paragraph sits under
    statements: tuple[str, ...]  # how the paragraph states it; {v} is the value
    questions: tuple[str, ...]  # how an employee asks for it
    values: tuple[str, ...]  # value per version (index 0 = first version); same value = unchanged
    kind: str = "number"  # number | time | text


@dataclass(frozen=True)
class Policy:
    doc_no: str
    title: str
    owner: str  # department code
    level: int
    audience: tuple[str, ...]  # department codes, or ("alle",)
    versions: tuple[date, ...]  # date each version took effect
    facts: tuple[Fact, ...]
    references: tuple[str, ...] = ()  # external circulars this policy implements
    topic: str = ""  # used in generic paragraphs ("Diese Richtlinie regelt ...")


def F(
    id: str,
    section: str,
    statements: list[str],
    questions: list[str],
    values: list[str],
    kind: str = "number",
) -> Fact:
    return Fact(id, section, tuple(statements), tuple(questions), tuple(values), kind)


D = date

POLICIES: tuple[Policy, ...] = (
    Policy(
        "RL-ZV-01",
        "Richtlinie Freigabe und Kontrolle im Zahlungsverkehr",
        "ZV",
        2,
        ("ZV", "CO", "RV"),
        (D(2022, 3, 1), D(2023, 7, 1), D(2025, 4, 1)),
        (
            F(
                "zv.four_eyes",
                "Freigabe von Zahlungen",
                [
                    "Zahlungsaufträge ab einem Betrag von {v} sind nach dem Vier-Augen-Prinzip durch zwei berechtigte Mitarbeiter freizugeben.",
                ],
                [
                    "Ab welchem Betrag müssen Zahlungen im Vier-Augen-Prinzip freigegeben werden?",
                    "Welche Betragsgrenze gilt für die Zweitfreigabe von Zahlungsaufträgen?",
                ],
                ["25.000 EUR", "15.000 EUR", "10.000 EUR"],
            ),
            F(
                "zv.inst_limit",
                "Echtzeitüberweisungen",
                [
                    "Echtzeitüberweisungen (SEPA Instant) werden je Auftrag bis zu einem Betrag von {v} ausgeführt; höhere Beträge sind als reguläre SEPA-Überweisung einzureichen.",
                ],
                [
                    "Bis zu welchem Betrag werden SEPA-Echtzeitüberweisungen ausgeführt?",
                    "Wie hoch ist das Limit für Instant Payments je Auftrag?",
                ],
                ["15.000 EUR", "100.000 EUR", "100.000 EUR"],
            ),
            F(
                "zv.cutoff",
                "Annahmeschlusszeiten",
                [
                    "Der Annahmeschluss für SEPA-Überweisungen mit Ausführung am selben Geschäftstag ist {v} Uhr.",
                ],
                [
                    "Bis wann müssen SEPA-Überweisungen eingehen, damit sie noch am selben Tag ausgeführt werden?",
                    "Welcher Annahmeschluss gilt für SEPA-Überweisungen?",
                ],
                ["15:00", "16:00", "16:00"],
                "time",
            ),
            F(
                "zv.sanctions_escalation",
                "Sanktionsprüfung",
                [
                    "Treffer der Sanktionslistenprüfung sind innerhalb von {v} an Compliance zu eskalieren; die Zahlung bleibt bis zur Klärung angehalten.",
                ],
                [
                    "Innerhalb welcher Frist sind Treffer der Sanktionsprüfung an Compliance zu melden?",
                ],
                ["2 Stunden", "2 Stunden", "1 Stunde"],
            ),
            F(
                "zv.callback",
                "Neue Zahlungsempfänger",
                [
                    "Bei Zahlungen an einen neu angelegten Empfänger ab {v} ist vor der Freigabe ein telefonischer Rückruf beim Auftraggeber über eine bekannte Rufnummer durchzuführen.",
                ],
                [
                    "Ab welchem Betrag ist bei neuen Zahlungsempfängern ein Rückruf beim Auftraggeber nötig?",
                ],
                ["50.000 EUR", "10.000 EUR", "10.000 EUR"],
            ),
        ),
        topic="die Freigabe, Ausführung und Kontrolle von Zahlungsaufträgen",
    ),
    Policy(
        "RL-KR-01",
        "Kompetenzordnung im Kreditgeschäft",
        "KR",
        3,
        ("KR", "RI", "CO", "RV"),
        (D(2021, 10, 1), D(2024, 1, 1)),
        (
            F(
                "kr.branch_limit",
                "Kreditkompetenzen",
                [
                    "Die Leitung einer Filiale entscheidet über Kredite bis zu einem Gesamtobligo von {v} je Kreditnehmereinheit, sofern die Ratingklasse höchstens 6 beträgt.",
                ],
                [
                    "Bis zu welchem Obligo darf eine Filialleitung Kredite selbst entscheiden?",
                    "Wie hoch ist die Kreditkompetenz der Filialleitung?",
                ],
                ["250.000 EUR", "500.000 EUR"],
            ),
            F(
                "kr.division_limit",
                "Kreditkompetenzen",
                [
                    "Die Bereichsleitung Kreditgeschäft entscheidet über Kredite bis zu einem Gesamtobligo von {v}; darüber entscheidet der Kreditausschuss.",
                ],
                [
                    "Ab welchem Obligo entscheidet der Kreditausschuss statt der Bereichsleitung?",
                ],
                ["1.500.000 EUR", "2.000.000 EUR"],
            ),
            F(
                "kr.second_vote_rating",
                "Votierung",
                [
                    "Ab Ratingklasse {v} ist neben dem Markt-Votum stets ein Votum der Marktfolge einzuholen, unabhängig von der Höhe des Kredits.",
                ],
                [
                    "Ab welcher Ratingklasse ist immer ein Marktfolge-Votum nötig?",
                ],
                ["10", "9"],
            ),
            F(
                "kr.review_interval",
                "Kreditüberwachung",
                [
                    "Kreditengagements über 750.000 EUR sind mindestens alle {v} einer Bonitätsprüfung zu unterziehen.",
                ],
                [
                    "Wie oft müssen große Kreditengagements einer Bonitätsprüfung unterzogen werden?",
                ],
                ["12 Monate", "12 Monate"],
            ),
        ),
        topic="die Zuständigkeiten für Kreditentscheidungen",
    ),
    Policy(
        "RL-KR-02",
        "Bewertung von Kreditsicherheiten",
        "KR",
        2,
        ("KR", "RI", "RV"),
        (D(2022, 1, 1), D(2025, 1, 1)),
        (
            F(
                "kr.haircut_residential",
                "Sicherheitenabschläge",
                [
                    "Auf den Marktwert wohnwirtschaftlich genutzter Immobilien ist ein Sicherheitenabschlag von {v} vorzunehmen.",
                ],
                [
                    "Welcher Abschlag gilt für Wohnimmobilien als Kreditsicherheit?",
                ],
                ["20 %", "25 %"],
            ),
            F(
                "kr.haircut_commercial",
                "Sicherheitenabschläge",
                [
                    "Für gewerblich genutzte Immobilien beträgt der Sicherheitenabschlag {v} des Marktwerts.",
                ],
                [
                    "Welcher Sicherheitenabschlag gilt für Gewerbeimmobilien?",
                ],
                ["40 %", "40 %"],
            ),
            F(
                "kr.revaluation",
                "Überprüfung der Werte",
                [
                    "Der Wert wohnwirtschaftlicher Immobiliensicherheiten ist spätestens alle {v} zu überprüfen.",
                ],
                [
                    "Wie oft muss der Wert von Wohnimmobilien-Sicherheiten überprüft werden?",
                ],
                ["3 Jahre", "3 Jahre"],
            ),
            F(
                "kr.ltv",
                "Beleihungsauslauf",
                [
                    "Der Beleihungsauslauf darf bei Baufinanzierungen {v} des Beleihungswerts nicht überschreiten.",
                ],
                [
                    "Welcher maximale Beleihungsauslauf gilt bei Baufinanzierungen?",
                ],
                ["80 %", "90 %"],
            ),
        ),
        topic="die Bewertung und Überwachung von Kreditsicherheiten",
    ),
    Policy(
        "RL-GW-01",
        "Richtlinie zur Verhinderung von Geldwäsche und Terrorismusfinanzierung",
        "CO",
        3,
        ("CO", "VT", "ZV", "KR", "RV"),
        (D(2022, 6, 1), D(2024, 6, 1)),
        (
            F(
                "gw.kyc_high",
                "Aktualisierung der Kundendaten",
                [
                    "Bei Kunden mit hohem Risiko sind die Kundendaten mindestens alle {v} zu aktualisieren.",
                ],
                [
                    "Wie oft sind die Kundendaten bei Hochrisikokunden zu aktualisieren?",
                ],
                ["12 Monate", "12 Monate"],
            ),
            F(
                "gw.kyc_low",
                "Aktualisierung der Kundendaten",
                [
                    "Bei Kunden mit geringem Risiko erfolgt die Aktualisierung der Kundendaten spätestens nach {v}.",
                ],
                [
                    "Nach welcher Frist müssen die Daten von Kunden mit geringem Risiko aktualisiert werden?",
                ],
                ["10 Jahren", "5 Jahren"],
            ),
            F(
                "gw.cash_threshold",
                "Bargeschäfte",
                [
                    "Bei Bartransaktionen von Nicht-Kunden ab {v} ist die Identität des Einzahlenden festzustellen.",
                ],
                [
                    "Ab welchem Betrag muss bei Bareinzahlungen von Nicht-Kunden die Identität festgestellt werden?",
                ],
                ["10.000 EUR", "2.500 EUR"],
            ),
            F(
                "gw.pep_approval",
                "Politisch exponierte Personen",
                [
                    "Die Aufnahme einer Geschäftsbeziehung mit einer politisch exponierten Person bedarf der Zustimmung durch {v}.",
                ],
                [
                    "Wer muss der Geschäftsbeziehung mit einer politisch exponierten Person zustimmen?",
                ],
                ["ein Mitglied der Geschäftsleitung", "ein Mitglied der Geschäftsleitung"],
                "text",
            ),
            F(
                "gw.suspicion_report",
                "Verdachtsmeldungen",
                [
                    "Interne Verdachtsmeldungen sind innerhalb von {v} an den Geldwäschebeauftragten weiterzuleiten.",
                ],
                [
                    "Innerhalb welcher Frist sind interne Geldwäsche-Verdachtsmeldungen an den Geldwäschebeauftragten zu geben?",
                ],
                ["2 Geschäftstagen", "1 Geschäftstag"],
            ),
        ),
        topic="die Sorgfaltspflichten zur Verhinderung von Geldwäsche und Terrorismusfinanzierung",
    ),
    Policy(
        "RL-CO-01",
        "Interessenkonflikte, Zuwendungen und Mitarbeitergeschäfte",
        "CO",
        2,
        ("alle",),
        (D(2021, 1, 1), D(2023, 1, 1), D(2025, 9, 1)),
        (
            F(
                "co.gift_limit",
                "Geschenke und Einladungen",
                [
                    "Geschenke von Kunden oder Geschäftspartnern dürfen bis zu einem Wert von {v} je Anlass angenommen werden; darüber hinausgehende Geschenke sind abzulehnen.",
                ],
                [
                    "Bis zu welchem Wert dürfen Mitarbeiter Geschenke von Kunden annehmen?",
                    "Wie hoch ist die Wertgrenze für Geschenke von Geschäftspartnern?",
                ],
                ["50 EUR", "40 EUR", "35 EUR"],
            ),
            F(
                "co.holding_period",
                "Mitarbeitergeschäfte",
                [
                    "Für eigene Wertpapiergeschäfte von Mitarbeitern gilt eine Mindesthaltedauer von {v}.",
                ],
                [
                    "Wie lange müssen Mitarbeiter eigene Wertpapiere mindestens halten?",
                ],
                ["30 Tagen", "30 Tagen", "60 Tagen"],
            ),
            F(
                "co.invitation_report",
                "Geschenke und Einladungen",
                [
                    "Einladungen zu Veranstaltungen sind vor der Annahme bei Compliance anzuzeigen, wenn ihr Wert {v} übersteigt.",
                ],
                [
                    "Ab welchem Wert müssen Einladungen bei Compliance angezeigt werden?",
                ],
                ["100 EUR", "100 EUR", "75 EUR"],
            ),
        ),
        topic="den Umgang mit Interessenkonflikten, Zuwendungen und Mitarbeitergeschäften",
    ),
    Policy(
        "RL-IT-01",
        "Richtlinie Zugangs- und Berechtigungsmanagement",
        "IT",
        2,
        ("alle",),
        (D(2022, 2, 1), D(2024, 10, 1)),
        (
            F(
                "it.password_length",
                "Passwörter",
                [
                    "Passwörter für Benutzerkonten müssen mindestens {v} lang sein.",
                ],
                [
                    "Wie lang muss ein Passwort mindestens sein?",
                    "Welche Mindestlänge gilt für Passwörter?",
                ],
                ["10 Zeichen", "14 Zeichen"],
            ),
            F(
                "it.leaver_deactivation",
                "Austritte",
                [
                    "Benutzerkonten ausscheidender Mitarbeiter sind spätestens {v} nach dem Austritt zu sperren.",
                ],
                [
                    "Wann müssen die Konten ausgeschiedener Mitarbeiter gesperrt werden?",
                ],
                ["5 Tage", "1 Tag"],
            ),
            F(
                "it.priv_review",
                "Privilegierte Berechtigungen",
                [
                    "Privilegierte Berechtigungen sind mindestens alle {v} durch die Fachverantwortlichen zu rezertifizieren.",
                ],
                [
                    "Wie oft müssen privilegierte Berechtigungen rezertifiziert werden?",
                ],
                ["6 Monate", "3 Monate"],
            ),
        ),
        topic="die Vergabe, Überprüfung und den Entzug von Zugängen und Berechtigungen",
    ),
    Policy(
        "RL-IT-02",
        "Patch- und Schwachstellenmanagement",
        "IT",
        2,
        ("IT", "RV"),
        (D(2022, 5, 1), D(2023, 11, 1), D(2025, 6, 1)),
        (
            F(
                "it.patch_critical",
                "Fristen für Sicherheitsupdates",
                [
                    "Sicherheitsupdates für kritische Schwachstellen sind innerhalb von {v} nach Veröffentlichung einzuspielen.",
                ],
                [
                    "Innerhalb welcher Frist müssen kritische Sicherheitsupdates eingespielt werden?",
                ],
                ["14 Kalendertagen", "7 Kalendertagen", "3 Kalendertagen"],
            ),
            F(
                "it.patch_high",
                "Fristen für Sicherheitsupdates",
                [
                    "Updates für Schwachstellen mit hoher Kritikalität sind innerhalb von {v} einzuspielen.",
                ],
                [
                    "Bis wann müssen Updates für hoch kritische Schwachstellen installiert sein?",
                ],
                ["30 Kalendertagen", "30 Kalendertagen", "14 Kalendertagen"],
            ),
            F(
                "it.scan_interval",
                "Schwachstellenscans",
                [
                    "Alle aus dem Internet erreichbaren Systeme werden mindestens {v} auf Schwachstellen gescannt.",
                ],
                [
                    "Wie oft werden aus dem Internet erreichbare Systeme auf Schwachstellen gescannt?",
                ],
                ["monatlich", "wöchentlich", "wöchentlich"],
                "text",
            ),
        ),
        topic="das Einspielen von Sicherheitsupdates und die Behandlung von Schwachstellen",
    ),
    Policy(
        "RL-IT-03",
        "Datensicherung und Wiederherstellung",
        "IT",
        2,
        ("IT", "OR", "RV"),
        (D(2021, 6, 1), D(2024, 3, 1)),
        (
            F(
                "it.backup_daily",
                "Aufbewahrung von Sicherungen",
                [
                    "Tägliche Datensicherungen werden {v} aufbewahrt.",
                ],
                [
                    "Wie lange werden tägliche Datensicherungen aufbewahrt?",
                ],
                ["30 Tage", "35 Tage"],
            ),
            F(
                "it.restore_test",
                "Wiederherstellungstests",
                [
                    "Die Wiederherstellung aus Sicherungen wird für jedes kritische System mindestens {v} getestet.",
                ],
                [
                    "Wie oft muss die Wiederherstellung kritischer Systeme aus Backups getestet werden?",
                ],
                ["jährlich", "halbjährlich"],
                "text",
            ),
        ),
        topic="die Sicherung von Daten und deren Wiederherstellung",
    ),
    Policy(
        "RL-OR-01",
        "Notfallmanagement",
        "OR",
        2,
        ("alle",),
        (D(2022, 9, 1), D(2025, 2, 1)),
        (
            F(
                "or.rto_critical",
                "Wiederanlaufziele",
                [
                    "Zeitkritische Geschäftsprozesse sind nach einem Ausfall innerhalb von {v} wiederherzustellen.",
                ],
                [
                    "In welcher Zeit müssen zeitkritische Prozesse nach einem Ausfall wieder laufen?",
                    "Welches Wiederanlaufziel gilt für zeitkritische Geschäftsprozesse?",
                ],
                ["4 Stunden", "2 Stunden"],
            ),
            F(
                "or.drill",
                "Notfalltests",
                [
                    "Für jeden zeitkritischen Geschäftsprozess ist mindestens {v} eine Notfallübung durchzuführen.",
                ],
                [
                    "Wie oft sind Notfallübungen für zeitkritische Prozesse durchzuführen?",
                ],
                ["einmal jährlich", "einmal jährlich"],
                "text",
            ),
        ),
        topic="die Vorsorge für Notfälle und den Wiederanlauf von Geschäftsprozessen",
    ),
    Policy(
        "RL-IT-04",
        "Behandlung und Meldung von IKT-Vorfällen",
        "IT",
        2,
        ("IT", "CO", "OR", "RV"),
        (D(2023, 1, 1), D(2025, 3, 1)),
        (
            F(
                "it.incident_report",
                "Meldung an die Aufsicht",
                [
                    "Schwerwiegende IKT-Vorfälle sind der Aufsicht innerhalb von {v} nach ihrer Einstufung als schwerwiegend erstmals zu melden (vgl. AM 2/2024 Tz. 5).",
                ],
                [
                    "Innerhalb welcher Frist ist ein schwerwiegender IKT-Vorfall der Aufsicht zu melden?",
                ],
                ["24 Stunden", "4 Stunden"],
            ),
            F(
                "it.incident_internal",
                "Interne Eskalation",
                [
                    "Jeder vermutete Sicherheitsvorfall ist innerhalb von {v} an das Security Operations Center zu melden.",
                ],
                [
                    "Wie schnell muss ein vermuteter Sicherheitsvorfall an das Security Operations Center gemeldet werden?",
                ],
                ["60 Minuten", "30 Minuten"],
            ),
        ),
        references=("AM 2/2024",),
        topic="die Erkennung, Einstufung und Meldung von IKT-Vorfällen",
    ),
    Policy(
        "RL-AU-01",
        "Auslagerungsmanagement",
        "RI",
        3,
        ("RI", "EK", "CO", "IT", "RV"),
        (D(2022, 4, 1), D(2024, 9, 1)),
        (
            F(
                "au.notice",
                "Anzeige wesentlicher Auslagerungen",
                [
                    "Beabsichtigte wesentliche Auslagerungen sind der Aufsicht mindestens {v} vor Vertragsbeginn anzuzeigen (vgl. AM 1/2023 Tz. 8).",
                ],
                [
                    "Wie lange vor Vertragsbeginn muss eine wesentliche Auslagerung angezeigt werden?",
                ],
                ["4 Wochen", "4 Wochen"],
            ),
            F(
                "au.risk_review",
                "Risikoanalyse",
                [
                    "Die Risikoanalyse für wesentliche Auslagerungen ist mindestens {v} zu aktualisieren.",
                ],
                [
                    "Wie oft ist die Risikoanalyse für wesentliche Auslagerungen zu aktualisieren?",
                ],
                ["alle zwei Jahre", "jährlich"],
                "text",
            ),
        ),
        references=("AM 1/2023",),
        topic="die Steuerung und Überwachung von Auslagerungen",
    ),
    Policy(
        "RL-DS-01",
        "Löschkonzept personenbezogener Daten",
        "DS",
        2,
        ("alle",),
        (D(2021, 5, 25), D(2024, 5, 1)),
        (
            F(
                "ds.applicants",
                "Löschfristen",
                [
                    "Unterlagen abgelehnter Bewerberinnen und Bewerber werden {v} nach Abschluss des Verfahrens gelöscht.",
                ],
                [
                    "Wann werden die Unterlagen abgelehnter Bewerber gelöscht?",
                ],
                ["6 Monate", "4 Monate"],
            ),
            F(
                "ds.access_request",
                "Auskunftsersuchen",
                [
                    "Auskunftsersuchen betroffener Personen sind innerhalb von {v} nach Eingang zu beantworten.",
                ],
                [
                    "In welcher Frist sind Auskunftsersuchen nach der DSGVO zu beantworten?",
                ],
                ["einem Monat", "einem Monat"],
                "text",
            ),
            F(
                "ds.video",
                "Löschfristen",
                [
                    "Aufzeichnungen der Videoüberwachung in Filialen werden nach {v} automatisch gelöscht, sofern kein Vorfall vorliegt.",
                ],
                [
                    "Nach wie vielen Tagen werden Videoaufzeichnungen der Filialen gelöscht?",
                ],
                ["72 Stunden", "72 Stunden"],
            ),
        ),
        topic="die Aufbewahrung und Löschung personenbezogener Daten",
    ),
    Policy(
        "RL-HR-01",
        "Reisekostenrichtlinie",
        "HR",
        1,
        ("alle",),
        (D(2022, 1, 1), D(2024, 1, 1), D(2026, 1, 1)),
        (
            F(
                "hr.hotel",
                "Übernachtung",
                [
                    "Übernachtungskosten werden bis zu {v} pro Nacht erstattet; in München, Frankfurt am Main und Hamburg gilt ein Zuschlag von 30 EUR.",
                ],
                [
                    "Bis zu welchem Betrag werden Hotelkosten pro Nacht erstattet?",
                    "Wie viel darf eine Hotelübernachtung auf Dienstreise kosten?",
                ],
                ["110 EUR", "130 EUR", "150 EUR"],
            ),
            F(
                "hr.first_class",
                "Bahnreisen",
                [
                    "Bahnfahrten in der 1. Klasse sind erstattungsfähig, wenn die einfache Fahrtzeit mehr als {v} beträgt.",
                ],
                [
                    "Ab welcher Fahrtzeit darf man auf Dienstreisen 1. Klasse Bahn fahren?",
                ],
                ["4 Stunden", "3 Stunden", "3 Stunden"],
            ),
            F(
                "hr.claim_deadline",
                "Abrechnung",
                [
                    "Reisekosten sind spätestens {v} nach Ende der Dienstreise abzurechnen.",
                ],
                [
                    "Bis wann müssen Reisekosten abgerechnet werden?",
                ],
                ["3 Monate", "3 Monate", "6 Wochen"],
            ),
        ),
        topic="die Planung und Abrechnung von Dienstreisen",
    ),
    Policy(
        "RL-HR-02",
        "Pflichtschulungen",
        "HR",
        2,
        ("alle",),
        (D(2022, 1, 1), D(2025, 1, 1)),
        (
            F(
                "hr.new_joiner_training",
                "Neue Mitarbeitende",
                [
                    "Neue Mitarbeitende absolvieren die Pflichtschulungen zu Geldwäscheprävention und Informationssicherheit innerhalb von {v} nach Eintritt.",
                ],
                [
                    "Bis wann müssen neue Mitarbeitende die Pflichtschulungen abschließen?",
                ],
                ["3 Monaten", "6 Wochen"],
            ),
            F(
                "hr.aml_refresh",
                "Wiederholungsschulungen",
                [
                    "Die Schulung zur Geldwäscheprävention ist {v} zu wiederholen.",
                ],
                [
                    "Wie oft muss die Geldwäsche-Schulung wiederholt werden?",
                ],
                ["jährlich", "jährlich"],
                "text",
            ),
        ),
        topic="die verpflichtenden Schulungen für Mitarbeitende",
    ),
    Policy(
        "RL-HR-03",
        "Mobiles Arbeiten",
        "HR",
        1,
        ("alle",),
        (D(2022, 7, 1), D(2024, 7, 1)),
        (
            F(
                "hr.remote_days",
                "Umfang",
                [
                    "Mobiles Arbeiten ist an bis zu {v} pro Woche möglich, sofern betriebliche Belange nicht entgegenstehen.",
                ],
                [
                    "An wie vielen Tagen pro Woche darf mobil gearbeitet werden?",
                ],
                ["2 Tagen", "3 Tagen"],
            ),
            F(
                "hr.remote_abroad",
                "Mobiles Arbeiten im Ausland",
                [
                    "Mobiles Arbeiten aus dem EU-Ausland ist an höchstens {v} pro Kalenderjahr zulässig und vorab zu beantragen.",
                ],
                [
                    "Wie viele Tage im Jahr darf man aus dem EU-Ausland arbeiten?",
                ],
                ["10 Arbeitstagen", "20 Arbeitstagen"],
            ),
        ),
        topic="das Arbeiten außerhalb der Geschäftsräume",
    ),
    Policy(
        "RL-TR-01",
        "Limitsystem Marktpreisrisiken",
        "TR",
        4,
        ("TR", "RI", "RV"),
        (D(2023, 1, 1), D(2025, 1, 1)),
        (
            F(
                "tr.var_limit",
                "Value-at-Risk-Limite",
                [
                    "Das Value-at-Risk-Limit für das Handelsbuch beträgt {v} (99 %, Haltedauer 1 Tag).",
                ],
                [
                    "Wie hoch ist das VaR-Limit des Handelsbuchs?",
                ],
                ["4.000.000 EUR", "5.500.000 EUR"],
            ),
            F(
                "tr.stop_loss",
                "Verlustbegrenzung",
                [
                    "Erreichen die kumulierten Verluste eines Händlers im Monat {v}, sind alle offenen Positionen des Händlers zu schließen.",
                ],
                [
                    "Bei welchem Monatsverlust muss ein Händler seine Positionen schließen?",
                ],
                ["250.000 EUR", "300.000 EUR"],
            ),
        ),
        topic="die Begrenzung von Marktpreisrisiken im Handelsgeschäft",
    ),
    Policy(
        "RL-TR-02",
        "Steuerung des Liquiditätsrisikos",
        "TR",
        4,
        ("TR", "RI", "RV"),
        (D(2022, 10, 1), D(2025, 7, 1)),
        (
            F(
                "tr.lcr_floor",
                "Interne Kennzahlen",
                [
                    "Die Liquiditätsdeckungsquote (LCR) darf intern einen Wert von {v} nicht unterschreiten.",
                ],
                [
                    "Welcher interne Mindestwert gilt für die LCR?",
                ],
                ["115 %", "125 %"],
            ),
            F(
                "tr.survival",
                "Stresstests",
                [
                    "Die Überlebensperiode im kombinierten Stressszenario muss mindestens {v} betragen.",
                ],
                [
                    "Wie lang muss die Überlebensperiode im kombinierten Stressszenario mindestens sein?",
                ],
                ["30 Tage", "60 Tage"],
            ),
        ),
        topic="die Steuerung und Überwachung des Liquiditätsrisikos",
    ),
    Policy(
        "RL-VT-01",
        "Beschwerdemanagement",
        "VT",
        2,
        ("VT", "CO", "RV"),
        (D(2022, 2, 1), D(2025, 5, 1)),
        (
            F(
                "vt.complaint_ack",
                "Eingangsbestätigung",
                [
                    "Der Eingang einer Kundenbeschwerde ist innerhalb von {v} schriftlich zu bestätigen.",
                ],
                [
                    "In welcher Frist muss der Eingang einer Kundenbeschwerde bestätigt werden?",
                ],
                ["5 Geschäftstagen", "2 Geschäftstagen"],
            ),
            F(
                "vt.complaint_answer",
                "Beantwortung",
                [
                    "Beschwerden zu Zahlungsdiensten sind innerhalb von {v} abschließend zu beantworten.",
                ],
                [
                    "Bis wann müssen Beschwerden zu Zahlungsdiensten beantwortet sein?",
                ],
                ["15 Geschäftstagen", "15 Geschäftstagen"],
            ),
        ),
        topic="die Bearbeitung von Kundenbeschwerden",
    ),
    Policy(
        "RL-VT-02",
        "Anlageberatung und Dokumentation",
        "VT",
        2,
        ("VT", "CO", "RV"),
        (D(2021, 9, 1), D(2024, 4, 1)),
        (
            F(
                "vt.call_recording",
                "Aufzeichnung",
                [
                    "Telefongespräche im Rahmen der Anlageberatung werden aufgezeichnet und {v} aufbewahrt.",
                ],
                [
                    "Wie lange werden aufgezeichnete Beratungsgespräche aufbewahrt?",
                ],
                ["5 Jahre", "7 Jahre"],
            ),
            F(
                "vt.suitability",
                "Geeignetheitserklärung",
                [
                    "Die Geeignetheitserklärung ist dem Kunden {v} zur Verfügung zu stellen.",
                ],
                [
                    "Wann muss der Kunde die Geeignetheitserklärung erhalten?",
                ],
                ["vor Ausführung des Geschäfts", "vor Ausführung des Geschäfts"],
                "text",
            ),
        ),
        topic="die Anlageberatung und ihre Dokumentation",
    ),
    Policy(
        "RL-EK-01",
        "Einkaufs- und Vergaberichtlinie",
        "EK",
        2,
        ("alle",),
        (D(2022, 3, 1), D(2025, 3, 1)),
        (
            F(
                "ek.quotes",
                "Vergleichsangebote",
                [
                    "Ab einem Auftragswert von {v} sind mindestens drei Vergleichsangebote einzuholen.",
                ],
                [
                    "Ab welchem Auftragswert braucht man drei Vergleichsangebote?",
                ],
                ["5.000 EUR", "10.000 EUR"],
            ),
            F(
                "ek.tender",
                "Ausschreibungen",
                [
                    "Aufträge mit einem Wert über {v} sind über den Einkauf auszuschreiben.",
                ],
                [
                    "Ab welchem Auftragswert muss der Einkauf eine Ausschreibung durchführen?",
                ],
                ["100.000 EUR", "150.000 EUR"],
            ),
        ),
        topic="die Beschaffung von Waren und Dienstleistungen",
    ),
    Policy(
        "RL-RI-01",
        "Neue-Produkte-Prozess",
        "RI",
        2,
        ("RI", "VT", "TR", "CO", "RV"),
        (D(2022, 11, 1), D(2025, 8, 1)),
        (
            F(
                "ri.npp_review",
                "Nachschau",
                [
                    "Neue Produkte werden {v} nach ihrer Einführung einer Nachschau durch das Risikocontrolling unterzogen.",
                ],
                [
                    "Wann nach der Einführung wird ein neues Produkt nachgeschaut?",
                ],
                ["12 Monate", "6 Monate"],
            ),
            F(
                "ri.npp_test",
                "Testphase",
                [
                    "Eine Testphase für neue Produkte darf höchstens {v} dauern.",
                ],
                [
                    "Wie lange darf die Testphase eines neuen Produkts höchstens dauern?",
                ],
                ["3 Monate", "3 Monate"],
            ),
        ),
        topic="die Einführung neuer Produkte und Märkte",
    ),
)


@dataclass(frozen=True)
class Circular:
    """A simulated supervisory circular ("Aufsichtsmitteilung"); not a real regulator's text."""

    ref: str
    title: str
    versions: tuple[date, ...]
    paragraphs: tuple[tuple[str, tuple[str, ...]], ...]  # (Tz, text per version)


CIRCULARS: tuple[Circular, ...] = (
    Circular(
        "AM 2/2024",
        "Aufsichtsmitteilung 2/2024 zur Meldung schwerwiegender IKT-Vorfälle (simuliert)",
        (D(2024, 3, 1), D(2025, 1, 17)),
        (
            ("1", ("Diese Mitteilung gilt für alle Institute im Anwendungsbereich.",) * 2),
            (
                "5",
                (
                    "Schwerwiegende IKT-Vorfälle sind innerhalb von 24 Stunden nach ihrer Einstufung erstmals zu melden.",
                    "Schwerwiegende IKT-Vorfälle sind innerhalb von 4 Stunden nach ihrer Einstufung, spätestens jedoch 24 Stunden nach Kenntnis, erstmals zu melden.",
                ),
            ),
            ("6", ("Ein Zwischenbericht folgt innerhalb von 72 Stunden nach der Erstmeldung.",) * 2),
        ),
    ),
    Circular(
        "AM 1/2023",
        "Aufsichtsmitteilung 1/2023 zu Auslagerungen (simuliert)",
        (D(2023, 2, 1), D(2026, 2, 1)),
        (
            ("3", ("Wesentliche Auslagerungen sind in einem Auslagerungsregister zu erfassen.",) * 2),
            (
                "8",
                (
                    "Beabsichtigte wesentliche Auslagerungen sind mindestens vier Wochen vor Vertragsbeginn anzuzeigen.",
                    "Beabsichtigte wesentliche Auslagerungen sind mindestens sechs Wochen vor Vertragsbeginn anzuzeigen.",
                ),
            ),
        ),
    ),
)


@dataclass(frozen=True)
class Truth:
    """What a rule said on a date: value, document, version and paragraph number."""

    fact: str
    value: str
    doc_no: str
    version: int
    tz: str
    valid_from: date
    valid_to: date | None


@dataclass
class World:
    policies: tuple[Policy, ...] = POLICIES
    circulars: tuple[Circular, ...] = CIRCULARS
    users: tuple[User, ...] = USERS
    # paragraph numbers are assigned when the documents are laid out (render.layout)
    tz: dict[tuple[str, str], str] = field(default_factory=dict)

    def policy(self, doc_no: str) -> Policy:
        return next(p for p in self.policies if p.doc_no == doc_no)

    def fact(self, fact_id: str) -> tuple[Policy, Fact]:
        for p in self.policies:
            for f in p.facts:
                if f.id == fact_id:
                    return p, f
        raise KeyError(fact_id)

    def version_on(self, p: Policy, on: date) -> int | None:
        """1-based version in force on a date, or None before the first version."""
        current = None
        for i, start in enumerate(p.versions, start=1):
            if start <= on:
                current = i
        return current

    def truth(self, fact_id: str, on: date) -> Truth | None:
        p, f = self.fact(fact_id)
        v = self.version_on(p, on)
        if v is None:
            return None
        valid_to = p.versions[v] if v < len(p.versions) else None
        return Truth(fact_id, f.values[v - 1], p.doc_no, v, self.tz[(p.doc_no, f.id)], p.versions[v - 1], valid_to)


def can_read(user: User, p: Policy) -> bool:
    """The access rule the platform must enforce (it implements it independently)."""
    if user.clearance < p.level:
        return False
    return user.auditor or "alle" in p.audience or any(d in p.audience for d in user.departments)
