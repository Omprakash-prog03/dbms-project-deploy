// Supreme control: copy secrets, confirm destructive actions, disarm the lock.
(() => {
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.dataset.copy || "";
      const original = button.textContent;
      try {
        await navigator.clipboard.writeText(value);
        button.textContent = "Copied";
      } catch (error) {
        // Clipboard needs permission; select the text so it can be copied by hand.
        const output = button.parentElement.querySelector("output");
        if (output && window.getSelection) {
          const range = document.createRange();
          range.selectNodeContents(output);
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
        }
        button.textContent = "Select and copy";
      }
      setTimeout(() => {
        button.textContent = original;
      }, 1800);
    });
  });

  // A lockdown ends everyone else's session, so it takes two deliberate clicks.
  const form = document.getElementById("lockdownForm");
  const lockButton = form ? form.querySelector(".supreme-lock") : null;
  if (lockButton) lockButton.dataset.label = lockButton.innerHTML;
  if (form && lockButton) {
    form.addEventListener("submit", (event) => {
      if (lockButton.dataset.armed === "true") return;
      event.preventDefault();
      const key = form.querySelector('input[name="master_key"]');
      if (!key || !key.value) {
        key.focus();
        return;
      }
      lockButton.dataset.armed = "true";
      lockButton.classList.add("is-armed");
      lockButton.textContent = "Click again to sign everyone out";
      setTimeout(() => {
        lockButton.dataset.armed = "false";
        lockButton.classList.remove("is-armed");
        lockButton.innerHTML = lockButton.dataset.label;
      }, 6000);
    });
  }

  // Removing an administrator is irreversible from the UI: make them read it.
  document.querySelectorAll("form[data-confirm]").forEach((target) => {
    target.addEventListener("submit", (event) => {
      if (target.dataset.confirmed === "true") return;
      if (!window.confirm(target.dataset.confirm)) {
        event.preventDefault();
        return;
      }
      target.dataset.confirmed = "true";
    });
  });

  // Close any open "more actions" menu when clicking elsewhere.
  document.addEventListener("click", (event) => {
    document.querySelectorAll(".supreme-more[open]").forEach((details) => {
      if (!details.contains(event.target)) details.removeAttribute("open");
    });
  });
})();
