Open tasks:

None.

Erledigt (Session 2026-09-21, committed):
- Man-Page `man/wu.1` + Drift-Test + AGENTS.md/README-Verweis (#20).
- `/open-periods`-Re-Record (20260921-231543) ausgewertet: UI-Route ruft
  exakt POST classreg/open-periods (OnLoad heute..heute, Schuljahr-Wahl
  Start..heute); neu: GET open-periods/meta. `--von/--bis` bei allen
  `offen`-Befehlen optional, Default Schuljahr-Start..heute (#21).
  Suite 83/83 grün.

Review-Basis für den nächsten Lauf:
- Domain-CLI-Serie committed als 7f69335 (#17), davor 72c9bc2 (#16).
- Stundenplan-Serie committed als 9d5c30a (#18), inkl. Live-Write-Paar
  (Absenz setzen+löschen am WMC-Termin 2026-09-25, beide Wege — insert
  + entfernen via Schüler-Lookup — verifiziert, netto null).
  Review ab `git diff 7f69335...9d5c30a`.
- Man-Page + offen-Default als (#20, #21) committed (Hash s.
  `git log`).
- Follow-up als Issue angelegt: #22 `raum suchen` (Freie-Raum-Suche:
  ROOM-entries je Slot + capacity-Filter aus rooms/form;
  `availability`-Semantik klären — beide aufgenommenen Slots lieferten
  durchgehend NONE).

Last updated: 2026-09-21
