const loginForm = document.getElementById("loginForm");
const loginButton = document.getElementById("submitBtn");
const errorMessage = document.getElementById("loginError");
const username = document.getElementById("username");
const password = document.getElementById("password");
const accessCode = document.getElementById("accessCode");
const accessHint = document.getElementById("accessCodeHint");
const statusBox = document.getElementById("accessStatus");
const statusText = document.getElementById("accessStatusText");
let busy = false;
let pollTimer = null;

const setLabel = (text) => {
  loginButton.querySelector("span").textContent = text;
};

const resetButton = () => {
  loginButton.disabled = false;
  setLabel("Step into your workspace");
  document
    .querySelectorAll("[data-demo]")
    .forEach((button) => (button.disabled = false));
  busy = false;
};

const setStatus = (state, message) => {
  if (!statusBox) return;
  statusBox.hidden = false;
  statusBox.dataset.state = state;
  statusText.textContent = message;
};

const clearStatus = () => {
  if (statusBox) statusBox.hidden = true;
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

// While an administrator waits for the owner, keep checking so the page can
// say "your code is ready" without them refreshing anything.
const watchForOwner = () => {
  if (pollTimer) clearInterval(pollTimer);
  let ticks = 0;
  pollTimer = setInterval(async () => {
    ticks += 1;
    if (ticks > 120) {
      clearInterval(pollTimer);
      pollTimer = null;
      return;
    }
    try {
      const response = await fetch("/api/auth/access-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.value.trim() }),
      });
      const data = await response.json();
      if (!data || !data.state) return;
      if (data.state === "approved") {
        setStatus("ready", data.message);
        accessCode.focus();
        accessCode.select();
        clearInterval(pollTimer);
        pollTimer = null;
      } else if (data.state === "pending") {
        setStatus("waiting", data.message);
      } else if (["blocked", "closed", "no-key", "revoked", "expired", "used"].includes(data.state)) {
        setStatus("blocked", data.message);
      }
    } catch (error) {
      /* a failed poll is harmless; the next one retries */
    }
  }, 5000);
};

// As soon as an administrator types their name, say what will happen next —
// before they press the button and wonder why a password alone is not enough.
const checkGate = async () => {
  const value = username.value.trim();
  if (!value || busy) return;
  try {
    const response = await fetch("/api/auth/access-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: value }),
    });
    const data = await response.json();
    if (!data || !data.state) return;
    const informative = ["none", "closed", "blocked", "no-key", "pending", "approved", "used", "revoked", "expired"];
    if (informative.includes(data.state)) {
      const tones = { closed: "blocked", blocked: "blocked", "no-key": "blocked", approved: "ready" };
      setStatus(tones[data.state] || "waiting", data.message);
      if (data.state === "approved") accessCode.focus();
    }
  } catch (error) {
    /* the check is a courtesy; failures stay silent */
  }
};

username.addEventListener("blur", checkGate);

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  loginButton.disabled = true;
  errorMessage.hidden = true;
  setLabel("Opening your workspace…");
  document
    .querySelectorAll("[data-demo]")
    .forEach((button) => (button.disabled = true));
  const usernameValue = username.value.trim();
  const codeValue = (accessCode && accessCode.value.trim()) || "";
  try {
    const data = await apiRequest("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: usernameValue,
        password: password.value,
        access_code: codeValue,
      }),
    });
    clearStatus();
    location.assign(data.redirect);
  } catch (error) {
    resetButton();
    // Anything about the owner's gate belongs beside the code box, not above it.
    if (error.code === "approval_required") {
      const wrongCode = /not correct|attempt/i.test(error.message || "");
      setStatus(wrongCode ? "warn" : "waiting", error.message);
      if (accessHint && wrongCode) {
        accessHint.textContent = "Check the six digits, or ask the owner for a new code.";
      }
      password.closest(".form-group").classList.add("is-locked");
      accessCode.focus();
      accessCode.select();
      if (usernameValue) watchForOwner();
    } else if (error.code === "owner_blocked") {
      setStatus("blocked", error.message);
      if (accessHint) accessHint.textContent = error.message;
    } else {
      errorMessage.textContent = error.message;
      errorMessage.hidden = false;
    }
  }
});

document.getElementById("togglePassword").addEventListener("click", (event) => {
  const visible = password.type === "password";
  password.type = visible ? "text" : "password";
  event.currentTarget.setAttribute(
    "aria-label",
    visible ? "Hide password" : "Show password",
  );
  event.currentTarget.setAttribute("aria-pressed", String(visible));
});

document.querySelectorAll("[data-demo]").forEach((button) =>
  button.addEventListener("click", () => {
    username.value = button.dataset.demo;
    password.value = button.dataset.demo + "123";
    loginForm.requestSubmit();
  }),
);
