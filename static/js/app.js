/* Shared UI. All requests stay on this origin, including proxied previews. */
(() => {
  const originalFetch = window.fetch.bind(window);
  window.fetch = (resource, init = {}) => {
    const url = new URL(
      resource instanceof Request ? resource.url : resource,
      location.href,
    );
    const method = (
      init.method || (resource instanceof Request ? resource.method : "GET")
    ).toUpperCase();
    if (
      url.origin === location.origin &&
      !["GET", "HEAD", "OPTIONS"].includes(method)
    ) {
      const headers = new Headers(
        init.headers ||
          (resource instanceof Request ? resource.headers : undefined),
      );
      const token = document.querySelector('meta[name="csrf-token"]')?.content;
      if (token) headers.set("X-CSRF-Token", token);
      init = { ...init, headers };
    }
    return originalFetch(resource, init);
  };
})();

// Page scripts still call fetch() directly, so attach the CSRF token here for
// every same-origin mutation. Without this, POSTs fail with "session expired".
const nativeFetch = window.fetch.bind(window);
window.fetch = function csrfFetch(input, init = {}) {
  const request = new Request(input, init);
  const method = (request.method || "GET").toUpperCase();
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  if (
    token &&
    !["GET", "HEAD", "OPTIONS"].includes(method) &&
    !request.headers.has("X-CSRF-Token") &&
    new URL(request.url, location.href).origin === location.origin
  ) {
    request.headers.set("X-CSRF-Token", token);
  }
  return nativeFetch(request);
};

window.apiRequest = async function (url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("Something went wrong. Please refresh and try again.");
  }
  if (!response.ok || data.success === false)
    throw new Error(data.message || "This action could not be completed.");
  return data;
};
window.escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
window.showToast = function (message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast${type === "error" ? " error" : ""}`;
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.textContent = message;
  container.append(toast);
  setTimeout(() => toast.remove(), 5500);
};

const modalFocus = new WeakMap();
const visibleModals = () =>
  [...document.querySelectorAll(".modal-overlay, .sql-modal-backdrop")].filter(
    (m) => getComputedStyle(m).display !== "none",
  );
const focusable = (modal) =>
  [
    ...modal.querySelectorAll(
      'button, a[href], input:not([type="hidden"]), select, textarea, [tabindex="0"]',
    ),
  ].filter((e) => !e.disabled && e.getClientRects().length);
window.openModal = function (id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modalFocus.set(modal, document.activeElement);
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  const heading = modal.querySelector("h3");
  if (heading && !modal.hasAttribute("aria-labelledby")) {
    heading.id ||= `${id}Heading`;
    modal.setAttribute("aria-labelledby", heading.id);
  }
  modal.classList.add("active");
  modal.style.display = "flex";
  modal.tabIndex = -1;
  document.body.classList.add("modal-open");
  requestAnimationFrame(() =>
    (
      modal.querySelector('input:not([type="hidden"]):not([disabled])') ||
      focusable(modal)[0] ||
      modal
    ).focus(),
  );
};
window.closeModal = function (id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.remove("active");
  modal.style.display = "none";
  if (!visibleModals().length) document.body.classList.remove("modal-open");
  modalFocus.get(modal)?.focus();
  modal.dispatchEvent(new Event("modalclosed"));
};

window.confirmAction = ({
  title,
  message,
  confirmLabel = "Confirm",
  danger = false,
  fields = [],
}) =>
  new Promise((resolve) => {
    let modal = document.getElementById("confirmModal");
    if (modal) modal.remove();
    modal = document.createElement("div");
    modal.id = "confirmModal";
    modal.className = "modal-overlay";
    modal.setAttribute("aria-labelledby", "confirmTitle");
    modal.innerHTML =
      '<div class="modal-card" style="max-width:440px"><div class="modal-header"><h3 id="confirmTitle"></h3><button class="close-modal-btn" aria-label="Close">×</button></div><p class="confirm-message" style="font-size:12px;line-height:1.8;color:var(--text-muted)"></p><div class="form-actions"><button class="btn-secondary-pill cancel-confirm">Cancel</button><button class="btn-primary-pill accept-confirm"></button></div></div>';
    modal.querySelector("h3").textContent = title;
    modal.querySelector(".confirm-message").textContent = message;
    const accept = modal.querySelector(".accept-confirm");
    accept.textContent = confirmLabel;
    if (danger) {
      accept.style.background = "#efb2ba";
      accept.style.color = "#3b1b24";
    }
    const controls = [];
    if (fields.length) {
      const fieldContainer = document.createElement("div");
      fieldContainer.className = "form-grid";
      fieldContainer.style.marginTop = "20px";
      fields.forEach((field) => {
        const group = document.createElement("div");
        group.className = "form-group full-width";
        const label = document.createElement("label");
        label.textContent = field.label;
        label.htmlFor = `confirm-${field.name}`;
        const input = document.createElement("input");
        input.className = "form-input";
        input.id = label.htmlFor;
        input.name = field.name;
        input.type = field.type || "text";
        input.required = Boolean(field.required);
        input.autocomplete = "off";
        if (field.max) input.max = field.max;
        group.append(label, input);
        fieldContainer.append(group);
        controls.push(input);
      });
      modal.querySelector(".form-actions").before(fieldContainer);
    }
    let accepted = false;
    accept.addEventListener("click", () => {
      if (controls.some((control) => !control.reportValidity())) return;
      accepted = fields.length
        ? Object.fromEntries(
            controls.map((control) => [control.name, control.value]),
          )
        : true;
      closeModal(modal.id);
    });
    modal
      .querySelectorAll(".cancel-confirm,.close-modal-btn")
      .forEach((b) => b.addEventListener("click", () => closeModal(modal.id)));
    modal.addEventListener(
      "modalclosed",
      () => {
        resolve(accepted);
        modal.remove();
      },
      { once: true },
    );
    document.body.append(modal);
    openModal(modal.id);
  });

document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("click", (event) => {
    if (event.target.matches(".modal-overlay,.sql-modal-backdrop"))
      closeModal(event.target.id);
  });
  document.addEventListener("keydown", (event) => {
    const modal = visibleModals().at(-1);
    if (event.key === "Escape") {
      if (modal) closeModal(modal.id);
      closeSidebar();
      closeNotifications();
    }
    if (event.key === "Tab" && modal) {
      const elements = focusable(modal);
      if (!elements.length) {
        event.preventDefault();
        modal.focus();
        return;
      }
      if (
        event.shiftKey &&
        (document.activeElement === elements[0] ||
          !modal.contains(document.activeElement))
      ) {
        event.preventDefault();
        elements.at(-1).focus();
      } else if (
        !event.shiftKey &&
        document.activeElement === elements.at(-1)
      ) {
        event.preventDefault();
        elements[0].focus();
      }
    }
    if (
      (event.ctrlKey || event.metaKey) &&
      event.key.toLowerCase() === "k" &&
      document.getElementById("searchModal")
    ) {
      event.preventDefault();
      openSearch();
    }
  });

  const menuButton = document.querySelector(".mobile-menu");
  const sidebar = document.getElementById("sidebar");
  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    menuButton?.setAttribute("aria-expanded", "false");
    if (sidebar && innerWidth <= 760) sidebar.inert = true;
  }
  function updateSidebar() {
    if (sidebar)
      sidebar.inert =
        innerWidth <= 760 && !document.body.classList.contains("sidebar-open");
  }
  menuButton?.addEventListener("click", () => {
    const open = !document.body.classList.contains("sidebar-open");
    document.body.classList.toggle("sidebar-open", open);
    menuButton.setAttribute("aria-expanded", String(open));
    updateSidebar();
    if (open) sidebar.querySelector("a")?.focus();
  });
  document.querySelector(".sidebar-scrim")?.addEventListener("click", () => {
    closeSidebar();
    menuButton?.focus();
  });
  window.addEventListener("resize", updateSidebar);
  updateSidebar();

  const notifications = document.getElementById("notificationsPanel");
  const notificationsButton = document.getElementById("notificationsBtn");
  function closeNotifications() {
    if (notifications) notifications.hidden = true;
    notificationsButton?.setAttribute("aria-expanded", "false");
  }
  notificationsButton?.addEventListener("click", () => {
    notifications.hidden = !notifications.hidden;
    notificationsButton.setAttribute(
      "aria-expanded",
      String(!notifications.hidden),
    );
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".notification-wrap")) closeNotifications();
  });

  const input = document.getElementById("globalSearchInput");
  const results = document.getElementById("searchResults");
  let timer,
    controller,
    sequence = 0;
  function openSearch() {
    closeNotifications();
    closeSidebar();
    openModal("searchModal");
  }
  document
    .getElementById("globalSearchBtn")
    ?.addEventListener("click", openSearch);
  input?.addEventListener("input", () => {
    clearTimeout(timer);
    controller?.abort();
    const current = ++sequence;
    const term = input.value.trim();
    results.replaceChildren();
    const note = document.createElement("p");
    note.className = "empty-note";
    note.textContent = term
      ? "Finding your focus…"
      : "Type a name, roll number, or course to get started.";
    results.append(note);
    if (!term) return;
    timer = setTimeout(async () => {
      controller = new AbortController();
      try {
        const data = await apiRequest(
          `/api/search?q=${encodeURIComponent(term)}`,
          { signal: controller.signal },
        );
        if (current !== sequence) return;
        results.replaceChildren();
        if (!data.results.length) {
          note.textContent =
            "No matches yet. Try a name, roll number, or course code.";
          results.append(note);
        }
        data.results.forEach((item) => {
          const link = document.createElement("a");
          link.className = "command-result";
          link.href = item.url;
          const details = document.createElement("div");
          const title = document.createElement("strong");
          title.textContent = item.title;
          const subtitle = document.createElement("span");
          subtitle.textContent = item.subtitle;
          details.append(title, subtitle);
          const kind = document.createElement("span");
          kind.className = "result-kind";
          kind.textContent = item.kind;
          link.append(details, kind);
          results.append(link);
        });
      } catch (error) {
        if (error.name !== "AbortError" && current === sequence) {
          note.textContent = error.message;
          results.replaceChildren(note);
        }
      }
    }, 220);
  });
  document.getElementById("searchModal")?.addEventListener("keydown", (e) => {
    const links = [...results.querySelectorAll("a")];
    if (!links.length) return;
    const index = links.indexOf(document.activeElement);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      links[(index + 1) % links.length].focus();
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (index <= 0) input.focus();
      else links[index - 1].focus();
    }
    if (e.key === "Enter" && document.activeElement === input) {
      e.preventDefault();
      links[0].click();
    }
  });

  // Associate legacy form labels and controls; all new forms have explicit labels.
  document.querySelectorAll(".form-group").forEach((group, index) => {
    const label = group.querySelector("label"),
      control = group.querySelector("input:not([type=hidden]),select,textarea");
    if (label && control) {
      control.id ||= `field-${index}`;
      label.htmlFor = control.id;
    }
  });
  document
    .querySelectorAll("input:not([type=hidden]),select,textarea")
    .forEach((control, index) => {
      if (control.labels?.length || control.hasAttribute("aria-label")) return;
      const label = control.previousElementSibling;
      if (label?.tagName === "LABEL") {
        control.id ||= `control-${index}`;
        label.htmlFor = control.id;
      } else if (control.name)
        control.setAttribute("aria-label", control.name.replaceAll("_", " "));
    });
  document
    .querySelectorAll(".sql-close-btn,.close-modal-btn")
    .forEach((button) => {
      if (!button.getAttribute("aria-label"))
        button.setAttribute("aria-label", "Close dialog");
    });
});
