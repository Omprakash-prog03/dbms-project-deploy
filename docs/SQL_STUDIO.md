# SQL Studio — the simulated database client

`/studio` is an administrator screen that behaves like a desktop database client.
It exists so that "how does the database actually work?" can be answered by
*using* it in front of an audience, not by showing a screenshot.

Everything on the screen is live: the navigator is read from the engine's own
catalogue, statements run against the same database the portal uses, the result
grid holds the rows the engine returned, and the execution plan is the
optimiser's, not a drawing of one.

```
┌ title bar ─────────────────────────────────────────────────────────────────┐
│ SQL Studio   NIST University · 20 tables · 5 views                          │
│              Connection: NIST_UNIVERSITY · SQLite 3.40.1   READ-ONLY       │
├ menu bar ──────────────────────────────────────────────────────────────────┤
│ File   Edit   Worksheet   Tools   Help                       admin@NIST_UNI │
├ toolbar ───────────────────────────────────────────────────────────────────┤
│ +  ▷ Run statement F9  ▷ Run script F5  ▞ Explain F10 │ ✓ Commit ↻ Roll back │
│ Format  Comment  Clear                                  Snippets  History  │
├───────────────┬────────────────────────────────────────────────────────────┤
│ Connections   │ Worksheet 1 ×   +                    right-click to rename │
│ [filter…]     ├────────────────────────────────────────────────────────────┤
│ ▾ NIST_UNI…   │ 1 SELECT s.roll_no, s.first_name …                          │
│   ▾ Tables 20 │ 2 FROM student s                                            │
│     ▸ student │ 3 JOIN department d ON d.dept_id = s.dept_id                │
│     ▸ result  ├────────────────────────────────────────────────────────────┤
│   ▸ Views   5 │ Results 25 │ Script output │ Explain │ Messages            │
│   ▸ Indexes   │ # ROLL_NO      STUDENT            DEPT_CODE   SEMESTER …   │
│   ▸ Triggers  │ 1 23CIVIL133   Mitesh Sengupta     CIVIL       7            │
│   ▸ Proced…   │ …                                                          │
├───────────────┴────────────────────────────────────────────────────────────┤
│ ● admin@NIST_UNIVERSITY  Ln 1, Col 1  25 rows  1 ms   READ-ONLY  SQLite    │
└────────────────────────────────────────────────────────────────────────────┘
```

## The five parts of the window

| Part | What it does |
| --- | --- |
| **Navigator** | Every table (with its columns, types, PK/NN marks and foreign keys), view, index, trigger, procedure and function. Filter box; expand/collapse; right-click for object actions; double-click a table to insert a `SELECT`, double-click a column to insert its name. |
| **Worksheet tabs** | Up to eight worksheets, each with its own text, kept in `localStorage` so a reload does not lose work. New, duplicate, rename (double-click the tab), close. |
| **Editor** | Line gutter, SQL syntax colour, Tab indent, auto-indent on Enter, `Ctrl`/`⌘` + `/` to comment a block, **Format** to normalise a worksheet. The statement under the cursor is what `F9` runs. |
| **Result panes** | **Results** (sortable grid, sticky row numbers, `NULL` styling, copy/save as CSV), **Script output** (one line per statement with its timing), **Explain** (the optimiser's steps, indented, labelled *scan* or *index*), **Messages** (errors and notices, connection facts). |
| **Status bar** | Connection and user, cursor position, rows, elapsed milliseconds, read-only mode, engine version and character set. |

## Menus, dialogs and the guided tour

- **File** — new / duplicate / rename / close worksheet, save or copy results as CSV.
- **Edit** — undo, redo, select all, copy worksheet, comment / uncomment.
- **Worksheet** — run, run script, explain, format, clear, snippets, statement history.
- **Tools** — object details, connection information, collapse / expand the navigator.
- **Help** — **guided tour**, keyboard shortcuts, why the session is read-only, About.

The **guided tour** is the "watch the software being used" mode: it dims the
window, draws a ring around one part at a time, explains it, and — for the
worksheet and results steps — writes a query and runs it so the audience sees
the grid fill. When the tour ends, the editor is restored to exactly what it
held before.

## Keyboard

| Keys | Action |
| --- | --- |
| `F9` / `Ctrl`+`Enter` | Run the statement under the cursor |
| `F5` | Run every statement in the worksheet |
| `F10` | Explain the statement under the cursor |
| `Ctrl`+`T` / `Ctrl`+`W` | New worksheet / close worksheet |
| `Ctrl`+`/` | Comment or uncomment the selected lines |
| `Ctrl`+`Space` | Snippet list |
| `F1` | Keyboard shortcuts |
| `←` `→` | Previous / next tour step while the tour is open |
| `Esc` | Close a menu, popover, dialog or the tour |

## The safety model

A client that can run anything can break anything. This one draws the line
where the portal stays safe, and says so in the interface:

| Statement | Behaviour |
| --- | --- |
| `SELECT`, `WITH`, `VALUES`, `TABLE`, `EXPLAIN` | Runs for real against the live rows. Results are capped at 300 shown rows and the grid says so. |
| `INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE` | **Prepared, not run.** The engine compiles the statement with `EXPLAIN`, which proves the syntax, the table and the columns without touching a row; the studio reports *Statement prepared successfully* and records that nothing was committed. |
| `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `PRAGMA`, `ATTACH`, `VACUUM`, `BEGIN`, `COMMIT`, `ROLLBACK`, `SET`, `CALL`… | Refused with `STUDIO-002`. A typo must not be able to damage the schema or the session. |
| Writes to `login_history` / `staff_activity` | Refused with `STUDIO-004`. The two registers are append-only for every client, including this one. |

To change data for real, the portal screens or the SQL console
(`/raw-data/query`) are the tools; the studio explains the read side of the
database and shows the prepare step a real client performs.

Studio runs are also kept out of the change log (`g.activity_skip`), so
demonstrating the tool never fabricates an audit trail.

## Where the code lives

| File | Purpose |
| --- | --- |
| `routes/studio.py` | Blueprint: the page, the four JSON endpoints (`/studio/run`, `/studio/script`, `/studio/explain`, `/studio/describe/<object>`) and the menu definitions. |
| `repositories/studio.py` | Connection facts, the catalogue for the navigator, statement classification, the read-only runner, the script splitter, the plan tree and the object describer. |
| `templates/studio/index.html` | The window: title bar, menus, toolbar, navigator tree, worksheets, editor, four result panes, status bar, popovers, context menu, tour and dialogs. |
| `static/css/studio.css` | The client theme (tokens, panes, grid, plan, tour). |
| `static/js/studio.js` | Editor highlighting and gutter, worksheet state, menus, popovers, grid sorting, CSV export, plan rendering, history, tour, shortcuts. |
| `tests/test_studio.py` | 24 tests: access, reads, masking, prepared writes, refusals, script splitting, plans, describe, change-log isolation. |
