document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-admission-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.admissionAction,
        name = button.dataset.name;
      const accepted = await confirmAction({
        title:
          action === "approve"
            ? "Welcome a new beginning."
            : "Reject this application?",
        message:
          action === "approve"
            ? `Approve ${name}? This creates a student record, a unique roll number, and a portal account. Course enrollment is a separate step. Confirm their date of birth. A unique password will be generated and shown only once.`
            : `Reject ${name}'s application? It will move to the rejected list and cannot be approved from the pending queue.`,
        confirmLabel:
          action === "approve" ? "Approve application" : "Reject application",
        danger: action !== "approve",
        fields:
          action === "approve"
            ? [
                {
                  name: "dob",
                  label: "Applicant date of birth (age 15+) *",
                  type: "date",
                  required: true,
                  max: new Date().toISOString().slice(0, 10),
                },
                { name: "address", label: "Residential address (optional)" },
              ]
            : [],
      });
      if (!accepted) return;
      const row = document.getElementById(`pending-item-${button.dataset.id}`);
      const rowButtons = [...(row?.querySelectorAll("button") || [button])];
      rowButtons.forEach((b) => (b.disabled = true));
      try {
        const data = await apiRequest(`/api/admissions/${action}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            application_id: Number(button.dataset.id),
            ...(typeof accepted === "object" ? accepted : {}),
          }),
        });
        showToast(
          action === "approve"
            ? `Welcome aboard. Roll number ${data.roll_no} is ready.`
            : data.message,
        );
        if (action === "approve") {
          await confirmAction({
            title: "Their new chapter is ready.",
            message: `Save these login details now; the password is only shown once. Username: ${data.username}. Temporary password: ${data.temporary_password}. Share them privately with the student. An administrator can reset the password later.`,
            confirmLabel: "I have saved the details",
          });
        }
        // Refresh authoritative counters and the pending queue (including the next item).
        location.reload();
      } catch (error) {
        showToast(error.message, "error");
        rowButtons.forEach((b) => (b.disabled = false));
      }
    });
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("applicationForm");
  if (!form) return;
  const error = document.getElementById("applicationFormError");
  const save = document.getElementById("saveApplicationBtn");
  document.getElementById("addApplicationBtn").addEventListener("click", () => {
    form.reset();
    error.hidden = true;
    openModal("applicationModal");
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (save.disabled) return;
    save.disabled = true;
    error.hidden = true;
    try {
      const response = await apiRequest("/api/admissions/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      showToast(response.message);
      closeModal("applicationModal");
      location.assign("/admissions?status=Pending");
    } catch (problem) {
      error.textContent = problem.message;
      error.hidden = false;
    } finally {
      save.disabled = false;
    }
  });
});
