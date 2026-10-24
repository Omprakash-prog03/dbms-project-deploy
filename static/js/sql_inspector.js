// ============================================================================
// "SHOW SQL" LIVE DATABASE INSPECTOR (VIVA DEFENSE TOOL)
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
  const showSqlBtn = document.getElementById("showSqlBtn");
  const sqlModal = document.getElementById("sqlModal");
  const sqlContent = document.getElementById("sqlModalContent");
  const sqlEngine = document.getElementById("sqlModalEngine");

  if (showSqlBtn) {
    showSqlBtn.addEventListener("click", () => {
      apiRequest("/api/inspect-sql")
        .then((data) => {
          if (sqlEngine) {
            sqlEngine.textContent = `${data.engine} | Schema: ${data.database}`;
          }

          if (!data.queries || data.queries.length === 0) {
            sqlContent.innerHTML = `<p style="color: #8E8E8E; padding: 20px 0;">No direct SQL queries were recorded for this view request.</p>`;
          } else {
            let html = "";
            data.queries.forEach((q, idx) => {
              html += `
                            <div style="background: #181818; color: #E0E0E0; border-radius: 16px; padding: 18px; margin-bottom: 16px; font-family: monospace; font-size: 13px; line-height: 1.5; overflow-x: auto;">
                                <div style="display: flex; justify-content: space-between; color: #888; font-size: 11px; margin-bottom: 8px; border-bottom: 1px solid #333; padding-bottom: 4px;">
                                    <span>Query #${idx + 1}</span>
                                    <span>Execution Time: <strong style="color: #3DDC84;">${q.duration_ms} ms</strong></span>
                                </div>
                                <pre style="margin: 0; white-space: pre-wrap; color: #F5F5F5;">${escapeHtml(q.sql)}</pre>
                                ${
                                  q.params && q.params.length > 0
                                    ? `
                                <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #282828; color: #A3A3A3; font-size: 11.5px;">
                                    <strong>Bound Parameters:</strong> [${q.params.map((p) => `"${escapeHtml(String(p))}"`).join(", ")}]
                                </div>`
                                    : ""
                                }
                            </div>`;
            });
            sqlContent.innerHTML = html;
          }
          openModal("sqlModal");
        })
        .catch((err) => {
          showToast("Could not inspect SQL: " + err, "error");
        });
    });
  }

  function escapeHtml(string) {
    return String(string)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
});
