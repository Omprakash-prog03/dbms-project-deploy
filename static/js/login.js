const loginForm = document.getElementById("loginForm");
const loginButton = document.getElementById("submitBtn");
const errorMessage = document.getElementById("loginError");
const username = document.getElementById("username");
const password = document.getElementById("password");
let busy = false;
loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (busy) return;
  busy = true;
  loginButton.disabled = true;
  errorMessage.hidden = true;
  loginButton.querySelector("span").textContent = "Opening your workspace…";
  document
    .querySelectorAll("[data-demo]")
    .forEach((button) => (button.disabled = true));
  try {
    const data = await apiRequest("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value,
      }),
    });
    location.assign(data.redirect);
  } catch (error) {
    errorMessage.textContent = error.message;
    errorMessage.hidden = false;
    loginButton.disabled = false;
    loginButton.querySelector("span").textContent = "Step into your workspace";
    document
      .querySelectorAll("[data-demo]")
      .forEach((button) => (button.disabled = false));
    busy = false;
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
