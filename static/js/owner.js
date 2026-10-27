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


  // The rotating code counts down on its own and fetches the next number when it
  // rolls over, so the supreme page never shows a stale code.
  const rotatingCode = document.getElementById("rotatingCode");
  const rotatingTimer = document.getElementById("rotatingTimer");
  const rotatingNext = document.getElementById("rotatingNext");
  if (rotatingCode && rotatingTimer) {
    let left = Number(rotatingTimer.dataset.seconds || 600);
    const minutes = Number(rotatingTimer.dataset.minutes || 10);
    const copyButton = document.getElementById("rotatingCopy");
    const paint = () => {
      const safe = Math.max(0, left);
      rotatingTimer.textContent = `changes in ${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, "0")}`;
    };
    const refresh = async () => {
      try {
        const response = await fetch("/owner/rotating-code", {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });
        if (!response.ok) return;
        const data = await response.json();
        if (rotatingCode.textContent !== data.code) {
          rotatingCode.textContent = data.code;
          if (copyButton) copyButton.dataset.copy = data.code;
          rotatingCode.classList.remove("is-fresh");
          void rotatingCode.offsetWidth;
          rotatingCode.classList.add("is-fresh");
        }
        left = Number(data.seconds_left || minutes * 60);
        if (rotatingNext && data.next_change_label) {
          rotatingNext.textContent = data.next_change_label;
        }
        paint();
      } catch (error) {
        /* offline: keep counting, the number is re-read on the next tick */
      }
    };
    paint();
    setInterval(() => {
      left -= 1;
      if (left <= 0) {
        left = minutes * 60;
        refresh();
      }
      paint();
    }, 1000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) refresh();
    });
    const copied = document.getElementById("rotatingCopied");
    if (copyButton) {
      copyButton.addEventListener("click", () => {
        if (!copied) return;
        copied.hidden = false;
        setTimeout(() => {
          copied.hidden = true;
        }, 1800);
      });
    }
  }

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
