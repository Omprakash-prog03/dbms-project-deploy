// Database workshop: run a join, re-plan it, walk a procedure, evaluate a function
// and try to break a trigger — all without reloading the page. The server renders
// the first result, so the page is complete even if this file never loads.
(() => {
  const token =
    document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";

  const escape = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[character],
    );

  const cellHtml = (cell) => {
    const classes = [cell.null ? "is-null" : "", cell.numeric ? "is-num" : ""]
      .filter(Boolean)
      .join(" ");
    return `<td class="${classes}">${escape(cell.text)}</td>`;
  };

  const gridHtml = (result) => {
    if (!result) return "";
    if (!result.ok) {
      return `<div class="ws-error" role="alert"><strong>The engine refused this statement.</strong>
        <p>${escape(result.error)}</p></div>`;
    }
    const head = result.columns
      .map((column) => `<th scope="col">${escape(column)}</th>`)
      .join("");
    const body = result.rows.length
      ? result.rows
          .map(
            (row) =>
              `<tr><td class="ws-rownum" aria-hidden="true">${row.number}</td>${row.cells
                .map(cellHtml)
                .join("")}</tr>`,
          )
          .join("")
      : `<tr><td class="ws-empty" colspan="${result.columns.length + 1}">No rows selected.</td></tr>`;
    const engine = document.querySelector(".ws-engine-chip")?.innerText?.trim() || "";
    const truncated = result.truncated
      ? `<span aria-hidden="true">·</span><span class="ws-warn">showing the first ${result.shown}</span>`
      : "";
    return `<div class="ws-grid-wrap" tabindex="0" role="region" aria-label="Result rows"><table class="ws-grid">
      <thead><tr><th class="ws-rownum" scope="col"><span aria-hidden="true">#</span><span class="sr-only">Row</span></th>${head}</tr></thead>
      <tbody>${body}</tbody></table></div>
      <div class="ws-statusbar">
        <span><strong>${result.row_count}</strong> row${result.row_count === 1 ? "" : "s"} selected</span>
        <span aria-hidden="true">·</span><span>${result.elapsed_ms} ms</span>
        ${truncated}
        <span class="ws-statusbar-spacer"></span>
        <span class="ws-statusbar-engine">${escape(engine)}</span>
      </div>`;
  };

  const planHtml = (plan) => {
    if (!plan || !plan.ok) {
      return `<div class="ws-error"><p>${escape(plan?.error || "No plan available.")}</p></div>`;
    }
    const steps = plan.steps
      .map(
        (step) => `<li class="ws-plan-step ws-plan-step-${step.kind}">
          <span class="ws-plan-kind">${escape(step.kind)}</span>
          <span class="ws-mono">${escape(step.detail)}</span></li>`,
      )
      .join("");
    const verdict =
      plan.verdict === "index" ? "Index lookups only" : "Full table scan involved";
    return `<div class="ws-plan-verdict ws-plan-${plan.verdict}">${verdict}</div>
      <ol class="ws-plan-steps">${steps}</ol>
      <p class="ws-muted">${escape(plan.summary)}</p>`;
  };

  const dryRunHtml = (outcome) => {
    if (!outcome || !outcome.steps || !outcome.steps.length) {
      return `<div class="ws-error"><p>${escape(
        outcome?.error || "No check could be run.",
      )}</p></div>`;
    }
    const steps = outcome.steps
      .map(
        (step) => `<div class="ws-dryrun-step ${step.ok ? "is-pass" : "is-stop"}">
          <div class="ws-dryrun-head">
            <span class="ws-dryrun-badge">${step.ok ? "PASS" : "STOP"}</span>
            <strong>${escape(step.title)}</strong>
          </div>
          <pre class="ws-code ws-code-inline">${escape(step.sql)}</pre>
          <p class="ws-dryrun-detail">${escape(step.detail)}</p>
        </div>`,
      )
      .join("");
    return `<div class="ws-dryrun">${steps}
      <p class="ws-dryrun-verdict">${escape(outcome.verdict || "")}</p></div>`;
  };

  const proofHtml = (outcome) => {
    if (!outcome || outcome.ok === false) {
      return `<div class="ws-proof-inner"><div class="ws-proof-verdict">Not demonstrated</div>
        <p class="ws-proof-meta">${escape(outcome?.error || "Nothing to attempt.")}</p></div>`;
    }
    const refused = outcome.refused;
    const verdict = refused
      ? "The guard refused it"
      : "⚠ The statement was accepted — this rule did not fire";
    return `<div class="ws-proof-inner ${refused ? "" : "is-open"}">
      <div class="ws-proof-verdict">${refused ? "✓" : "⚠"} ${verdict}</div>
      <pre class="ws-code ws-code-inline">${escape(outcome.statement || "")}</pre>
      <p class="ws-proof-message">${escape(outcome.message || "")}</p>
      <p class="ws-proof-meta">
        Attempted and rolled back in ${outcome.elapsed_ms} ms${outcome.setup_note ? ` · ${escape(outcome.setup_note)}` : ""} ·
        ${escape(outcome.expects || "")}
      </p>
    </div>`;
  };

  const post = async (url, onDone, button) => {
    if (button) {
      button.disabled = true;
      button.dataset.label = button.dataset.label || button.innerHTML;
      button.innerHTML = "Working…";
    }
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRF-Token": token,
        },
        credentials: "same-origin",
        body: "{}",
      });
      const payload = await response.json().catch(() => null);
      if (!payload) {
        onDone({ ok: false, error: `The server answered ${response.status}.` });
        return;
      }
      onDone(payload);
    } catch (error) {
      onDone({ ok: false, error: "The request did not reach the server. Try again." });
    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = button.dataset.label || button.innerHTML;
      }
    }
  };

  // ---- run a join ---------------------------------------------------------
  document.querySelectorAll("[data-ws-run]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById("wsResult");
      if (target) target.classList.add("ws-busy");
      post(`/database/run/${button.dataset.wsRun}`, (payload) => {
        if (target) {
          target.classList.remove("ws-busy");
          target.innerHTML = gridHtml(payload);
        }
      }, button);
    });
  });

  // ---- re-plan an existing panel -----------------------------------------
  document.querySelectorAll("[data-ws-explain]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.wsExplain;
      const target =
        document.getElementById(button.dataset.wsPlanTarget || "") ||
        document.querySelector("#wsResult")?.parentElement.querySelector(".ws-plan-verdict")
          ?.parentElement ||
        null;
      const holder = target?.tagName === "DETAILS" ? target : target;
      post(`/database/explain/${key}`, (payload) => {
        if (!holder) return;
        if (holder.tagName === "DETAILS") {
          const verdict = holder.querySelector(".ws-plan-verdict");
          const steps = holder.querySelector(".ws-plan-steps");
          const summary = holder.querySelector(".ws-muted");
          if (payload.ok) {
            if (verdict) {
              verdict.className = `ws-plan-verdict ws-plan-${payload.verdict}`;
              verdict.textContent =
                payload.verdict === "index"
                  ? "Index lookups only"
                  : "Full table scan involved";
            }
            if (steps) {
              steps.innerHTML = payload.steps
                .map(
                  (step) => `<li class="ws-plan-step ws-plan-step-${step.kind}">
                    <span class="ws-plan-kind">${escape(step.kind)}</span>
                    <span class="ws-mono">${escape(step.detail)}</span></li>`,
                )
                .join("");
            }
            if (summary) summary.textContent = payload.summary;
          }
        } else {
          holder.innerHTML = planHtml(payload);
        }
      }, button);
    });
  });

  // ---- evaluate a function ----------------------------------------------
  document.querySelectorAll("[data-ws-function]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById("wsFunction");
      post(`/database/function/${button.dataset.wsFunction}`, (payload) => {
        if (!target) return;
        target.innerHTML =
          (payload.blurb ? `<p class="ws-note">${escape(payload.blurb)}</p>` : "") +
          gridHtml(payload);
      }, button);
    });
  });

  // ---- walk a procedure --------------------------------------------------
  document.querySelectorAll("[data-ws-procedure]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById("wsDryRun");
      post(
        `/database/procedure/${encodeURIComponent(button.dataset.wsProcedure)}`,
        (payload) => {
          if (target) target.innerHTML = dryRunHtml(payload);
        },
        button,
      );
    });
  });

  // ---- try to break a trigger -------------------------------------------
  document.querySelectorAll("[data-ws-prove]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.wsProveTarget;
      const target = id ? document.getElementById(id) : null;
      if (target) {
        target.hidden = false;
        target.innerHTML = `<div class="ws-proof-inner"><p class="ws-proof-meta">
          Running the statement and rolling it back…</p></div>`;
      }
      post(`/database/prove/${button.dataset.wsProve}`, (payload) => {
        if (target) target.innerHTML = proofHtml(payload);
      }, button);
    });
  });
})();
