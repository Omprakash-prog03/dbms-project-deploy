// Owner controls: copy one-time codes without retyping them.
(() => {
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.dataset.copy || "";
      try {
        await navigator.clipboard.writeText(value);
        const original = button.textContent;
        button.textContent = "Copied";
        setTimeout(() => {
          button.textContent = original;
        }, 1600);
      } catch (error) {
        // Clipboard needs HTTPS and permission; a selection is the fallback.
        const output = button.parentElement.querySelector("output");
        if (output && window.getSelection) {
          const range = document.createRange();
          range.selectNodeContents(output);
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
        }
      }
    });
  });

  // A lock is irreversible for everyone else, so make the intent deliberate.
  const form = document.getElementById("lockdownForm");
  const lockButton = form ? form.querySelector(".owner-lock-btn") : null;
  if (lockButton) lockButton.dataset.label = lockButton.innerHTML;
  if (form) {
    form.addEventListener("submit", (event) => {
      const button = form.querySelector(".owner-lock-btn");
      if (button && button.dataset.armed !== "true") {
        event.preventDefault();
        button.dataset.armed = "true";
        button.textContent = "Click again to sign everyone out";
        setTimeout(() => {
          button.dataset.armed = "false";
          button.innerHTML = button.dataset.label;
        }, 5000);
      }
    });
  }
})();
