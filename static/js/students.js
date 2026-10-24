document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("studentForm");
  const error = document.getElementById("studentFormError");
  const saveButton = document.getElementById("saveStudentBtn");
  function openStudent(student = null) {
    form.reset();
    error.hidden = true;
    form.elements.student_id.value = student?.student_id || "";
    form.elements.roll_no.readOnly = Boolean(student);
    // Passwords are only set when creating; existing accounts are reset explicitly.
    document.getElementById("studentPasswordGroup").hidden = Boolean(student);
    form.elements.initial_password.value = "";
    if (student)
      Object.entries(student).forEach(([key, value]) => {
        if (form.elements.namedItem(key))
          form.elements.namedItem(key).value = value ?? "";
      });
    document.getElementById("studentModalTitle").textContent = student
      ? `A little update for ${student.first_name}.`
      : "Welcome a new learner.";
    openModal("studentModal");
  }
  document
    .getElementById("addStudentBtn")
    ?.addEventListener("click", () => openStudent());
  document
    .querySelectorAll(".edit-student")
    .forEach((button) =>
      button.addEventListener("click", () =>
        openStudent(JSON.parse(button.dataset.student)),
      ),
    );
  document
    .querySelectorAll(".reset-student")
    .forEach((button) =>
      button.addEventListener("click", () =>
        openPasswordResetModal(
          "student",
          button.dataset.id,
          button.dataset.name,
        ),
      ),
    );
  document.querySelectorAll(".delete-student").forEach((button) =>
    button.addEventListener("click", async () => {
      if (
        !(await confirmAction({
          title: "Remove this student?",
          message: `Remove ${button.dataset.name}? This also removes their portal access. Students with academic or payment records are protected and cannot be deleted.`,
          confirmLabel: "Remove student",
          danger: true,
        }))
      )
        return;
      button.disabled = true;
      try {
        const data = await apiRequest(
          `/api/students/delete/${button.dataset.id}`,
          { method: "POST" },
        );
        showToast(data.message);
        setTimeout(() => location.reload(), 500);
      } catch (error) {
        showToast(error.message, "error");
        button.disabled = false;
      }
    }),
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saveButton.disabled) return;
    const payload = Object.fromEntries(new FormData(form));
    const id = payload.student_id;
    delete payload.student_id;
    if (id) delete payload.initial_password;
    saveButton.disabled = true;
    error.hidden = true;
    try {
      const data = await apiRequest(
        id ? `/api/students/update/${id}` : "/api/students/create",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      showToast(data.message);
      closeModal("studentModal");
      setTimeout(() => location.reload(), 500);
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      error.scrollIntoView({ block: "nearest" });
    } finally {
      saveButton.disabled = false;
    }
  });
  if (new URLSearchParams(location.search).get("new") === "1") {
    openStudent();
    const url = new URL(location.href);
    url.searchParams.delete("new");
    history.replaceState(null, "", url);
  }
});
