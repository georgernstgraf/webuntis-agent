# Domain Knowledge

Business rules and domain relationships not obvious from code.

## Entities

- **Period**: A single school hour (e.g. 13:25–14:15). Has `periodId`, `lsId` (lesson block), `hr` (hour number), `class`, `subject`, `date`, `time`.
- **Lesson Block (lsId)**: A group of periods forming one continuous lesson (e.g. 13:25+14:25 = 2-period block). One PUT updates ALL periods in the block.
- **Topic**: The Lehrstoff (lesson topic) entry for a period. Has `id` (topicId), `periodId`, `text`, `attachments`. May be `null` (no topic row yet → create with `id: 0`).
- **Open Period**: A period where the teacher still owes a topic (`topicNeeded=true`) or absence check (`absCheckNeeded=true`). Filter: `TOPIC_OR_ABSENCE_OPEN`.
- **Teacher**: Identified by `person_id` from JWT. Used as `teacherId` in open-periods query.
- **Schoolyear**: Has `id`, `name` (e.g. "2025/2026"), `dateRange` ({start, end}). Current schoolyear id derived from date range match.

## GRG-* Repository Structure

- **GRG-WMC**: Web & Mobile Computing — classes 3aaif, 3akif, 3bkif, 3caif, 4aaif, 4akif, 4bkif, 4caif
- **GRG-SWP**: Softwareentwicklung und Projektmanagement — classes 2ahwii, 3ahwii, 5ahwii (split into _X/_Y)
- **GRG-INFI**: Informatik und Informationssysteme — class 2ahwii
- **GRG-POSTHEORIE**: POS-Theorie (PrOgrammieren und Software) — classes 4baif, 6acif; uses PDF folien not per-lesson folders
- **GRG-JAVA**: Java-Programmierung — class 3aaif
- **GRG-CS**: Computer Science — class 3ahwii (C# OOP, NOT in GRG-SWP despite SWP subject)
- **-T suffix**: Teacher-only companion repo (same classes as main repo)

## Class Name Rules

- **Abteilungs-/Formklassen** (suffix aif, cif, kif): advance year in February (3aaif→4aaif, 3bkif→4bkif)
- **Tagesklassen** (suffix hwii, hwit): keep name across February
- **Split classes**: `5ahwii_X` and `5ahwii_Y` = two groups of the same class, taught separately
- **Cross-repo anomaly**: 3AHWII SWP1x content is in GRG-CS (C#), not GRG-SWP (Deno/TS). The `3HWII/` folder in GRG-SWP is next year's planning.

## WebUntis Subject Mapping

| WebUntis subject | Full name | GRG repos |
|---|---|---|
| POS1/POS | Programmieren und Softwareengineering | GRG-POSTHEORIE, GRG-JAVA |
| SWP1x/SWP1y/SWP1 | Softwareentwicklung und Projektmanagement | GRG-SWP (and GRG-CS for 3AHWII) |
| WMC_1/WMC1 | Webprogrammierung und Mobile Computing | GRG-WMC |
| INFIx/INF | Informatik und Informationssysteme | GRG-INFI |
| CS | Computer Science | GRG-CS |
| SS | Sprech- & Supplierbereitschaft | (none — skip) |
| BESP | Berufsspezifische Praxis | (none — skip, ask user) |

## Lesson Topic Derivation Priority

1. Git folder names with date prefix (e.g. `2025-10-02_cases_click_images/`) — highest confidence
2. README files with dated entries (e.g. `## 2025-10-06 Tests`)
3. Git diffs (`git show <hash>`) — actual file content
4. PDF folien (POS-Theorie: Folien_WS=Graphen, Folien_SS=Algorithmen)
5. Parallel classes (same subject, same curriculum)
6. Dummy text: `(kein Unterricht gefunden für <class> am <date>)`
