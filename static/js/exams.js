document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("examForm");
  if (!form) return;
  const error = document.getElementById("examFormError");
  const save = document.getElementById("saveExamBtn");
  document.getElementById("addExamBtn").addEventListener("click", () => {
    form.reset();
    error.hidden = true;
    openModal("examModal");
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (save.disabled) return;
    save.disabled = true;
    error.hidden = true;
    const data = Object.fromEntries(new FormData(form));
    try {
      const response = await apiRequest("/api/exams/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      showToast(response.message);
      closeModal("examModal");
      location.assign(
        `/results?offering_id=${encodeURIComponent(data.offering_id)}&exam_id=${response.exam_id}`,
      );
    } catch (problem) {
      error.textContent = problem.message;
      error.hidden = false;
    } finally {
      save.disabled = false;
    }
  });
});
