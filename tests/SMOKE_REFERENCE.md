# Manuelle Smoke-Referenz (Verhaltens-Vertrag)

Diese Liste dient dazu, nach den Refactor-Stages (besonders S4a/S4b) den **Live-Output**
im echten Twitch-Chat stichprobenartig gegen das Verhalten VOR dem Refactor zu prüfen.
Der automatisierte Teil (Registry, #help, Output-Primitiven) läuft über `pytest`.

## So prüfen
1. Bot lokal starten (`LOCAL_MODE=true`), in einen Test-Channel joinen.
2. Jeden Command unten absenden, Output notieren.
3. Nach dem Refactor exakt wiederholen — der Output muss **byte-identisch** sein
   (gleicher `@user, `-Prefix, gleiche Separatoren `" | "` / `", "`, gleiche Zahlen-Formatierung).

## Vertrag (darf sich NIE ändern)
- Jede Antwort beginnt mit `@{username}, ` (siehe `send_message`).
- Zahlen-Formatierung via `format_number`: K/M/B mit 2 Nachkommastellen.
- `#help`-Output inkl. `' | made by Iceshadow_'` (durch pytest eingefroren).
- Auctions-Liste wird bei `MAX_MESSAGE_LENGTH` (480) gekürzt (`commands/auction_house.py`).

## Referenz-Commands (mit einem realen IGN, z.B. dem eigenen)
| Command | Fokus | Prä-Refactor-Output (hier eintragen) |
|---|---|---|
| `#skills <ign>` | Skill-Average + `" | "`-Liste | |
| `#sa <ign>` | Alias von skills | |
| `#bank <ign>` | Zahlen-Formatierung, `", "`-Parts | |
| `#ca <ign>` | classaverage (klassenbasiert) | |
| `#roll` | Zufalls-Range 1–1000 | |
| `#roll 5 10` | Arg-Parsing (2 Args) | |
| `#networth <ign>` | **Node-Service :3000** | |
| `#help` | Command-Liste (auto-getestet) | |
| `#skills a b c` | "Too many arguments"-Pfad (S4b!) | |
| `#guild <ign>` | funktionsbasiert | |
| `#status` | `_hypxiel_command` (Typo, S4b) | |

> Hinweis: `#networth` hängt am Node-Service auf `http://localhost:3000` (`networth.js`).
> Vor dem Test sicherstellen, dass dieser läuft (via `start.sh` oder `node networth.js`).
