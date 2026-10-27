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

## The second connection: an Oracle practice schema

The **Connection** selector in the title bar offers two sessions:

| Connection | Character | Data changes |
| --- | --- | --- |
| `NIST_UNIVERSITY` | the portal's own database, SQLite 3 | read-only: reads run, writes are prepared and declined |
| `ORACLE_XE` | a **practice schema** in the Oracle dialect, user `STUDIO` | **writable**: `CREATE`, `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, sequences, views, indexes and comments really happen |

`ORACLE_XE` exists because the portal is a teaching system and the Oracle
syllabus is full of statements the read-only portal session must refuse.
Switching the selector swaps the navigator, the starter worksheet, the
snippets, the connection facts in the Messages pane, the status bar and the
badge in the title bar (**Read-only session** / **Practice schema · writable**).
The two sessions remember their own worksheet text.

The practice schema arrives as the classic SCOTT demonstration: `DEPT` (4
rows), `EMP` (14 rows), `EMP_DEPTNO_IDX`, `EMP_SEQ` (next value 8000) and four
`COMMENT ON` entries. **Reset practice schema** in the toolbar drops everything
you created and seeds it again.

### What really runs

`SELECT` — including `DUAL`, `ROWNUM`, `FETCH FIRST n ROWS ONLY`,
`OFFSET … FETCH`, `NVL`, `NVL2`, `DECODE`, `TO_CHAR`, `TO_DATE`, `TO_NUMBER`,
`MOD`, `TRUNC`, `LISTAGG … WITHIN GROUP`, `MINUS`, `SYSDATE`, `USER`;
`CREATE / DROP / ALTER TABLE` with `NUMBER`, `VARCHAR2`, `CHAR`, `DATE`,
`CLOB`, `DEFAULT`, `NOT NULL`, `PRIMARY KEY`, `UNIQUE`, `CHECK`,
`REFERENCES`, `GENERATED BY DEFAULT AS IDENTITY`;
`INSERT`, `UPDATE`, `DELETE`; `CREATE / DROP SEQUENCE` with `NEXTVAL` and
`CURRVAL`; `CREATE VIEW`, `CREATE INDEX`, `COMMENT ON TABLE|COLUMN`,
`DESCRIBE`, `EXPLAIN PLAN FOR`.

Every statement is shown twice: what you wrote, and the *translated and
executed* SQL that the embedded engine actually received. Nothing is hidden.

### What is refused, and why

| Statement | Reply |
| --- | --- |
| `MERGE`, `CONNECT BY`, `PIVOT`, `UNPIVOT`, `MODEL` | `ORA-00933` with a pointer to the workshop page |
| PL/SQL blocks, procedures, functions, triggers, packages, types | `ORA-00933` — this is a practice schema, not a server with a PL/SQL engine |
| `COMMIT`, `ROLLBACK`, `SAVEPOINT` | `ORA-01086` — every statement commits as it runs |
| `ATTACH`, `PRAGMA`, `VACUUM`, `REINDEX` | `ORA-01031` — the practice file stays its own file |

Errors are Oracle errors, not engine errors: `ORA-00942` *table or view does
not exist*, `ORA-00904` *invalid identifier*, `ORA-00955` *name is already used*,
`ORA-00001` *unique constraint violated*, `ORA-01400` *cannot insert NULL*,
`ORA-02291` *integrity constraint violated — parent key not found*,
`ORA-02290` *check constraint violated*, `ORA-01418` *index does not exist*,
`ORA-02289` *sequence does not exist*, `ORA-08002` *CURRVAL is not yet defined*.

### The honest disclosure

PythonAnywhere's free tier — where this portal is deployed — runs no Oracle
server: there is no listener, no 512 MiB to hold an instance, and no network
route to one. `ORACLE_XE` is therefore a **simulation**: the dialect, the
column folding, the error codes and the write behaviour are faithful, the
server is not Oracle's. The dialog behind **Tools → Oracle practice schema**,
the connection facts and the title-bar badge say so, so nobody presenting the
tool can accidentally claim otherwise.

`repositories/oracle.py` keeps the practice file at `instance/studio_oracle.db`
(override with `STUDIO_ORACLE_PATH`). It refuses outright to open the portal's
own database, so a bad setting cannot point the writable session at live rows.

### Using it in front of an audience

1. Switch the connection to `ORACLE_XE`; the worksheet fills with the starter
   script — four `SELECT`s, a `CREATE TABLE`, two `INSERT`s, a `SELECT`, a
   `COMMENT` and a `DESCRIBE`.
2. Press `F5`. Every line in **Script output** reports success and the
   navigator grows a `PROJECT` table without a reload.
3. Run `DESCRIBE project` and point at the `NUMBER(6)` / `VARCHAR2(60)` types —
   the Oracle types, not SQLite's.
4. Run `SELECT * FROM project WHERE ROWNUM <= 1`, then break it on purpose
   (`SELECT nope FROM project`) and show `ORA-00904`.
5. **Reset practice schema** to put the demonstration back for the next person.

## Undo, redo — and taking back a real change

**In the worksheet.** Every worksheet keeps its own stack of edits: text *and*
caret position. The toolbar's **Undo** / **Redo** buttons, `Ctrl` + `Z`,
`Ctrl` + `Shift` + `Z` (or `Ctrl` + `Y`) and the Edit menu all step through it.
Typing is coalesced on a short timer, so one press takes back a burst rather
than a single character; **Format**, **Comment**, **Clear**, a snippet insert and
a connection switch are each recorded as one step. The stack belongs to the
worksheet, so switching tabs does not mix them, and its tail is saved with the
worksheet — reload the page and you can still undo what you typed before it.

**In the practice schema.** A statement that changes `ORACLE_XE` can be taken
back for real. Before every writable statement the studio freezes the practice
file (it is about 60 KB, so the snapshot is cheap); **Undo this change** appears
on the card under the result, and **Tools → Undo practice change**
(`Ctrl` + `Alt` + `Z`) walks back up to twelve changes. **Redo practice change**
(`Ctrl` + `Alt` + `Y`) replays the one you took back, and a new statement clears
the redo stack, the way any editor does. Reads never take a snapshot, a
statement that fails leaves none, and **Reset practice schema** clears the
journal. Restoring works at the file level, so a dropped table, a deleted row
and a new index all come back exactly as they were — metadata, sequences and
comments included.

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
database and shows the prepare step a real client performs. The table above
describes the **portal** connection — the Oracle practice connection on the
same screen is writable, but only inside its own file.

Studio runs are also kept out of the change log (`g.activity_skip`), so
demonstrating the tool never fabricates an audit trail.

## Where the code lives

| File | Purpose |
| --- | --- |
| `routes/studio.py` | Blueprint: the page, the four portal JSON endpoints (`/studio/run`, `/studio/script`, `/studio/explain`, `/studio/describe/<object>`), the seven practice endpoints (`/studio/oracle/run`, `/script`, `/explain`, `/tree`, `/reset`, `/undo`, `/redo`) and the menu definitions. |
| `repositories/studio.py` | Connection facts, the catalogue for the navigator, statement classification, the read-only runner, the script splitter, the plan tree and the object describer. |
| `templates/studio/index.html` | The window: title bar, menus, toolbar, navigator tree, worksheets, editor, four result panes, status bar, popovers, context menu, tour and dialogs. |
| `static/css/studio.css` | The client theme (tokens, panes, grid, plan, tour). |
| `static/js/studio.js` | Editor highlighting and gutter, worksheet state, menus, popovers, grid sorting, CSV export, plan rendering, history, tour, shortcuts. |
| `repositories/oracle.py` | The Oracle practice connection: seed, translation, error mapping, sequences, `DESCRIBE`, plans, catalogue, reset. |
| `tests/test_studio.py` | 24 tests: access, reads, masking, prepared writes, refusals, script splitting, plans, describe, change-log isolation. |
| `repositories/dialect.py` | Oracle SQL on every screen: recognises an Oracle-only statement, translates it with the studio's translator, passes anything else through untouched. |
| `tests/test_dialect.py` | 23 tests: `ROWNUM`, `DUAL`, `NVL`, `DECODE`, `TO_CHAR`, `FETCH FIRST`, `MINUS`, `LISTAGG` on the portal tables, passthrough, the switch, the journal, undo/redo over HTTP and access control. |
| `tests/test_oracle.py` | 31 tests: the seeded schema, reads and functions, DDL/DML round trips, sequences, `DESCRIBE`, Oracle error codes, refusals, the starter script, reset, the HTTP endpoints and access control. |
