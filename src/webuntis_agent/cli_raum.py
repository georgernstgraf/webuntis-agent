"""CLI raum-Befehle: Raumsuche und Raumgrößen (vorbereitet, Stubs).

Die Endpunkte sind reverse-engineered und dokumentiert
(docs/WEBUNTIS_API.md: timetable/entries mit resourceType=ROOM,
calendar-entry/rooms/form mit `capacity` je Raum). Die Umsetzung
(Freie-Raum-Suche je Stunde + Kapazitätsfilter) ist als Folgeissue
geplant — diese Stubs reservieren das CLI-Vokabular und zeigen
eindeutig "not implemented" (Exit 3).
"""

from __future__ import annotations

import argparse
import sys

_NOT_IMPLEMENTED = (
    "noch nicht implementiert — Endpunkte sind dokumentiert "
    "(docs/WEBUNTIS_API.md § Räume), Umsetzung als Folgeissue geplant"
)


def cmd_raum_suchen(args: argparse.Namespace) -> int:
    """Freien Raum für eine Stunde suchen (geplant, noch ein Stub).

    Geplante Semantik: Räume, die zu --datum in der --stunde. Schulstunde
    frei sind (Belegung via ROOM-Stundenplan) und die Kapazitätsfilter
    erfüllen (--min-plaetze / --max-plaetze, z.B. klein < 20 oder
    groß >= 36). --nur-freie blendet belegte Räume aus.
    """
    print(f"raum suchen: {_NOT_IMPLEMENTED}", file=sys.stderr)
    print("geplant: freie Räume je Schulstunde + Kapazitätsfilter "
          "(rooms/form liefert capacity je Raum)", file=sys.stderr)
    return 3


def cmd_raum_groesse(args: argparse.Namespace) -> int:
    """Sitzplätze eines Raums anzeigen (geplant, noch ein Stub).

    Geplante Semantik: capacity (Sitzplätze) + Gebäude/Typ eines Raums
    aus calendar-entry/rooms/form.
    """
    print(f"raum groesse {args.raum}: {_NOT_IMPLEMENTED}", file=sys.stderr)
    return 3
