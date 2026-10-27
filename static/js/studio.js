/* ============================================================================
   SQL Studio — the client behaviour.

   The page arrives fully rendered, so this file only adds the behaviour a
   desktop client has: menus that open, a navigator that expands, worksheets
   that switch and persist, an editor with a line gutter and syntax colour, a
   result grid you can sort, and a status bar that keeps up.
   ========================================================================== */
(() => {
  const app = document.getElementById("studioApp");
  if (!app) return;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const CSRF =
    document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";

  const urls = {
    portal: {
      run: app.dataset.runUrl,
      script: app.dataset.scriptUrl,
      explain: app.dataset.explainUrl,
      describe: app.dataset.describeUrl,
      tree: app.dataset.portalTreeUrl,
      undo: app.dataset.portalUndoUrl,
      redo: app.dataset.portalRedoUrl,
    },
    oracle: {
      run: app.dataset.oracleRunUrl,
      script: app.dataset.oracleScriptUrl,
      explain: app.dataset.oracleExplainUrl,
      tree: app.dataset.oracleTreeUrl,
      reset: app.dataset.oracleResetUrl,
      undo: app.dataset.oracleUndoUrl,
      redo: app.dataset.oracleRedoUrl,
    },
  };
  const oracleStarter = app.dataset.oracleStarter || "";
  const endpoints = () => urls[state.connection];

  const lockIcon = (kind) =>
    kind === "unlocked"
      ? '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 7-2.6"/></svg>'
      : '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>';
  const STORAGE_KEY = "nist-sql-studio-v1";
  const HISTORY_KEY = "nist-sql-studio-history-v1";
  const MAX_WORKSHEETS = 8;

  const el = {
    sql: $("#stSql"),
    highlight: $("#stHighlight"),
    gutter: $("#stGutter"),
    editorBox: $("#stEditorBox"),
    tabs: $("#stWorksheetTabs"),
    tree: $("#stTree"),
    filter: $("#stObjectFilter"),
    selectionValue: $("#stSelectionValue"),
    grid: $("#stGrid"),
    gridHead: $("#stGridHead"),
    gridBody: $("#stGridBody"),
    gridScroll: $("#stGridScroll"),
    gridNote: $("#stGridNote"),
    resultEmpty: $("#stResultEmpty"),
    resultBadge: $("#stResultBadge"),
    outputBadge: $("#stOutputBadge"),
    messageBadge: $("#stMessageBadge"),
    log: $("#stLog"),
    plan: $("#stPlan"),
    planEmpty: $("#stPlanEmpty"),
    messageLog: $("#stMessageLog"),
    statusPosition: $("#stStatusPosition"),
    statusRows: $("#stStatusRows"),
    statusTime: $("#stStatusTime"),
    contextMenu: $("#stContextMenu"),
    snippetPopover: $("#stSnippetPopover"),
    historyPopover: $("#stHistoryPopover"),
    historyList: $("#stHistoryList"),
  };

  const state = {
    connection: "portal",
    memory: { portal: null, oracle: null },
    journals: (() => {
      const read = (text) => {
        try {
          return JSON.parse(text || "{}");
        } catch (error) {
          return {};
        }
      };
      return {
        portal: read(app.dataset.portalJournal),
        oracle: read(app.dataset.oracleJournal),
      };
    })(),
    journal: {},
    busySchema: false,
    worksheets: [],
    activeId: 1,
    nextId: 2,
    payload: null,
    sort: { column: null, direction: 1 },
    selection: null,
    contextTarget: null,
    busy: false,
    messages: 0,
    rowCount: 0,
    elapsed: null,
  };

  /* ------------------------------------------------------------------ utils */
  const escapeHtml = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (character) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
          character
        ],
    );

  const clock = () =>
    new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  let toastTimer = null;
  const toast = (text) => {
    let node = $(".st-toast", app);
    if (!node) {
      node = document.createElement("div");
      node.className = "st-toast";
      node.setAttribute("role", "status");
      app.appendChild(node);
    }
    node.textContent = text;
    node.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("is-visible"), 1500);
  };

  const api = async (url, body) => {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRF-Token": CSRF,
      },
      credentials: "same-origin",
      body: JSON.stringify(body || {}),
    });
    const payload = await response.json().catch(() => null);
    if (!payload) {
      return {
        ok: false,
        code: `HTTP ${response.status}`,
        error: "The studio could not reach the server. Try again.",
      };
    }
    return payload;
  };

  /* ------------------------------------------------------------------ state */
  const activeWorksheet = () =>
    state.worksheets.find((worksheet) => worksheet.id === state.activeId) || state.worksheets[0];

  // A worksheet is saved with the tail of its undo stack, so a reload does not
  // lose the ability to take back what was typed before it.
  const packWorksheet = ({ id, name, sql, history }) => {
    if (!history || !Array.isArray(history.entries) || history.entries.length < 2) {
      return { id, name, sql };
    }
    const entries = history.entries.slice(-20).map((entry) => ({
      text: String(entry.text ?? ""),
      start: Number(entry.start) || 0,
      end: Number(entry.end) || 0,
    }));
    const offset = history.entries.length - entries.length;
    return {
      id,
      name,
      sql,
      history: { entries, index: Math.max(0, Math.min((history.index ?? 0) - offset, entries.length - 1)) },
    };
  };

  const unpackHistory = (worksheet, saved) => {
    if (!saved || !Array.isArray(saved.entries) || !saved.entries.length) return null;
    const entries = saved.entries
      .filter((entry) => entry && typeof entry.text === "string")
      .slice(-20)
      .map((entry) => ({
        text: entry.text,
        start: Number(entry.start) || 0,
        end: Number(entry.end) || 0,
      }));
    if (!entries.length) return null;
    const index = Math.max(0, Math.min(Number(saved.index) || 0, entries.length - 1));
    return { entries, index };
  };

  const saveState = () => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          worksheets: state.worksheets.map(packWorksheet),
          activeId: state.activeId,
        }),
      );
    } catch (error) {
      /* private mode, or the quota is full: the studio still works in memory */
    }
  };

  const loadState = () => {
    const starter = el.sql.value;
    let restored = null;
    try {
      restored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    } catch (error) {
      restored = null;
    }
    if (restored && Array.isArray(restored.worksheets) && restored.worksheets.length) {
      state.worksheets = restored.worksheets
        .filter((worksheet) => typeof worksheet.sql === "string")
        .slice(0, MAX_WORKSHEETS)
        .map((worksheet, position) => {
          const restoredWorksheet = {
            id: Number(worksheet.id) || position + 1,
            name: String(worksheet.name || `Worksheet ${position + 1}`),
            sql: worksheet.sql,
          };
          const history = unpackHistory(restoredWorksheet, worksheet.history);
          if (history) restoredWorksheet.history = history;
          return restoredWorksheet;
        });
      state.activeId =
        state.worksheets.find((worksheet) => worksheet.id === restored.activeId)?.id ||
        state.worksheets[0].id;
      state.nextId = Math.max(...state.worksheets.map((worksheet) => worksheet.id)) + 1;
    } else {
      state.worksheets = [{ id: 1, name: "Worksheet 1", sql: starter }];
      state.activeId = 1;
      state.nextId = 2;
    }
  };

  /* ---------------------------------------------------------------- editor */
  const SQL_KEYWORDS = new Set(
    `SELECT FROM WHERE GROUP BY ORDER HAVING LIMIT OFFSET JOIN LEFT RIGHT INNER OUTER FULL
     CROSS ON USING AS AND OR NOT NULL IS IN BETWEEN LIKE GLOB ESCAPE EXISTS CASE WHEN THEN
     ELSE END DISTINCT ALL UNION INTERSECT EXCEPT INSERT INTO VALUES UPDATE SET DELETE
     CREATE TABLE VIEW INDEX TRIGGER PROCEDURE FUNCTION BEGIN COMMIT ROLLBACK SAVEPOINT
     PRIMARY KEY FOREIGN REFERENCES UNIQUE CHECK DEFAULT CONSTRAINT DROP ALTER ADD COLUMN
     EXPLAIN QUERY PLAN ANALYZE PRAGMA WITH RECURSIVE OVER PARTITION WINDOW FILTER CAST
     COLLATE ASC DESC TRUE FALSE IF REPLACE TEMP TEMPORARY WITHOUT ROWID RETURNING`
      .split(/\s+/)
      .filter(Boolean),
  );
  const SQL_FUNCTIONS = new Set(
    `COUNT SUM AVG MIN MAX ROUND COALESCE IFNULL NULLIF LENGTH UPPER LOWER SUBSTR TRIM
     DATE TIME DATETIME STRFTIME JULIANDAY ABS TOTAL GROUP_CONCAT ROW_NUMBER RANK
     DENSE_RANK NTILE LAG LEAD CUME_DIST PERCENT_RANK NOW CURRENT_DATE CURRENT_TIME
     CURRENT_TIMESTAMP CONCAT`
      .split(/\s+/)
      .filter(Boolean),
  );

  const highlightSql = (text) => {
    let out = "";
    let index = 0;
    const push = (kind, value) => {
      out += `<span class="tok-${kind}">${escapeHtml(value)}</span>`;
    };
    while (index < text.length) {
      const rest = text.slice(index);
      if (rest.startsWith("--")) {
        const end = text.indexOf("\n", index);
        const stop = end === -1 ? text.length : end;
        push("comment", text.slice(index, stop));
        index = stop;
        continue;
      }
      if (rest.startsWith("/*")) {
        const end = text.indexOf("*/", index + 2);
        const stop = end === -1 ? text.length : end + 2;
        push("comment", text.slice(index, stop));
        index = stop;
        continue;
      }
      const character = text[index];
      if (character === "'" || character === '"' || character === "`") {
        let cursor = index + 1;
        while (cursor < text.length) {
          if (text[cursor] === character) {
            if (text[cursor + 1] === character) {
              cursor += 2;
              continue;
            }
            cursor += 1;
            break;
          }
          cursor += 1;
        }
        push("string", text.slice(index, cursor));
        index = cursor;
        continue;
      }
      if (/[0-9]/.test(character) && !/[\w.]/.test(text[index - 1] || "")) {
        const match = rest.match(/^\d+(?:\.\d+)?/);
        push("number", match[0]);
        index += match[0].length;
        continue;
      }
      if (/[A-Za-z_]/.test(character)) {
        const match = rest.match(/^[A-Za-z_][A-Za-z0-9_]*/);
        const word = match[0];
        const upper = word.toUpperCase();
        if (SQL_KEYWORDS.has(upper)) push("keyword", word);
        else if (SQL_FUNCTIONS.has(upper) && /^\s*\(/.test(rest.slice(word.length)))
          push("function", word);
        else push("identifier", word);
        index += word.length;
        continue;
      }
      if (/[(),.;]/.test(character)) {
        push("punct", character);
        index += 1;
        continue;
      }
      if (/[=<>!+\-*/|%&~^]/.test(character)) {
        push("operator", character);
        index += 1;
        continue;
      }
      out += escapeHtml(character);
      index += 1;
    }
    return out;
  };

  const lineNumbers = (text) => {
    const total = text.split("\n").length;
    let out = "";
    for (let line = 1; line <= total; line += 1) out += `${line}\n`;
    return out;
  };

  const paintEditor = () => {
    const text = el.sql.value;
    el.highlight.innerHTML = `${highlightSql(text)}\n`;
    // The sentinel newline keeps the last line of the highlight layer as tall
    // as the textarea's, so the two layers never drift apart.
    el.gutter.textContent = lineNumbers(text);
    el.editorBox.classList.add("is-highlighted");
    syncEditorScroll();
  };

  const syncEditorScroll = () => {
    el.highlight.scrollTop = el.sql.scrollTop;
    el.highlight.scrollLeft = el.sql.scrollLeft;
    el.gutter.scrollTop = el.sql.scrollTop;
  };

  const caretPosition = () => {
    const upto = el.sql.value.slice(0, el.sql.selectionStart);
    const lines = upto.split("\n");
    return { line: lines.length, column: lines[lines.length - 1].length + 1 };
  };

  const updateCaret = () => {
    const { line, column } = caretPosition();
    el.statusPosition.textContent = `Ln ${line}, Col ${column}`;
  };

  const commitEditor = () => {
    const worksheet = activeWorksheet();
    if (!worksheet) return;
    worksheet.sql = el.sql.value;
    paintEditor();
    saveState();
    updateCaret();
  };

  /* ------------------------------------------------------- undo and redo ---
     Every worksheet keeps its own stack of {text, caret} snapshots, so undo
     follows the worksheet you are looking at and survives a reload. Typing is
     coalesced on a short timer; Format, Comment, Clear, snippet inserts and a
     connection switch are recorded as single steps. */
  const HISTORY_STEPS = 60;
  const HISTORY_CHAR_BUDGET = 80000;
  let historyTimer = null;

  const historyOf = (worksheet) => {
    if (!worksheet) return null;
    if (!worksheet.history || !Array.isArray(worksheet.history.entries)) {
      worksheet.history = { entries: [], index: -1 };
    }
    const history = worksheet.history;
    if (!history.entries.length) {
      history.entries = [{ text: worksheet.sql || "", start: 0, end: 0 }];
      history.index = 0;
    }
    return history;
  };

  const trimHistory = (history) => {
    while (history.entries.length > HISTORY_STEPS) history.entries.shift();
    let total = history.entries.reduce((sum, entry) => sum + (entry.text || "").length, 0);
    while (history.entries.length > 2 && total > HISTORY_CHAR_BUDGET) {
      total -= (history.entries.shift().text || "").length;
    }
    history.index = Math.max(0, Math.min(history.index, history.entries.length - 1));
  };

  const updateHistoryButtons = () => {
    const history = historyOf(activeWorksheet());
    const canUndo = Boolean(history) && history.index > 0;
    const canRedo = Boolean(history) && history.index < history.entries.length - 1;
    const undoButton = $("#stUndoTool");
    const redoButton = $("#stRedoTool");
    if (undoButton) {
      undoButton.disabled = !canUndo;
      undoButton.title = canUndo
        ? "Undo the last edit (Ctrl+Z)"
        : "Nothing to undo in this worksheet yet";
    }
    if (redoButton) {
      redoButton.disabled = !canRedo;
      redoButton.title = canRedo
        ? "Redo the edit undo took back (Ctrl+Shift+Z)"
        : "Nothing to redo";
    }
    const menuUndo = $("[data-action='undo']");
    const menuRedo = $("[data-action='redo']");
    if (menuUndo && menuUndo.tagName === "BUTTON" && !menuUndo.classList.contains("st-tool")) {
      menuUndo.disabled = !canUndo;
    }
    if (menuRedo && menuRedo.tagName === "BUTTON" && !menuRedo.classList.contains("st-tool")) {
      menuRedo.disabled = !canRedo;
    }
    return { canUndo, canRedo };
  };

  const recordHistory = () => {
    historyTimer = null;
    const worksheet = activeWorksheet();
    if (!worksheet) return;
    const history = historyOf(worksheet);
    const snapshot = { text: el.sql.value, start: el.sql.selectionStart, end: el.sql.selectionEnd };
    const current = history.entries[history.index];
    if (current && current.text === snapshot.text) {
      current.start = snapshot.start;
      current.end = snapshot.end;
      return;
    }
    history.entries = history.entries.slice(0, history.index + 1);
    history.entries.push(snapshot);
    history.index = history.entries.length - 1;
    trimHistory(history);
    updateHistoryButtons();
    saveState();
  };

  const scheduleHistory = () => {
    clearTimeout(historyTimer);
    historyTimer = setTimeout(recordHistory, 320);
  };

  const flushHistory = () => {
    if (historyTimer) {
      clearTimeout(historyTimer);
      historyTimer = null;
      recordHistory();
    }
  };

  const stepHistory = (delta) => {
    flushHistory();
    const worksheet = activeWorksheet();
    if (!worksheet) return;
    const history = historyOf(worksheet);
    const next = history.index + delta;
    if (next < 0 || next >= history.entries.length) {
      toast(delta < 0 ? "Nothing left to undo" : "Nothing left to redo");
      return false;
    }
    history.index = next;
    const entry = history.entries[next];
    const text = entry.text || "";
    el.sql.value = text;
    const start = Math.max(0, Math.min(entry.start ?? text.length, text.length));
    const end = Math.max(start, Math.min(entry.end ?? start, text.length));
    el.sql.selectionStart = start;
    el.sql.selectionEnd = end;
    worksheet.sql = text;
    paintEditor();
    updateCaret();
    updateHistoryButtons();
    saveState();
    el.sql.focus();
    return true;
  };

  const undoEdit = () => stepHistory(-1);
  const redoEdit = () => stepHistory(1);

  /* ------------------------------------------------- statements in the editor */
  const statementSpans = (text) => {
    const spans = [];
    let start = 0;
    let index = 0;
    let quote = "";
    let lineComment = false;
    let blockComment = false;
    while (index < text.length) {
      const character = text[index];
      const pair = text.slice(index, index + 2);
      if (lineComment) {
        if (character === "\n") lineComment = false;
        index += 1;
        continue;
      }
      if (blockComment) {
        if (pair === "*/") {
          blockComment = false;
          index += 2;
          continue;
        }
        index += 1;
        continue;
      }
      if (quote) {
        if (character === quote) {
          if (text[index + 1] === quote) {
            index += 2;
            continue;
          }
          quote = "";
        }
        index += 1;
        continue;
      }
      if (pair === "--") {
        lineComment = true;
        index += 2;
        continue;
      }
      if (pair === "/*") {
        blockComment = true;
        index += 2;
        continue;
      }
      if (character === "'" || character === '"' || character === "`") {
        quote = character;
        index += 1;
        continue;
      }
      if (character === ";") {
        spans.push({ start, end: index + 1, text: text.slice(start, index) });
        start = index + 1;
      }
      index += 1;
    }
    if (start < text.length) spans.push({ start, end: text.length, text: text.slice(start) });
    return spans
      .map((span) => {
        const body = span.text;
        const leading = body.length - body.replace(/^\s+/, "").length;
        return {
          start: span.start + leading,
          end: span.end,
          text: body.trim(),
        };
      })
      .filter((span) => {
        const bare = span.text
          .replace(/\/\*[\s\S]*?\*\//g, " ")
          .replace(/--[^\n]*/g, " ")
          .replace(/#[^\n]*/g, " ")
          .trim();
        return bare.length > 0;
      });
  };

  const statementAtCursor = () => {
    const text = el.sql.value;
    const spans = statementSpans(text);
    if (!spans.length) return text.trim();
    const position = el.sql.selectionStart;
    const exact = spans.find((span) => position >= span.start && position <= span.end);
    if (exact) return exact.text;
    const before = spans.filter((span) => span.end <= position).pop();
    return (before || spans[0]).text;
  };

  const insertText = (snippet) => {
    const start = el.sql.selectionStart;
    const end = el.sql.selectionEnd;
    const before = el.sql.value.slice(0, start);
    const after = el.sql.value.slice(end);
    const pad = before && !/\n$/.test(before) ? "\n" : "";
    el.sql.value = `${before}${pad}${snippet}${after}`;
    const caret = (before + pad + snippet).length;
    el.sql.selectionStart = caret;
    el.sql.selectionEnd = caret;
    el.sql.focus();
    commitEditor();
    recordHistory();
  };

  /* --------------------------------------------------------------- worksheets */
  const renderTabs = () => {
    $$(".st-ws-tab", el.tabs).forEach((tab) => tab.remove());
    state.worksheets.forEach((worksheet) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `st-ws-tab${worksheet.id === state.activeId ? " is-active" : ""}`;
      button.dataset.worksheet = String(worksheet.id);
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", worksheet.id === state.activeId ? "true" : "false");
      button.setAttribute("aria-controls", "stEditorBox");
      button.innerHTML = `<span class="st-ws-name" data-ws-name></span><span class="st-ws-close" data-ws-close role="presentation" title="Close worksheet">×</span>`;
      button.querySelector("[data-ws-name]").textContent = worksheet.name;
      el.tabs.appendChild(button);
    });
    const active = $(`.st-ws-tab[data-worksheet="${state.activeId}"]`, el.tabs);
    if (active) active.setAttribute("aria-current", "true");
  };

  const showWorksheet = (id) => {
    const worksheet = state.worksheets.find((item) => item.id === id);
    if (!worksheet) return;
    flushHistory();
    state.activeId = id;
    el.sql.value = worksheet.sql;
    renderTabs();
    paintEditor();
    updateCaret();
    saveState();
    updateHistoryButtons();
    el.sql.focus();
  };

  const newWorksheet = (name) => {
    if (state.worksheets.length >= MAX_WORKSHEETS) {
      toast("Eight worksheets is the limit in one browser tab");
      return;
    }
    const title = name || `Worksheet ${state.nextId}`;
    const worksheet = {
      id: state.nextId,
      name: title,
      sql:
        state.connection === "oracle"
          ? oracleStarter
          : `-- ${title}\n-- Type a statement, then press F9 to run it.\n\nSELECT *\nFROM department\nORDER BY dept_code;\n`,
    };
    state.nextId += 1;
    state.worksheets.push(worksheet);
    showWorksheet(worksheet.id);
    message(
      "note",
      "Worksheet opened",
      state.connection === "oracle"
        ? `${worksheet.name} is ready on ORACLE_XE. DDL and DML run against the practice schema.`
        : `${worksheet.name} is ready. The portal connection is live: what you run here reaches the portal's own screens.`,
    );
    toast(`${worksheet.name} opened`);
  };

  const duplicateWorksheet = () => {
    const current = activeWorksheet();
    if (!current) return;
    if (state.worksheets.length >= MAX_WORKSHEETS) {
      toast("Eight worksheets is the limit in one browser tab");
      return;
    }
    const copy = {
      id: state.nextId,
      name: `${current.name} (copy)`,
      sql: current.sql,
    };
    state.nextId += 1;
    state.worksheets.push(copy);
    showWorksheet(copy.id);
    toast("Worksheet duplicated");
  };

  const closeWorksheet = (id) => {
    if (state.worksheets.length === 1) {
      toast("The last worksheet cannot be closed");
      return;
    }
    const index = state.worksheets.findIndex((worksheet) => worksheet.id === id);
    if (index === -1) return;
    const [removed] = state.worksheets.splice(index, 1);
    if (state.activeId === removed.id) {
      const next = state.worksheets[Math.max(0, index - 1)];
      state.activeId = next.id;
      el.sql.value = next.sql;
    }
    renderTabs();
    paintEditor();
    saveState();
    toast(`${removed.name} closed`);
  };

  const renameWorksheet = (id) => {
    const worksheet = state.worksheets.find((item) => item.id === id);
    if (!worksheet) return;
    const label = $(`.st-ws-tab[data-worksheet="${id}"] [data-ws-name]`, el.tabs);
    if (!label) return;
    label.setAttribute("contenteditable", "true");
    label.focus();
    document.getSelection()?.selectAllChildren(label);
    const finish = (save) => {
      label.removeAttribute("contenteditable");
      const next = label.textContent.trim().slice(0, 40);
      if (save && next) {
        worksheet.name = next;
        label.textContent = next;
        saveState();
      } else {
        label.textContent = worksheet.name;
      }
      label.removeEventListener("blur", onBlur);
      label.removeEventListener("keydown", onKey);
    };
    const onBlur = () => finish(true);
    const onKey = (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        label.blur();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        finish(false);
      }
    };
    label.addEventListener("blur", onBlur);
    label.addEventListener("keydown", onKey);
  };

  /* --------------------------------------------------------------- formatting */
  const formatSql = () => {
    flushHistory();
    const text = el.sql.value;
    let formatted = "";
    let index = 0;
    while (index < text.length) {
      const rest = text.slice(index);
      if (rest.startsWith("--")) {
        const end = text.indexOf("\n", index);
        const stop = end === -1 ? text.length : end;
        formatted += text.slice(index, stop);
        index = stop;
        continue;
      }
      if (rest.startsWith("/*")) {
        const end = text.indexOf("*/", index + 2);
        const stop = end === -1 ? text.length : end + 2;
        formatted += text.slice(index, stop);
        index = stop;
        continue;
      }
      const character = text[index];
      if (character === "'" || character === '"' || character === "`") {
        let cursor = index + 1;
        while (cursor < text.length) {
          if (text[cursor] === character) {
            if (text[cursor + 1] === character) {
              cursor += 2;
              continue;
            }
            cursor += 1;
            break;
          }
          cursor += 1;
        }
        formatted += text.slice(index, cursor);
        index = cursor;
        continue;
      }
      const word = rest.match(/^[A-Za-z_][A-Za-z0-9_]*/);
      if (word) {
        const upper = word[0].toUpperCase();
        formatted += SQL_KEYWORDS.has(upper) ? upper : word[0];
        index += word[0].length;
        continue;
      }
      formatted += character;
      index += 1;
    }
    // One blank line between statements, no trailing whitespace, no runaway gaps.
    formatted = formatted
      .split("\n")
      .map((line) => line.replace(/[ \t]+$/, ""))
      .join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    el.sql.value = `${formatted}\n`;
    commitEditor();
    recordHistory();
    toast("Worksheet formatted");
  };

  const selectedLineRange = () => {
    const value = el.sql.value;
    const start = el.sql.selectionStart;
    const end = el.sql.selectionEnd;
    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
    let lineEnd = value.indexOf("\n", end);
    if (lineEnd === -1) lineEnd = value.length;
    return { lineStart, lineEnd };
  };

  const commentLines = (remove) => {
    flushHistory();
    const { lineStart, lineEnd } = selectedLineRange();
    const before = el.sql.value.slice(0, lineStart);
    const block = el.sql.value.slice(lineStart, lineEnd);
    const after = el.sql.value.slice(lineEnd);
    const lines = block.split("\n");
    const commented = lines.every((line) => !line.trim() || line.trimStart().startsWith("--"));
    const next = lines
      .map((line) => {
        if (!line.trim()) return line;
        if (remove || commented) return line.replace(/^(\s*)-- ?/, "$1");
        return line.replace(/^(\s*)/, "$1-- ");
      })
      .join("\n");
    el.sql.value = before + next + after;
    el.sql.selectionStart = lineStart;
    el.sql.selectionEnd = lineStart + next.length;
    commitEditor();
    recordHistory();
    toast(remove || commented ? "Comment removed" : "Comment added");
  };

  /* ------------------------------------------------------------------ output */
  const logLine = (kind, text) => {
    const line = document.createElement("p");
    line.className = `st-log-line${kind ? ` is-${kind}` : ""}`;
    line.innerHTML = `<span class="st-log-time">${clock()}</span><span class="st-log-text">${escapeHtml(text)}</span>`;
    el.log.appendChild(line);
    el.log.scrollTop = el.log.scrollHeight;
    return line;
  };

  const setOutputBadge = (count) => {
    el.outputBadge.textContent = count ? String(count) : "";
  };

  const message = (kind, title, text) => {
    const wrapper = document.createElement("div");
    wrapper.className = `st-message${kind ? ` is-${kind}` : ""}`;
    wrapper.innerHTML = `<time>${clock()}</time><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(text)}</p></div>`;
    el.messageLog.prepend(wrapper);
    state.messages += 1;
    el.messageBadge.hidden = false;
    el.messageBadge.textContent = String(state.messages);
  };

  const setBusy = (busy) => {
    state.busy = busy;
    app.classList.toggle("is-busy", busy);
    $$("[data-action='run-statement'], [data-action='run-script'], [data-action='explain']").forEach(
      (button) => {
        button.disabled = busy;
      },
    );
  };

  /* -------------------------------------------------------------------- grid */
  const csvFor = () => {
    if (!state.payload || !state.payload.columns) return "";
    const escape = (value) =>
      /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
    const head = state.payload.columns.map((column) => escape(column.name)).join(",");
    const rows = sortedRows().map((row) =>
      row.cells.map((cell) => (cell.null ? "" : escape(cell.text))).join(","),
    );
    return [head, ...rows].join("\n");
  };

  const sortedRows = () => {
    const payload = state.payload;
    if (!payload || !payload.rows) return [];
    const { column, direction } = state.sort;
    if (column === null) return payload.rows;
    const rows = [...payload.rows];
    rows.sort((left, right) => {
      const a = left.cells[column];
      const b = right.cells[column];
      if (a.null && b.null) return 0;
      if (a.null) return 1;
      if (b.null) return -1;
      if (a.numeric && b.numeric) {
        const na = Number(String(a.text).replace(/,/g, ""));
        const nb = Number(String(b.text).replace(/,/g, ""));
        return (na - nb) * direction;
      }
      return a.text.localeCompare(b.text, undefined, { sensitivity: "base" }) * direction;
    });
    return rows.map((row, position) => ({ ...row, number: position + 1 }));
  };

  const renderGrid = () => {
    const payload = state.payload;
    if (!payload || !payload.columns) {
      el.gridScroll.hidden = true;
      el.resultEmpty.hidden = false;
      el.gridNote.hidden = true;
      el.resultBadge.textContent = "";
      return;
    }
    el.resultEmpty.hidden = true;
    el.gridScroll.hidden = false;
    const { column, direction } = state.sort;
    el.gridHead.innerHTML = `<tr><th class="st-rowno" scope="col"><span aria-hidden="true">#</span><span class="sr-only">Row</span></th>${payload.columns
      .map((item, index) => {
        const marker =
          column === index ? `<span class="st-sort">${direction === 1 ? "▲" : "▼"}</span>` : "";
        return `<th scope="col"><button type="button" data-sort="${index}" title="Sort by ${escapeHtml(
          item.name,
        )}">${escapeHtml(item.name)}${marker}</button></th>`;
      })
      .join("")}</tr>`;
    el.gridBody.innerHTML = sortedRows()
      .map(
        (row) =>
          `<tr><td class="st-rowno" aria-hidden="true">${row.number}</td>${row.cells
            .map((cell, index) => {
              const classes = [
                cell.null ? "is-null" : "",
                cell.numeric && payload.columns[index]?.numeric ? "is-num" : "",
              ]
                .filter(Boolean)
                .join(" ");
              return `<td class="${classes}" tabindex="-1">${escapeHtml(cell.text)}</td>`;
            })
            .join("")}</tr>`,
      )
      .join("");
    el.gridNote.hidden = false;
    const rowCount = payload.row_count ?? 0;
    const truncated = payload.truncated
      ? `<span class="st-warn-text">showing the first ${payload.shown.toLocaleString()} rows</span>`
      : "";
    el.gridNote.innerHTML = `<strong>${rowCount.toLocaleString()} row${
      rowCount === 1 ? "" : "s"
    }</strong><span>${payload.elapsed_ms} ms</span>${truncated}<span class="st-tool-grow"></span><span>${escapeHtml(
      payload.statement?.split("\n")[0] || "",
    )}</span>`;
    el.resultBadge.textContent = rowCount ? rowCount.toLocaleString() : "";
  };

  const sortBy = (index) => {
    if (state.sort.column === index) {
      state.sort.direction = state.sort.direction === 1 ? -1 : 1;
    } else {
      state.sort = { column: index, direction: 1 };
    }
    renderGrid();
  };

  /* -------------------------------------------------------------------- plan */
  const renderPlan = (payload) => {
    if (!payload.ok) {
      el.planEmpty.hidden = false;
      el.plan.hidden = true;
      return;
    }
    el.planEmpty.hidden = true;
    el.plan.hidden = false;
    const steps = payload.nodes
      .map((node) => {
        const branch = node.depth ? "└ " : "";
        return `<li class="st-plan-step is-${node.kind}" style="padding-left: ${
          8 + node.depth * 18
        }px"><span class="st-plan-kind">${node.kind}</span><span><span class="st-plan-branch">${branch}</span>${escapeHtml(
          node.detail,
        )}</span></li>`;
      })
      .join("");
    const statement = (payload.statement || "").replace(/\s+/g, " ").trim();
    el.plan.innerHTML = `<div class="st-plan-head">
        <span class="st-plan-chip is-${payload.verdict}">${
          payload.verdict === "scan" ? "Full table scan" : "Index access only"
        }</span>
        <span class="st-plan-summary">${escapeHtml(payload.summary)}</span>
      </div>
      <p class="st-plan-statement" title="${escapeHtml(statement)}">${escapeHtml(
        statement.length > 180 ? `${statement.slice(0, 179)}…` : statement,
      )}</p>
      <ol class="st-plan-steps">${steps}</ol>`;
  };

  /* ------------------------------------------------------------------- panes */
  const activatePane = (name, options = {}) => {
    $$(".st-rtab").forEach((tab) => {
      const active = tab.dataset.pane === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    $$(".st-pane").forEach((pane) => {
      const active = pane.id === `pane-${name}`;
      pane.classList.toggle("is-active", active);
      pane.hidden = !active;
    });
    if (name === "messages" && !options.quiet) {
      state.messages = 0;
      el.messageBadge.hidden = true;
      el.messageBadge.textContent = "";
    }
  };

  /* ----------------------------------------------------------------- running */
  const history = {
    read() {
      try {
        return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
      } catch (error) {
        return [];
      }
    },
    add(sql, ok, summary) {
      if (!sql) return;
      const items = history.read().filter((item) => item.sql !== sql);
      items.unshift({ sql, ok, summary, at: new Date().toISOString() });
      try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, 40)));
      } catch (error) {
        /* the popover simply stays empty */
      }
    },
  };

  const describeOutcome = (payload) => {
    if (!payload.ok) return payload.error || "The statement failed.";
    if (payload.kind === "prepare") return payload.message;
    if (payload.kind === "read") return `${payload.row_count} row${payload.row_count === 1 ? "" : "s"} fetched.`;
    return payload.message || "Statement completed.";
  };

  const translatedNote = (payload) => {
    if (!payload || !payload.translated) return "";
    const notes = (payload.notes || []).map((note) => `· ${note}`).join(" ");
    return `<div class="st-translated"><span>Translated and executed</span>
      <pre>${escapeHtml(payload.translated)}</pre>
      ${notes ? `<p>${escapeHtml(notes)}</p>` : ""}</div>`;
  };

  const showOutcome = (payload) => {
    state.payload = payload;
    state.sort = { column: null, direction: 1 };
    if (payload.ok && (payload.kind === "ddl" || payload.kind === "write")) {
      state.payload = null;
      renderGrid();
      el.resultEmpty.hidden = true;
      el.gridScroll.hidden = true;
      el.gridNote.hidden = true;
      el.resultBadge.textContent = "";
      const panel = $("#stCommand");
      panel.hidden = false;
      const journal = payload.journal || null;
      const undoRow = journal
        ? `<div class="st-command-actions">
             <button type="button" class="st-command-button" data-action="undo-change"${
               journal.can_undo ? "" : " disabled"
             }>Undo this change</button>
             <button type="button" class="st-command-button" data-action="redo-change"${
               journal.can_redo ? "" : " disabled"
             }>Redo</button>
             <span class="st-command-hint">Ctrl+Alt+Z · Ctrl+Alt+Y</span>
           </div>`
        : "";
      panel.innerHTML = `<div class="st-command-card">
          <div class="st-command-verdict">${escapeHtml(payload.message || "Statement completed.")}</div>
          <p class="st-command-meta">${escapeHtml(payload.verb || "")} · ${payload.elapsed_ms} ms · ${
            payload.connection === "oracle"
              ? "committed to the practice schema"
              : "committed to the portal database · visible on every portal screen"
          }</p>
          ${undoRow}
        </div>${translatedNote(payload)}`;
      if (journal) setJournal(journal);
      activatePane("results");
      el.statusRows.textContent = payload.message || "Command completed";
      el.statusTime.textContent = `${payload.elapsed_ms} ms`;
      if (payload.connection === "oracle") refreshOracleTree();
      else if (payload.kind === "ddl") refreshPortalTree();
      return;
    }
    const command = $("#stCommand");
    if (command) {
      command.hidden = true;
      command.innerHTML = "";
    }
    if (payload.ok && payload.kind === "describe") {
      el.resultEmpty.hidden = true;
      el.gridScroll.hidden = false;
      renderGrid();
      activatePane("results");
      el.statusRows.textContent = `${payload.row_count} columns`;
      el.statusTime.textContent = `${payload.elapsed_ms} ms`;
      return;
    }
    const structureVerb = ["CREATE", "DROP", "ALTER", "TRUNCATE", "RENAME"].includes(payload.verb);
    if (!payload.ok && structureVerb && state.connection === "portal") {
      message("note", "Want to create or drop tables for real?",
        "Switch the Connection selector to ORACLE_XE: that schema is fully writable, and nothing you do there touches the portal. Data changes (INSERT, UPDATE, DELETE) do run here and can be undone with Undo change.");
    }
    if (payload.ok && payload.kind === "prepare") {
      state.payload = null;
      renderGrid();
      el.resultEmpty.querySelector("h2").textContent = "Statement prepared, not run";
      el.resultEmpty.querySelector("p").textContent =
        "The engine compiled the statement and found it valid, but it was not run. Open Messages for the detail.";
      activatePane("results");
      el.statusRows.textContent = "Prepared, not committed";
      el.statusTime.textContent = `${payload.elapsed_ms} ms`;
    } else if (payload.ok) {
      el.resultEmpty.querySelector("h2").textContent = "No statement has run yet";
      el.resultEmpty.querySelector("p").textContent =
        "Press F9 to run the statement under the cursor, or F5 to run the whole worksheet. Reads execute against the live database; data changes are prepared and declined.";
      renderGrid();
      if (payload.translated) {
        const panel = $("#stCommand");
        panel.hidden = false;
        panel.innerHTML = translatedNote(payload);
      }
      activatePane("results");
      el.statusRows.textContent = `${(payload.row_count ?? 0).toLocaleString()} rows`;
      el.statusTime.textContent = `${payload.elapsed_ms} ms`;
    } else {
      state.payload = null;
      renderGrid();
      message(
        "error",
        payload.code || "Statement failed",
        `${payload.error || "The statement failed."}${payload.hint ? `\n\n${payload.hint}` : ""}`,
      );
      if (state.connection === "portal" && (payload.code || "").startsWith("STUDIO-")) {
        message(
          "note",
          "The practice schema accepts this",
          "ORACLE_XE — the second connection — is writable. Switch to it in the Connection selector and the same statement will run.",
        );
      }
      activatePane("messages");
      el.statusRows.textContent = "Statement failed";
      el.statusTime.textContent = `${payload.elapsed_ms ?? 0} ms`;
    }
    if (payload.kind === "prepare") {
      message("note", "Prepared, not run", payload.note || payload.message);
      if (state.connection === "portal") {
        message(
          "note",
          "Want it to run for real?",
          "Switch the Connection selector to ORACLE_XE. The practice schema on that connection is writable: CREATE, INSERT, UPDATE, DELETE and DROP all really execute there.",
        );
      }
    }
  };

  const runStatement = async () => {
    if (state.busy) return;
    const sql = statementAtCursor();
    if (!sql) {
      toast("Put the cursor on a statement first");
      return;
    }
    setBusy(true);
    el.statusRows.textContent = "Running…";
    try {
      const payload = await api(endpoints().run, { sql });
      logLine(
        payload.ok ? "ok" : "error",
        `${payload.verb || "STATEMENT"} · ${describeOutcome(payload)} ${payload.elapsed_ms ? `· ${payload.elapsed_ms} ms` : ""}`,
      );
      setOutputBadge($$(".st-log-line", el.log).length);
      history.add(sql, payload.ok, describeOutcome(payload));
      showOutcome(payload);
    } finally {
      setBusy(false);
    }
  };

  const runScript = async () => {
    if (state.busy) return;
    const text = el.sql.value;
    if (!text.trim()) {
      toast("The worksheet is empty");
      return;
    }
    setBusy(true);
    el.statusRows.textContent = "Running script…";
    const rule = logLine("rule", `Run script · ${clock()}`);
    rule.classList.add("is-head");
    try {
      const payload = await api(endpoints().script, { sql: text });
      if (payload.error) {
        logLine("error", payload.error);
        return;
      }
      payload.statements.forEach((statement) => {
        const style = statement.ok ? (statement.kind === "prepare" ? "note" : "ok") : "error";
        const bits = [
          `Statement ${statement.index} of ${payload.total}`,
          statement.verb || "?",
          describeOutcome(statement),
          `${statement.elapsed_ms} ms`,
        ];
        logLine(style, bits.join(" · "));
      });
      logLine(
        payload.failed ? "error" : "ok",
        `Script complete · ${payload.succeeded} succeeded${
          payload.failed ? `, ${payload.failed} failed` : ""
        }${payload.prepared ? `, ${payload.prepared} prepared but not committed` : ""} · ${payload.elapsed_ms} ms`,
      );
      if (payload.note) logLine("note", payload.note);
      setOutputBadge($$(".st-log-line", el.log).length);
      history.add(text, payload.ok, `${payload.succeeded}/${payload.total} statements succeeded`);
      const firstFailure = payload.statements.find((statement) => !statement.ok);
      const lastRead = [...payload.statements].reverse().find((statement) => statement.ok && statement.kind === "read");
      if (firstFailure) {
        message(
          "error",
          firstFailure.code || "Statement failed",
          `${firstFailure.statement}\n${firstFailure.error}${firstFailure.hint ? `\n\n${firstFailure.hint}` : ""}`,
        );
      }
      if (lastRead) {
        showOutcome(lastRead);
      } else {
        state.payload = null;
        renderGrid();
      }
      el.statusRows.textContent = `${payload.succeeded}/${payload.total} statements`;
      el.statusTime.textContent = `${payload.elapsed_ms} ms`;
      activatePane(firstFailure ? "output" : "results");
      if (state.connection === "oracle") {
        const created = payload.statements.filter((statement) => statement.kind === "ddl" && statement.ok);
        if (created.length) {
          message(
            "note",
            "Schema changed",
            created.map((statement) => `${statement.verb} · ${statement.object || statement.statement.split("\n")[0]}`).join("\n"),
          );
        }
        refreshOracleTree();
      }
      toast(
        payload.failed
          ? `Script finished with ${payload.failed} error${payload.failed === 1 ? "" : "s"}`
          : "Script finished cleanly",
      );
    } finally {
      setBusy(false);
    }
  };

  const explainStatement = async () => {
    if (state.busy) return;
    const sql = statementAtCursor();
    if (!sql) {
      toast("Put the cursor on a statement first");
      return;
    }
    setBusy(true);
    try {
      const payload = await api(endpoints().explain, { sql });
      activatePane("plan");
      renderPlan(payload);
      if (payload.ok) {
        logLine("ok", `EXPLAIN · ${payload.nodes.length} steps · ${payload.elapsed_ms} ms`);
        el.statusRows.textContent = `${payload.nodes.length} plan steps`;
        el.statusTime.textContent = `${payload.elapsed_ms} ms`;
      } else {
        logLine("error", `EXPLAIN · ${payload.error}`);
        message("error", payload.code || "Plan failed", payload.error);
      }
    } finally {
      setBusy(false);
    }
  };

  /* -------------------------------------------------------------------- tree */
  const selectionLabel = (type, name) => {
    if (!type) return name;
    return `${type} · ${name}`;
  };

  const selectObject = (node, type, name) => {
    $$(".st-node-row.is-selected, .st-leaf.is-selected", el.tree).forEach((row) =>
      row.classList.remove("is-selected"),
    );
    if (node) node.classList.add("is-selected");
    state.selection = { type, name };
    el.selectionValue.textContent = selectionLabel(type, name);
    el.selectionValue.title = selectionLabel(type, name);
  };

  const queryFor = (name, columns, limit) => {
    if (!columns || !columns.length) {
      return `SELECT *\nFROM ${name}${limit ? `\nLIMIT ${limit}` : ""};\n`;
    }
    // Wrap the column list the way a client would, so a wide table still reads.
    const lines = [];
    let current = "";
    columns.forEach((column) => {
      const piece = `${current ? ", " : ""}${column}`;
      if (current && (current + piece).length > 72) {
        lines.push(current);
        current = column;
      } else {
        current += piece;
      }
    });
    if (current) lines.push(current);
    const list = lines.join("\n       ");
    return `SELECT ${list}\nFROM ${name}${limit ? `\nLIMIT ${limit}` : ""};\n`;
  };

  const columnsOf = (objectName) => {
    const row = $$(".st-object", el.tree).find(
      (candidate) => candidate.dataset.objectName === objectName,
    );
    if (!row) return [];
    return $$(".st-leaf-column", row.parentElement)
      .map((leaf) => leaf.dataset.column)
      .filter(Boolean);
  };

  const treeAction = (action) => {
    const target = state.contextTarget;
    if (!target) return;
    const { type, name } = target;
    if (action === "copy-name") {
      navigator.clipboard?.writeText(name).then(
        () => toast(`${name} copied`),
        () => toast("The browser blocked the clipboard"),
      );
      return;
    }
    if (action === "describe") {
      describeObject(type, name);
      return;
    }
    if (type !== "table" && type !== "view") {
      toast("Only tables and views can be queried");
      return;
    }
    const columns = columnsOf(name);
    if (action === "query") insertText(queryFor(name, columns, 100));
    if (action === "query-50") insertText(queryFor(name, columns, 50));
    if (action === "select-columns")
      insertText(`${columns.map((column) => `  ${column}`).join(",\n") || "*"}\n`);
    if (action === "insert") insertText(name);
  };

  const describeObject = async (type, name) => {
    if (type !== "table" && type !== "view") {
      message("note", `${type} · ${name}`, "This object is listed in the navigator; open its tab in the database workshop for the full definition.");
      activatePane("messages");
      return;
    }
    try {
      if (state.connection === "oracle") {
        toast("Object details for the practice schema are in the navigator");
        return;
      }
      const url = urls.describe.replace("__object__", encodeURIComponent(name));
      const response = await fetch(url, {
        headers: { Accept: "application/json", "X-CSRF-Token": CSRF },
        credentials: "same-origin",
      });
      const payload = await response.json();
      if (!payload.ok) {
        message("error", "Object details", payload.error || "The object could not be described.");
        activatePane("messages");
        return;
      }
      const lines = (payload.columns || [])
        .map(
          (column) =>
            `${column.name.padEnd(22)} ${String(column.type || "—").padEnd(14)}${
              column.pk ? " PK" : ""
            }${column.notnull || column.nullable === false ? " NOT NULL" : ""}`,
        )
        .join("\n");
      message(
        "note",
        `${payload.type} · ${payload.name}`,
        `${payload.rows !== undefined ? `${payload.rows} rows\n` : ""}${lines}${
          payload.foreign_keys && payload.foreign_keys.length
            ? `\n\nForeign keys: ${payload.foreign_keys
                .map((key) => `${key.column_name} → ${key.ref_table}.${key.ref_column}`)
                .join(", ")}`
            : ""
        }`,
      );
      activatePane("messages");
    } catch (error) {
      message("error", "Object details", "The object could not be described.");
      activatePane("messages");
    }
  };

  /* ------------------------------------------------------------------- menus */
  const closeMenus = () => {
    $$("[data-menu-button]").forEach((button) => button.setAttribute("aria-expanded", "false"));
    $$(".st-menu-list").forEach((list) => {
      list.hidden = true;
    });
  };

  const openMenu = (button) => {
    const list = button.parentElement.querySelector(".st-menu-list");
    const isOpen = button.getAttribute("aria-expanded") === "true";
    closeMenus();
    if (!isOpen) {
      button.setAttribute("aria-expanded", "true");
      list.hidden = false;
      list.querySelector(".st-menu-item")?.focus();
    }
  };

  /* ---------------------------------------------------------------- popovers */
  const popoverAnchor = (popover, anchor) => {
    const box = app.getBoundingClientRect();
    const rect = anchor.getBoundingClientRect();
    const width = 380;
    const left = Math.min(Math.max(12, rect.left - box.left - width + rect.width), box.width - width - 12);
    const top = rect.bottom - box.top + 6;
    popover.style.left = `${Math.max(12, left)}px`;
    popover.style.top = `${top}px`;
  };

  const closePopovers = () => {
    el.snippetPopover.hidden = true;
    el.historyPopover.hidden = true;
    $$("[data-action='snippets'], [data-action='history']").forEach((button) =>
      button.setAttribute("aria-expanded", "false"),
    );
  };

  const openSnippets = (anchor) => {
    const isOpen = !el.snippetPopover.hidden;
    closePopovers();
    if (isOpen) return;
    popoverAnchor(el.snippetPopover, anchor);
    el.snippetPopover.hidden = false;
    anchor.setAttribute("aria-expanded", "true");
    $(".st-snippet", el.snippetPopover)?.focus();
  };

  const openHistory = (anchor) => {
    const isOpen = !el.historyPopover.hidden;
    closePopovers();
    if (isOpen) return;
    const items = history.read();
    el.historyList.innerHTML = items.length
      ? items
          .map(
            (item, index) =>
              `<button type="button" class="st-history-item" data-history="${index}"><code>${escapeHtml(
                item.sql.slice(0, 180),
              )}</code><span>${new Date(item.at).toLocaleString()} · ${
                item.ok ? "succeeded" : "failed"
              }</span></button>`,
          )
          .join("")
      : `<p class="st-popover-empty">Nothing has run in this browser yet.</p>`;
    popoverAnchor(el.historyPopover, anchor);
    el.historyPopover.hidden = false;
    anchor.setAttribute("aria-expanded", "true");
    $(".st-history-item", el.historyPopover)?.focus();
    $$("[data-history]", el.historyPopover).forEach((button) => {
      button.addEventListener("click", () => {
        const item = items[Number(button.dataset.history)];
        if (item) {
          insertText(item.sql);
          closePopovers();
          toast("Statement inserted");
        }
      });
    });
  };

  /* ----------------------------------------------------------------- dialogs */
  let dialogReturnFocus = null;
  const openDialog = (id) => {
    const layer = document.getElementById(id);
    if (!layer) return;
    dialogReturnFocus = document.activeElement;
    layer.hidden = false;
    $("[data-dialog-close]", layer)?.focus();
  };
  const closeDialogs = () => {
    $$(".st-dialog-layer").forEach((layer) => {
      layer.hidden = true;
    });
    if (dialogReturnFocus && document.contains(dialogReturnFocus)) dialogReturnFocus.focus();
    dialogReturnFocus = null;
  };

  /* ---------------------------------------------------------------- actions */
  const actions = {
    "new-worksheet": () => newWorksheet(),
    "duplicate-worksheet": () => duplicateWorksheet(),
    "rename-worksheet": () => renameWorksheet(state.activeId),
    "close-worksheet": () => closeWorksheet(state.activeId),
    "run-statement": () => runStatement(),
    "run-script": () => runScript(),
    explain: () => explainStatement(),
    format: () => formatSql(),
    comment: () => commentLines(false),
    uncomment: () => commentLines(true),
    clear: () => {
      flushHistory();
      el.sql.value = "-- Cleared worksheet\n\n";
      commitEditor();
      recordHistory();
      toast("Worksheet cleared");
    },
    commit: () => {
      if (state.connection === "oracle") {
        logLine("ok", "COMMIT · complete. Every statement on this connection commits as it runs.");
        message("note", "Commit complete",
          "The practice session uses autocommit, the way a SQL*Plus session does after each DDL statement. Nothing is waiting.");
      } else {
        logLine("note", "COMMIT · every statement already commits as it runs.");
        message("note", "Nothing to commit", "This window commits each statement as it runs, so there is nothing pending. Every write is snapshotted — use Undo change to take one back.");
      }
      activatePane("messages");
    },
    rollback: () => {
      if (state.connection === "oracle") {
        logLine("note", "ROLLBACK · nothing pending. The practice session commits as it runs.");
        message("note", "Rollback not needed",
          "Each statement on ORACLE_XE is committed as it runs, so there is no open transaction to undo. Drop or delete what you created instead — or reset the practice schema.");
      } else {
        logLine("note", "ROLLBACK · nothing to roll back. Use Undo change instead.");
        message("note", "Rollback is not needed", "Nothing is pending: use Undo change (Ctrl+Alt+Z) to reverse the last statement, which restores the database exactly.");
      }
      activatePane("messages");
    },
    undo: () => undoEdit(),
    redo: () => redoEdit(),
    "undo-change": () => schemaStep("undo"),
    "redo-change": () => schemaStep("redo"),
    "oracle-undo": () => schemaStep("undo"),
    "oracle-redo": () => schemaStep("redo"),
    "portal-undo": () => schemaStep("undo"),
    "portal-redo": () => schemaStep("redo"),
    "select-all": () => {
      el.sql.focus();
      el.sql.select();
    },
    "copy-sql": () => {
      navigator.clipboard?.writeText(el.sql.value).then(
        () => toast("Worksheet copied"),
        () => toast("The browser blocked the clipboard"),
      );
    },
    "copy-csv": () => {
      const csv = csvFor();
      if (!csv) {
        toast("Run a statement first");
        return;
      }
      navigator.clipboard?.writeText(csv).then(
        () => toast("Results copied as CSV"),
        () => toast("The browser blocked the clipboard"),
      );
    },
    "download-csv": () => {
      const csv = csvFor();
      if (!csv) {
        toast("Run a statement first");
        return;
      }
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const link = document.createElement("a");
      const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, "-");
      link.href = URL.createObjectURL(blob);
      link.download = `sql-studio-${stamp}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(link.href);
      toast("CSV saved");
    },
    snippets: (button) => openSnippets(button),
    history: (button) => openHistory(button),
    describe: () => {
      const target = state.selection;
      if (!target) {
        toast("Select an object in the navigator first");
        return;
      }
      describeObject(target.type, target.name);
    },
    "connection-info": () => {
      message(
        "note",
        "Connection information",
        `${$("#stConnectionSelect")?.value || "connection"}\nWritable · ${el.statusTime.textContent}`,
      );
      activatePane("messages");
    },
    tour: () => startTour(),
    "oracle-info": () => openDialog("stOracleDialog"),
    "oracle-reset": () => resetPractice(),
    about: () => openDialog("stAboutDialog"),
    shortcuts: () => openDialog("stShortcutDialog"),
    "read-only-notice": () => openDialog("stReadOnlyDialog"),
    "collapse-tree": () => {
      $$("[data-tree-toggle]", el.tree).forEach((button) => {
        button.setAttribute("aria-expanded", "false");
        const children = button.parentElement.querySelector(":scope > .st-node-children");
        if (children) children.hidden = true;
      });
      const root = $(".st-node-root", el.tree);
      root.setAttribute("aria-expanded", "true");
      root.parentElement.querySelector(":scope > .st-node-children").hidden = false;
    },
    "expand-tree": () => {
      $$("[data-tree-toggle]", el.tree).forEach((button) => {
        button.setAttribute("aria-expanded", "true");
        const children = button.parentElement.querySelector(":scope > .st-node-children");
        if (children) children.hidden = false;
      });
    },
  };

  const invoke = (action, button) => {
    if (action && actions[action]) {
      actions[action](button);
    }
  };

  /* ------------------------------------------------------------- interactions */
  document.addEventListener("click", (event) => {
    const actionButton = event.target.closest("[data-action]");
    if (actionButton && app.contains(actionButton)) {
      const action = actionButton.dataset.action;
      if (action === "snippets" || action === "history") {
        event.stopPropagation();
        invoke(action, actionButton);
        return;
      }
      closeMenus();
      closePopovers();
      invoke(action, actionButton);
      return;
    }
    if (!event.target.closest(".st-menu")) closeMenus();
    if (!event.target.closest(".st-popover") && !event.target.closest("[data-action='snippets']") &&
        !event.target.closest("[data-action='history']")) {
      closePopovers();
    }
    if (!event.target.closest("#stContextMenu")) el.contextMenu.hidden = true;
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenus();
      closePopovers();
      closeDialogs();
      el.contextMenu.hidden = true;
      if (tour.running) endTour();
    }
    if (tour.running && event.key === "ArrowRight") goToStep(tour.index + 1);
    if (tour.running && event.key === "ArrowLeft") goToStep(tour.index - 1);
  });

  // menus
  $$("[data-menu-button]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openMenu(button);
    });
    button.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        openMenu(button);
      }
    });
    button.parentElement.addEventListener("keydown", (event) => {
      const list = button.parentElement.querySelector(".st-menu-list");
      if (list.hidden) return;
      const items = $$(".st-menu-item", list);
      const position = items.indexOf(document.activeElement);
      if (event.key === "ArrowDown") {
        event.preventDefault();
        items[(position + 1) % items.length]?.focus();
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        items[(position - 1 + items.length) % items.length]?.focus();
      }
      if (event.key === "Tab") closeMenus();
    });
    button.parentElement.querySelectorAll(".st-menu-item").forEach((item) => {
      item.addEventListener("click", () => closeMenus());
    });
  });

  // dialog layers
  $$(".st-dialog-layer").forEach((layer) => {
    layer.addEventListener("click", (event) => {
      if (event.target === layer) closeDialogs();
    });
  });
  $$("[data-dialog-close]").forEach((button) =>
    button.addEventListener("click", () => closeDialogs()),
  );

  // worksheet tabs
  el.tabs.addEventListener("click", (event) => {
    const close = event.target.closest("[data-ws-close]");
    const tab = event.target.closest(".st-ws-tab");
    if (!tab) return;
    const id = Number(tab.dataset.worksheet);
    if (close) {
      event.stopPropagation();
      closeWorksheet(id);
      return;
    }
    if (id !== state.activeId) showWorksheet(id);
  });
  el.tabs.addEventListener("dblclick", (event) => {
    const tab = event.target.closest(".st-ws-tab");
    if (tab) renameWorksheet(Number(tab.dataset.worksheet));
  });
  el.tabs.addEventListener("contextmenu", (event) => {
    const tab = event.target.closest(".st-ws-tab");
    if (!tab) return;
    event.preventDefault();
    renameWorksheet(Number(tab.dataset.worksheet));
  });

  // result tabs
  $$(".st-rtab").forEach((tab) => {
    tab.addEventListener("click", () => activatePane(tab.dataset.pane));
    tab.addEventListener("keydown", (event) => {
      const tabs = $$(".st-rtab");
      const index = tabs.indexOf(tab);
      if (event.key === "ArrowRight") tabs[(index + 1) % tabs.length].focus();
      if (event.key === "ArrowLeft") tabs[(index - 1 + tabs.length) % tabs.length].focus();
    });
  });

  // grid sorting and cell focus
  el.gridHead.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sort]");
    if (button) sortBy(Number(button.dataset.sort));
  });
  el.gridBody.addEventListener("click", (event) => {
    const cell = event.target.closest("td");
    if (!cell) return;
    $$(".st-grid td.is-focused", el.grid).forEach((node) => node.classList.remove("is-focused"));
    cell.classList.add("is-focused");
  });

  // editor
  el.sql.addEventListener("input", () => {
    commitEditor();
    scheduleHistory();
    updateCaret();
  });
  el.sql.addEventListener("blur", flushHistory);
  el.sql.addEventListener("scroll", syncEditorScroll);
  el.sql.addEventListener("click", updateCaret);
  el.sql.addEventListener("keyup", updateCaret);
  el.sql.addEventListener("keydown", (event) => {
    const { selectionStart, selectionEnd, value } = el.sql;
    const command = event.ctrlKey || event.metaKey;
    if (command && event.altKey && event.key.toLowerCase() === "z") {
      event.preventDefault();
      schemaStep("undo");
      return;
    }
    if (command && event.altKey && event.key.toLowerCase() === "y") {
      event.preventDefault();
      schemaStep("redo");
      return;
    }
    if (command && !event.altKey && event.key.toLowerCase() === "z") {
      event.preventDefault();
      if (event.shiftKey) redoEdit();
      else undoEdit();
      return;
    }
    if (command && !event.altKey && event.key.toLowerCase() === "y") {
      event.preventDefault();
      redoEdit();
      return;
    }
    if (event.key === "Tab") {
      event.preventDefault();
      el.sql.setRangeText("    ", selectionStart, selectionEnd, "end");
      commitEditor();
      return;
    }
    if (event.key === "Enter") {
      const lineStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
      const indent = (value.slice(lineStart, selectionStart).match(/^\s*/) || [""])[0];
      const previousWord = value.slice(0, selectionStart).trimEnd().split(/\s+/).pop()?.toUpperCase();
      const extra = ["BEGIN", "THEN", "AS", "("].includes(previousWord) ? "    " : "";
      event.preventDefault();
      el.sql.setRangeText(`\n${indent}${extra}`, selectionStart, selectionEnd, "end");
      commitEditor();
      return;
    }
    if (event.key === "F9" || (event.key === "Enter" && (event.ctrlKey || event.metaKey))) {
      event.preventDefault();
      runStatement();
      return;
    }
    if (event.key === "F5") {
      event.preventDefault();
      runScript();
      return;
    }
    if (event.key === "F10") {
      event.preventDefault();
      explainStatement();
      return;
    }
    if (event.key === "F1") {
      event.preventDefault();
      openDialog("stShortcutDialog");
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "t") {
      event.preventDefault();
      newWorksheet();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "w") {
      event.preventDefault();
      closeWorksheet(state.activeId);
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "/") {
      event.preventDefault();
      commentLines(false);
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === " ") {
      event.preventDefault();
      openSnippets($("[data-action='snippets']"));
      return;
    }
    if (event.key === "Escape") {
      closePopovers();
      closeMenus();
    }
  });

  // windows-level shortcuts outside the editor
  document.addEventListener("keydown", (event) => {
    const inDialog = $$(".st-dialog-layer:not([hidden])").length;
    if (event.key === "F1") {
      event.preventDefault();
      openDialog("stShortcutDialog");
    }
    if (!inDialog && event.key === "F5" && document.activeElement !== el.sql) {
      event.preventDefault();
      runScript();
    }
  });

  // tree
  el.tree.addEventListener("click", (event) => {
    const row = event.target.closest("[data-tree-toggle]");
    if (!row) return;
    const expanded = row.getAttribute("aria-expanded") === "true";
    row.setAttribute("aria-expanded", expanded ? "false" : "true");
    const children = row.parentElement.querySelector(":scope > .st-node-children");
    if (children) children.hidden = expanded;
    if (row.dataset.objectName) {
      selectObject(row, row.dataset.objectType || "object", row.dataset.objectName);
    }
  });

  el.tree.addEventListener("dblclick", (event) => {
    const leaf = event.target.closest(".st-leaf-column");
    if (leaf) {
      insertText(leaf.dataset.column);
      toast(`${leaf.dataset.column} inserted`);
      return;
    }
    const row = event.target.closest(".st-object");
    if (!row) return;
    const name = row.dataset.objectName;
    insertText(queryFor(name, columnsOf(name), 50));
    toast(`SELECT added for ${name}`);
  });

  el.tree.addEventListener("contextmenu", (event) => {
    const row = event.target.closest("[data-object-name]");
    if (!row) return;
    event.preventDefault();
    state.contextTarget = {
      type: row.dataset.objectType || "object",
      name: row.dataset.objectName,
    };
    selectObject(row.classList.contains("st-object") ? row : null, state.contextTarget.type, state.contextTarget.name);
    const box = app.getBoundingClientRect();
    el.contextMenu.hidden = false;
    const width = el.contextMenu.offsetWidth || 214;
    const height = el.contextMenu.offsetHeight || 240;
    const left = Math.min(event.clientX - box.left, box.width - width - 8);
    const top = Math.min(event.clientY - box.top, box.height - height - 8);
    el.contextMenu.style.left = `${Math.max(8, left)}px`;
    el.contextMenu.style.top = `${Math.max(8, top)}px`;
    $(".st-context-item", el.contextMenu)?.focus();
  });

  el.contextMenu.addEventListener("click", (event) => {
    const button = event.target.closest("[data-context]");
    if (!button) return;
    treeAction(button.dataset.context);
    el.contextMenu.hidden = true;
  });

  el.tree.addEventListener("click", (event) => {
    const leaf = event.target.closest(".st-leaf");
    if (!leaf) return;
    selectObject(
      leaf,
      leaf.dataset.objectType || (leaf.dataset.column ? "column" : "object"),
      leaf.dataset.objectName || leaf.dataset.column,
    );
  });

  // filter
  const filterTree = () => {
    const term = el.filter.value.trim().toLowerCase();
    $$(".st-node[data-object-row]", el.tree).forEach((node) => {
      const row = node.querySelector(".st-object");
      const match = !term || row.dataset.objectName.toLowerCase().includes(term);
      node.classList.toggle("is-filtered-out", !match);
      node.classList.toggle("is-match", Boolean(term) && match);
    });
    $$(".st-leaf", el.tree).forEach((leaf) => {
      const text = (leaf.dataset.column || leaf.dataset.objectName || leaf.textContent).toLowerCase();
      const match = !term || text.includes(term);
      leaf.classList.toggle("is-filtered-out", !match);
    });
    if (term) {
      $$(".st-node[data-group]", el.tree).forEach((group) => {
        const button = group.querySelector("[data-tree-toggle]");
        const children = group.querySelector(":scope > .st-node-children");
        button.setAttribute("aria-expanded", "true");
        if (children) children.hidden = false;
      });
    }
  };
  el.filter?.addEventListener("input", filterTree);

  // snippets
  $$("[data-snippet]", el.snippetPopover).forEach((button) => {
    button.addEventListener("click", () => {
      insertText(button.dataset.snippet);
      closePopovers();
      toast("Snippet inserted");
    });
  });
  $$("[data-popover-close]").forEach((button) =>
    button.addEventListener("click", () => closePopovers()),
  );


  /* -------------------------------------------------------- second connection */
  const sessionChip = $("#stSessionChip");
  const sessionChipText = $("#stSessionChipText");
  const connectionSelect = $("#stConnectionSelect");

  const statusConnectionName = () =>
    ($("#stStatusConnection")?.textContent || "").split("@")[0] || "user";

  const setChip = (mode) => {
    const oracle = mode === "oracle";
    const name = `${statusConnectionName()}@${oracle ? "ORACLE_XE" : "NIST_UNIVERSITY"}`;
    const conn = $("#stStatusConnection");
    if (conn) conn.textContent = name;
    const menuNote = $("#stMenuConnection");
    if (menuNote) menuNote.textContent = name;
    const statusMode = $("#stStatusMode");
    if (statusMode) {
      statusMode.innerHTML = `${lockIcon("unlocked")}<span>Writable</span>`;
    }
    const engine = $("#stStatusEngine");
    if (engine) engine.textContent = oracle ? "Oracle 21c XE · simulated" : "SQLite 3.40.1";
    const charset = $("#stStatusCharset");
    if (charset) charset.textContent = oracle ? "AL32UTF8" : "UTF-8";
    const banner = $("#stSessionBannerText");
    if (banner) {
      banner.textContent = oracle
        ? `Connected to ORACLE_XE as ${statusConnectionName()}. This practice schema is writable.`
        : `Connected to NIST_UNIVERSITY as ${statusConnectionName()}. Changes here reach the portal.`;
    }
    const factsPortal = $("#stFactsPortal");
    const factsOracle = $("#stFactsOracle");
    if (factsPortal) factsPortal.hidden = oracle;
    if (factsOracle) factsOracle.hidden = !oracle;
    sessionChip.dataset.mode = mode;
    sessionChip.classList.add("is-writable");
    sessionChipText.textContent = oracle
      ? "Practice schema · writable"
      : "Live data · linked to the portal";
    sessionChip.title = oracle
      ? "CREATE, INSERT, UPDATE and DELETE run in the practice schema, never the portal"
      : "Changes run against the portal's own database and appear on its screens; every change can be undone";
  };

  const switchConnection = (mode) => {
    if (mode === state.connection) return;
    flushHistory();
    state.memory[state.connection] = el.sql.value;
    state.connection = mode;
    state.journal = state.journals[mode] || {};
    setChip(mode);
    $("#stTreePortal").hidden = mode !== "portal";
    $("#stTreeOracle").hidden = mode !== "oracle";
    $("#stSnippetPortal").hidden = mode !== "portal";
    $("#stSnippetOracle").hidden = mode !== "oracle";
    const stored = state.memory[mode];
    el.sql.value = stored !== null && stored !== undefined
      ? stored
      : mode === "oracle"
        ? oracleStarter
        : (activeWorksheet()?.sql || "");
    commitEditor();
    state.payload = null;
    renderGrid();
    const command = $("#stCommand");
    if (command) {
      command.hidden = true;
      command.innerHTML = "";
    }
    el.resultEmpty.hidden = false;
    el.resultEmpty.querySelector("h2").textContent =
      mode === "oracle" ? "The practice schema is ready" : "No statement has run yet";
    el.resultEmpty.querySelector("p").textContent =
      mode === "oracle"
        ? "EMP, DEPT and EMP_SEQ are loaded. Press F9 to run the statement under the cursor — CREATE, INSERT, UPDATE and DELETE really work here."
        : "Press F9 to run the statement under the cursor, or F5 to run the whole worksheet. This window writes to the portal's own database, so a change made here is the change Students, Fees and Reports show. Every change can be undone.";
    recordHistory();
    updateHistoryButtons();
    updateSchemaButtons();
    el.statusRows.textContent = "No statement run";
    el.statusTime.textContent = "—";
    message(
      "note",
      mode === "oracle" ? "Connected to ORACLE_XE" : "Connected to NIST_UNIVERSITY",
      mode === "oracle"
        ? "Oracle Database 21c Express Edition (simulated). This session is writable: DDL and DML change the practice schema, never the portal."
        : "Linked to the portal: INSERT, UPDATE, DELETE and CREATE run against the live database, so the change is on the portal's screens immediately. Undo takes it back.",
    );
    activatePane("results");
    toast(mode === "oracle" ? "ORACLE_XE · practice schema (writable)" : "NIST_UNIVERSITY · linked to the portal");
    el.sql.focus();
  };

  // The Oracle navigator is rebuilt after DDL, so it always matches the schema.
  const treeNode = (kind, name, meta, extra) =>
    `<div class="st-node" data-node data-object-row>
       <button type="button" class="st-node-row st-object" data-tree-toggle aria-expanded="false"
               data-object-type="${kind}" data-object-name="${escapeHtml(name)}">
         <span class="st-caret" aria-hidden="true"></span>
         <span class="st-node-label">${escapeHtml(name)}</span>
         <span class="st-node-meta">${escapeHtml(meta)}</span>
       </button>
       <div class="st-node-children" hidden>${extra}</div>
     </div>`;

  const leafNode = (kind, name, label, meta) =>
    `<button type="button" class="st-leaf" data-object-type="${kind}" data-object-name="${escapeHtml(name)}"
             ${kind === "column" ? `data-column="${escapeHtml(name)}"` : ""}>
       <span class="st-leaf-name">${escapeHtml(name)}</span>
       <span class="st-leaf-type">${escapeHtml(meta || label || "")}</span>
     </button>`;

  const renderOracleTree = (catalogue) => {
    const tables = catalogue.tables
      .map((table) =>
        treeNode(
          "table",
          table.name,
          table.rows.toLocaleString(),
          table.columns
            .map((column) =>
              leafNode(
                "column",
                column.name,
                "",
                `${column.type}${column.pk ? " · PK" : ""}${column.nullable ? "" : " · NN"}`,
              ),
            )
            .join(""),
        ),
      )
      .join("");
    $("#stOracleTables").innerHTML = tables;
    $("#stOracleTableCount").textContent = catalogue.tables.length;
    $("#stOracleSequences").innerHTML = catalogue.sequences
      .map((sequence) => leafNode("sequence", sequence.name, "", `next ${sequence.next}`))
      .join("");
    $("#stOracleSequenceCount").textContent = catalogue.sequences.length;
    $("#stOracleViews").innerHTML = catalogue.views
      .map((view) => leafNode("view", view.name, "", `${view.columns.length} columns`))
      .join("");
    $("#stOracleViewCount").textContent = catalogue.views.length;
    $("#stOracleIndexes").innerHTML = catalogue.indexes
      .map((index) => leafNode("index", index.name, "", index.table))
      .join("");
    $("#stOracleIndexCount").textContent = catalogue.indexes.length;
  };

  const refreshPortalTree = async () => {
    try {
      const response = await fetch(app.dataset.portalTreeUrl, {
        headers: { Accept: "application/json", "X-CSRF-Token": CSRF },
        credentials: "same-origin",
      });
      const payload = await response.json();
      if (!payload || !payload.ok) return;
      if (typeof payload.tree_html === "string") {
        const host = $("#stTreePortal");
        if (host) host.innerHTML = payload.tree_html;
      }
      if (payload.journal) state.journals.portal = payload.journal;
      setJournal(payload.journal);
    } catch (error) {
      /* the navigator keeps its previous contents */
    }
  };

  const refreshOracleTree = async () => {
    if (state.connection !== "oracle") return;
    try {
      const response = await fetch(endpoints().tree, {
        headers: { Accept: "application/json", "X-CSRF-Token": CSRF },
        credentials: "same-origin",
      });
      const payload = await response.json();
      if (payload.ok) {
        renderOracleTree(payload.catalogue);
        if (payload.journal) setJournal(payload.journal);
        if (el.filter?.value.trim()) el.filter.dispatchEvent(new Event("input"));
      }
    } catch (error) {
      /* the navigator simply keeps the last known schema */
    }
  };

  // ---------------------------------------------------- undoing real changes
  const setJournal = (journal) => {
    if (journal) state.journals[state.connection] = journal;
    state.journal = state.journals[state.connection] || {};
    updateSchemaButtons();
  };

  const updateSchemaButtons = () => {
    const journal = state.journal || {};
    const scope = state.connection === "oracle" ? "practice schema" : "portal";
    $$("[data-action='undo-change'], [data-action='oracle-undo'], [data-action='portal-undo']").forEach((button) => {
      button.disabled = !journal.can_undo;
      button.title = journal.can_undo ? `Undo the last ${scope} change: ${journal.undo_label}` : `No ${scope} change to undo`;
    });
    $$("[data-action='redo-change'], [data-action='oracle-redo'], [data-action='portal-redo']").forEach((button) => {
      button.disabled = !journal.can_redo;
      button.title = journal.can_redo ? `Redo: ${journal.redo_label}` : "Nothing to redo";
    });
    const stateLine = $("#stJournalState");
    if (stateLine) {
      stateLine.textContent = `${journal.depth || 0}/${journal.limit || 12}`;
    }
  };

  const schemaStep = async (direction) => {
    if (state.busySchema) return;
    const oracle = state.connection === "oracle";
    const scope = oracle ? "practice schema" : "portal";
    state.busySchema = true;
    try {
      const response = await fetch(endpoints()[direction], {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": CSRF },
        credentials: "same-origin",
        body: "{}",
      });
      const payload = await response.json().catch(() => null);
      if (!payload) {
        toast("The studio could not reach the server");
        return;
      }
      if (!payload.ok) {
        setJournal(payload.journal);
        toast(payload.error || "Nothing to do");
        message("note",
                `${scope}: ${direction === "undo" ? "nothing to undo" : "nothing to redo"}`,
                payload.error || "The journal is empty.");
        return;
      }
      if (payload.catalogue && oracle) renderOracleTree(payload.catalogue);
      setJournal(payload.journal);
      if (!oracle) await refreshPortalTree();
      const command = $("#stCommand");
      if (command) {
        command.hidden = true;
        command.innerHTML = "";
      }
      state.payload = null;
      renderGrid();
      el.resultEmpty.hidden = false;
      el.resultEmpty.querySelector("h2").textContent =
        direction === "undo" ? "Change undone" : "Change replayed";
      el.resultEmpty.querySelector("p").textContent = oracle
        ? `${payload.message}. The navigator and the practice schema agree again.`
        : `${payload.message}. The portal database is back the way it was — Students, Fees and Reports read it on their next load.`;
      logLine("ok", `${direction === "undo" ? "UNDO" : "REDO"} · ${payload.message}`);
      message(
        "note",
        `${scope} ${direction === "undo" ? "restored" : "replayed"}`,
        oracle
          ? `${payload.message}. Undo reaches back twelve changes; Reset practice schema starts the demonstration over.`
          : `${payload.message}. Undo reaches back twelve portal changes, so a wrong INSERT here is one click away from being gone.`,
      );
      el.statusRows.textContent = payload.message;
      el.statusTime.textContent = "—";
      activatePane("results");
      toast(payload.message);
    } finally {
      state.busySchema = false;
    }
  };

  const resetPractice = async () => {
    if (state.connection !== "oracle") {
      toast("Switch to the Oracle connection first");
      return;
    }
    const response = await fetch(endpoints().reset, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": CSRF },
      credentials: "same-origin",
      body: "{}",
    });
    const payload = await response.json().catch(() => null);
    if (!payload) {
      toast("The reset did not reach the server");
      return;
    }
    await refreshOracleTree();
    setJournal({ can_undo: false, can_redo: false });
    logLine("note", `Practice schema reset · ${payload.tables} tables · SCOTT seed restored`);
    message("note", "Practice schema reset", "Every object you created was dropped and EMP/DEPT/EMP_SEQ were seeded again.");
    toast("Practice schema reset");
  };

  connectionSelect?.addEventListener("change", (event) => switchConnection(event.target.value));

  /* -------------------------------------------------------------------- tour */
  const tourSteps = [
    {
      target: ".st-titlebar",
      title: "The connection",
      text: "A client is useless until it is connected. This bar names the connection, the engine and its version, and says whether the window writes: the portal connection is live and undoable, the practice connection is separate.",
    },
    {
      target: ".st-navigator",
      title: "The navigator",
      text: "Every table, view, index, trigger and stored program in this schema, read from the catalogue. Expand a table to see its columns and their types.",
      before: () => {
        const group = $('[data-group="tables"] > [data-tree-toggle]', el.tree);
        if (group && group.getAttribute("aria-expanded") !== "true") group.click();
      },
    },
    {
      target: "#stEditorBox",
      title: "The worksheet",
      text: "Type here the way you would in any client: the gutter counts lines, keywords colour themselves, Tab indents, Ctrl+/ comments a block. The statement under the cursor is what F9 runs.",
      before: () => {
        el.sql.value = "-- The tour wrote this statement. End the tour and your worksheet comes back.\nSELECT s.roll_no,\n       s.first_name || ' ' || s.last_name AS student,\n       d.dept_code,\n       s.current_semester,\n       s.status\nFROM student s\nJOIN department d ON d.dept_id = s.dept_id\nORDER BY s.roll_no\nLIMIT 25;\n";
        commitEditor();
        activatePane("results");
        el.sql.focus();
      },
    },
    {
      target: ".st-results",
      title: "The result grid",
      text: "F9 compiles and runs the statement. The grid holds what came back, sortable by any column, with the row count and the engine's own timing underneath.",
      before: async () => {
        await runStatement();
      },
    },
    {
      target: ".st-results-tabs",
      title: "One statement, four views",
      text: "Results shows rows, Script output shows a line per statement with timings, Explain shows the plan, and Messages shows what the session wants to tell you.",
      before: () => {
        activatePane("messages");
      },
    },
    {
      target: ".st-tool-run",
      title: "Yours to drive",
      text: "That is the whole tool. Run scripts with F5, plan with F10, save any grid as CSV, and open the database workshop when you want the theory behind what you just ran.",
      before: () => {
        activatePane("results");
      },
    },
  ];

  const tour = { index: 0, running: false, backup: null };

  const tourNodes = {
    layer: $("#stTour"),
    ring: $("#stTourRing"),
    card: $(".st-tour-card"),
    step: $("#stTourStep"),
    title: $("#stTourTitle"),
    text: $("#stTourText"),
    next: $("[data-tour='next']"),
  };

  const placeTour = () => {
    const step = tourSteps[tour.index];
    const target = $(step.target);
    if (!target || !tour.running) return;
    const box = app.getBoundingClientRect();
    const rect = target.getBoundingClientRect();
    const pad = 6;
    tourNodes.ring.style.left = `${rect.left - box.left - pad}px`;
    tourNodes.ring.style.top = `${rect.top - box.top - pad}px`;
    tourNodes.ring.style.width = `${Math.min(rect.width + pad * 2, box.width - 16)}px`;
    tourNodes.ring.style.height = `${rect.height + pad * 2}px`;
    const cardWidth = 340;
    const below = rect.bottom - box.top + 14;
    const above = rect.top - box.top - 14;
    const tall = rect.height > box.height * 0.55;
    const top = tall
      ? Math.max(12, Math.min(box.height - 210, above - 130))
      : Math.min(below, box.height - 210);
    const left = Math.min(Math.max(14, rect.right - box.left - cardWidth), box.width - cardWidth - 16);
    tourNodes.card.style.left = `${Math.max(14, left)}px`;
    tourNodes.card.style.top = `${Math.max(12, top)}px`;
  };

  const renderTourStep = () => {
    const step = tourSteps[tour.index];
    tourNodes.step.textContent = `Step ${tour.index + 1} of ${tourSteps.length}`;
    tourNodes.title.textContent = step.title;
    tourNodes.text.textContent = step.text;
    tourNodes.next.textContent = tour.index === tourSteps.length - 1 ? "Finish" : "Next";
    placeTour();
  };

  const goToStep = async (index) => {
    if (!tour.running) return;
    tour.index = Math.max(0, Math.min(tourSteps.length - 1, index));
    const step = tourSteps[tour.index];
    if (step.before) {
      try {
        await step.before();
      } catch (error) {
        /* a step that cannot prepare itself still shows its explanation */
      }
    }
    renderTourStep();
    tourNodes.next.focus();
    setTimeout(placeTour, 60);
  };

  const startTour = () => {
    if (tour.running) {
      endTour();
      return;
    }
    const worksheet = activeWorksheet();
    tour.backup = { id: worksheet.id, sql: worksheet.sql };
    tour.running = true;
    tour.index = 0;
    tourNodes.layer.hidden = false;
    document.body.classList.add("is-touring");
    goToStep(0);
  };

  const endTour = (restore = true) => {
    if (!tour.running) return;
    tour.running = false;
    tourNodes.layer.hidden = true;
    document.body.classList.remove("is-touring");
    if (restore && tour.backup) {
      const worksheet = state.worksheets.find((item) => item.id === tour.backup.id);
      if (worksheet) {
        worksheet.sql = tour.backup.sql;
        if (state.activeId === worksheet.id) {
          el.sql.value = worksheet.sql;
          paintEditor();
          saveState();
        }
      }
    }
    tour.backup = null;
    el.sql.focus();
    toast("Tour finished — your worksheet is back");
  };

  tourNodes.next.addEventListener("click", () => {
    if (tour.index >= tourSteps.length - 1) endTour();
    else goToStep(tour.index + 1);
  });
  $("[data-tour='back']").addEventListener("click", () => goToStep(tour.index - 1));
  $("[data-tour='end']").addEventListener("click", () => endTour());
  window.addEventListener("resize", placeTour);
  el.sql.addEventListener("scroll", placeTour);

  /* -------------------------------------------------------------------- boot */
  loadState();
  updateHistoryButtons();
  updateSchemaButtons();
  el.sql.value = activeWorksheet().sql;
  renderTabs();
  paintEditor();
  updateCaret();
  setOutputBadge($$(".st-log-line", el.log).length);
  message(
    "note",
    "Session opened",
    "NIST_UNIVERSITY · linked to the portal. Reads, writes and schema changes run for real; every change is snapshotted and can be undone. Switch to ORACLE_XE for the separate practice schema.",
  );
  el.messageBadge.hidden = true;

  // Keep the two editor layers together when the pane is resized.
  new ResizeObserver(syncEditorScroll).observe(el.editorBox);
})();
