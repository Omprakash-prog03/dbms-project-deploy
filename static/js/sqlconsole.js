// SQL console: keyboard shortcut, history recall and example templates.
(() => {
  const form = document.getElementById("sqlForm");
  const input = document.getElementById("statement");
  if (!form || !input) return;

  const focusAtEnd = () => {
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  };

  // Ctrl/Cmd + Enter runs without reaching for the mouse.
  input.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  const load = (sql) => {
    input.value = sql;
    focusAtEnd();
  };

  document.querySelectorAll("[data-sql]").forEach((button) => {
    button.addEventListener("click", () => load(button.dataset.sql));
  });

  const clear = document.getElementById("sqlClear");
  if (clear) {
    clear.addEventListener("click", (event) => {
      event.preventDefault();
      input.value = "";
      focusAtEnd();
    });
  }

  // Keep the prompt usable: grow with the statement, up to a comfortable height.
  const grow = () => {
    input.style.height = "auto";
    input.style.height = Math.min(Math.max(input.scrollHeight, 104), 320) + "px";
  };
  input.addEventListener("input", grow);
  grow();
  focusAtEnd();
})();
