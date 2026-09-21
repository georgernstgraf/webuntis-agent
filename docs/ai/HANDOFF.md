Open tasks:

- Live-Absenz-Write-Verifikation: `lesson 3BAIF/WMC_1 absenzen
  eintragen --schueler-name "…" --datum 2026-09-25 --ausfuehren`
  gefolgt von `absenzen entfernen --absenz-id <id> --termin-id
  <PERIOD_ID> --ausfuehren` (Setzen+Löschen-Paar, netto null; PERIOD_ID
  z.B. aus `absenzen zeigen --termin-id`) — nur nach Nutzer-Go
  ausführen.
- Serie committen (inkl. Issue-Referenz wie bisher), danach:
  Folgeissue `raum suchen` (Freie-Raum-Suche: ROOM-entries je Slot +
  capacity-Filter aus rooms/form; `availability`-Semantik klären —
  beide aufgenommenen Slots lieferten durchgehend NONE).

Review-Basis für den nächsten Lauf:
- Domain-CLI-Serie committed als 7f69335 (#17), davor 72c9bc2 (#16).
- Stundenplan-Serie committed als 9d5c30a (#18). Review ab
  `git diff 7f69335...9d5c30a`.

Last updated: 2026-09-21
