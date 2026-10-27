# SQL Studio — the database client, linked to the portal

`/studio` is an administrator screen that behaves like a desktop database client.
It exists so that "how does the database actually work?" can be answered by
*using* it in front of an audience, not by showing a screenshot.

Everything on the screen is live: the navigator is read from the engine's own
catalogue, statements run against the same database the portal uses, the result
grid holds the rows the engine returned, and the execution plan is the
optimiser's, not a drawing of one.

The window is **wired to the portal**. A row inserted here is the row the
Students, Fees and Reports screens show on their next load; a table created here
appears in Raw data; a row deleted here is gone from the portal. Every statement
that writes is snapshotted first, so one click of **Undo change** puts the
database back exactly as it was.

```
┌ title bar ─────────────────────────────────────────────────────────────────┐
│ SQL Studio   NIST University · 20 tables · 5 views                          │
│              Connection: NIST_UNIVERSITY · SQLite 3.40.1   WRITABLE       │
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
│ ● admin@NIST_UNIVERSITY  Ln 1, Col 1  25 rows  1 ms   WRITABLE  SQLite    │
└────────────────────────────────────────────────────────────────────────────┘
```

## The five parts of the window

| Part | What it does |
| --- | --- |
| **Navigator** | Every table (with its columns, types, PK/NN marks and foreign keys), view, index, trigger, procedure and function. Filter box; expand/collapse; right-click for object actions; double-click a table to insert a `SELECT`, double-click a column to insert its name. |
| **Worksheet tabs** | Up to eight worksheets, each with its own text, kept in `localStorage` so a reload does not lose work. New, duplicate, rename (double-click the tab), close. |
| **Editor** | Line gutter, SQL syntax colour, Tab indent, auto-indent on Enter, `Ctrl`/`⌘` + `/` to comment a block, **Format** to normalise a worksheet. The statement under the cursor is what `F9` runs. |
| **Result panes** | **Results** (sortable grid, sticky row numbers, `NULL` styling, copy/save as CSV), **Script output** (one line per statement with its timing), **Explain** (the optimiser's steps, indented, labelled *scan* or *index*), **Messages** (errors and notices, connection facts). |
| **Status bar** | Connection and user, cursor position, rows, elapsed milliseconds, writable/undoable mode, engine version and character set. |

## Menus, dialogs and the guided tour

- **File** — new / duplicate / rename / close worksheet, save or copy results as CSV.
- **Edit** — undo, redo, **undo / redo the last database change**, select all, copy worksheet, comment / uncomment.
- **Worksheet** — run, run script, explain, format, clear, snippets, statement history.
- **Tools** — object details, connection information, collapse / expand the navigator.
- **Help** — **guided tour**, keyboard shortcuts, what this window may change, About.

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
| `Ctrl`+`Alt`+`Z` / `Ctrl`+`Alt`+`Y` | Undo / redo the last database change (either connection) |
| `Ctrl`+`Space` | Snippet list |
| `F1` | Keyboard shortcuts |
| `←` `→` | Previous / next tour step while the tour is open |
| `Esc` | Close a menu, popover, dialog or the tour |

## The second connection: an Oracle practice schema

The **Connection** selector in the title bar offers two sessions:

| Connection | Character | Data changes |
| --- | --- | --- |
| `NIST_UNIVERSITY` | the portal's own database, SQLite 3 | **writable and undoable**: `INSERT`, `UPDATE`, `DELETE` and `CREATE` really run and commit, so the change is on the portal's screens immediately |
| `ORACLE_XE` | a **practice schema** in the Oracle dialect, user `STUDIO` | **writable**: `CREATE`, `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, sequences, views, indexes and comments really happen — in its own file, never the portal's |

`ORACLE_XE` exists because the portal is a teaching system and the Oracle
syllabus is full of statements that would be reckless to run against live
student records.
Switching the selector swaps the navigator, the starter worksheet, the
snippets, the connection facts in the Messages pane, the status bar and the
badge in the title bar (**Live data · linked to the portal** / **Practice schema
· writable**). The two sessions remember their own worksheet text *and* their
own undo stacks.

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

## Linked to the portal

The portal connection is the portal's own database, seen through a client.
What that means in practice:

| Action in the studio | What the portal shows |
| --- | --- |
| `INSERT INTO student (…)` | The student is on **Students** on the next load, and in every report and export. |
| `UPDATE result SET marks = …` | The grade, the CGPA and the transcript PDF all read the new value. |
| `DELETE FROM fee_payment WHERE …` | The payment is gone from **Fees** and from the fee report. |
| `CREATE TABLE studio_report (…)` | The table is in **Raw data** and in the studio's navigator, marked *studio*. |
| `DROP TABLE studio_report` | Allowed, because this client created it. |
| `DROP TABLE student` | Refused (`STUDIO-007`). The portal's own tables cannot be dropped, altered or truncated from here. |
| `INSERT INTO login_history …` | Refused (`STUDIO-004`). The register and the change log are append-only for every client. |

Ownership is recorded on disk (`<sqlite dir>/studio_portal_journal/created.json`)
the first time the studio creates an object. Everything the studio did not create
counts as the portal's — including tables added by a later migration — so the
safe default is the one that wins.

The portal's 20 tables are listed in **Messages → connection facts**, next to the
journal depth and the label of the last change, so the presenter can see at a
glance what may be touched and what may not.

## Undo, redo — and taking back a real change

**In the worksheet.** Every worksheet keeps its own stack of edits: text *and*
caret position. The toolbar's **Undo** / **Redo** buttons, `Ctrl` + `Z`,
`Ctrl` + `Shift` + `Z` (or `Ctrl` + `Y`) and the Edit menu all step through it.
Typing is coalesced on a short timer, so one press takes back a burst rather
than a single character; **Format**, **Comment**, **Clear**, a snippet insert and
a connection switch are each recorded as one step. The stack belongs to the
worksheet, so switching tabs does not mix them, and its tail is saved with the
worksheet — reload the page and you can still undo what you typed before it.

**In the database — both connections.** A statement that writes can be taken
back for real. Before every writable statement the studio snapshots the file it
is about to change (the practice file is about 60 KB; the portal's is a few MB,
which `sqlite3`'s backup API copies in milliseconds while the portal keeps
serving). **Undo this change** appears on the card under the result, the
toolbar's **Undo change** / **Redo change** buttons and `Ctrl` + `Alt` + `Z` /
`Ctrl` + `Alt` + `Y` do the same from anywhere in the window, and each
connection has its own stack of twelve. A new statement clears the redo stack,
the way any editor does. Reads never take a snapshot, a statement that fails
leaves none, and **Reset practice schema** clears the practice journal.

Restoring works at the file level, so a dropped table, a deleted row and a new
index all come back exactly as they were — metadata, sequences and comments
included. Undo on the portal connection is what makes a live client safe to
hand to an administrator: a mistyped `DELETE FROM student WHERE …` is one click
away from being reversed.

## The safety model

A client that can run anything can break anything. This one draws the line
where the portal stays safe *and* stays workable, and says so in the interface:

| Statement | Behaviour |
| --- | --- |
| `SELECT`, `WITH`, `VALUES`, `TABLE`, `EXPLAIN` | Runs for real against the live rows. Results are capped at 300 shown rows and the grid says so. |
| `INSERT`, `UPDATE`, `DELETE`, `REPLACE`, `MERGE` | **Runs and commits.** The change is on the portal's screens immediately and the card under the result offers **Undo this change**. |
| `CREATE TABLE / VIEW / INDEX / SEQUENCE` | **Runs.** The object appears in the navigator (marked *studio*) and in Raw data, and is owned by the studio, so it may be dropped again. |
| `DROP`, `ALTER`, `TRUNCATE` of a portal table | Refused with `STUDIO-007`: the portal needs its own tables. |
| `PRAGMA`, `ATTACH`, `VACUUM`, `BEGIN`, `COMMIT`, `ROLLBACK`, `SET`, `CALL`… | Refused with `STUDIO-002`. Transaction control and engine settings would strand a database that every statement commits to. |
| Writes to `login_history` / `staff_activity` | Refused with `STUDIO-004`. The two registers are append-only for every client, including this one. |
| A write when the snapshot cannot be taken | Refused with `STUDIO-008`. If the studio cannot record an undo step, it does not take the risk. |

Studio runs are also kept out of the change log (`g.activity_skip`), so
demonstrating the tool never fabricates an audit trail; the journal under the
result is the audit trail of what the studio itself did.

The SQL console (`/raw-data/query`) remains the plain prompt for data changes —
no undo, no snapshot. This window is the safer place to experiment, and the
console is still the only way to write without a journal.

## Where the code lives

| File | Purpose |
| --- | --- |
| `routes/studio.py` | Blueprint: the page, the portal JSON endpoints (`/studio/run`, `/studio/script`, `/studio/explain`, `/studio/describe/<object>`, `/studio/tree`, `/studio/undo`, `/studio/redo`), the seven practice endpoints (`/studio/oracle/run`, `/script`, `/explain`, `/tree`, `/reset`, `/undo`, `/redo`) and the menu definitions. |
| `repositories/studio.py` | Connection facts, the catalogue for the navigator, statement classification, the portal write path (snapshot → translate → execute), object ownership, the two journals, the script splitter, the plan tree and the object describer. |
| `repositories/journal.py` | The reusable undo stack: snapshot with `sqlite3`'s backup API in both directions, an `index.json` plus one file per step, twelve steps deep. Used by the practice schema and by the portal. |
| `templates/studio/_tree_portal.html` | The portal navigator, rendered on the page and re-rendered by `/studio/tree` after a structural change. |
| `templates/studio/index.html` | The window: title bar, menus, toolbar, navigator tree, worksheets, editor, four result panes, status bar, popovers, context menu, tour and dialogs. |
| `static/css/studio.css` | The client theme (tokens, panes, grid, plan, tour). |
| `static/js/studio.js` | Editor highlighting and gutter, worksheet state, menus, popovers, grid sorting, CSV export, plan rendering, history, tour, shortcuts. |
| `repositories/oracle.py` | The Oracle practice connection: seed, translation, error mapping, sequences, `DESCRIBE`, plans, catalogue, reset. |
| `tests/test_studio.py` | 32 tests: access, reads, masking, writes that reach the portal screens, undo and redo, created tables in Raw data, portal-table protection, append-only refusals, script splitting, plans, describe, change-log isolation. |
| `repositories/dialect.py` | Oracle SQL on every screen: recognises an Oracle-only statement, translates it with the studio's translator, passes anything else through untouched. |
| `tests/test_dialect.py` | 23 tests: `ROWNUM`, `DUAL`, `NVL`, `DECODE`, `TO_CHAR`, `FETCH FIRST`, `MINUS`, `LISTAGG` on the portal tables, passthrough, the switch, the journal, undo/redo over HTTP and access control. |
| `tests/test_oracle.py` | 31 tests: the seeded schema, reads and functions, DDL/DML round trips, sequences, `DESCRIBE`, Oracle error codes, refusals, the starter script, reset, the HTTP endpoints and access control. |
