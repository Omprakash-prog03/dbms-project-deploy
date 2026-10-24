document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("departmentForm");
  if (!form) return;
  const error = document.getElementById("departmentFormError");
  const save = document.getElementById("saveDepartmentBtn");
  function openDepartment(department = null) {
    form.reset();
    error.hidden = true;
    form.elements.dept_id.value = department?.dept_id || "";
    for (const field of [
      "dept_code",
      "dept_name",
      "established_year",
      "hod_faculty_id",
    ]) {
      if (department) form.elements[field].value = department[field] ?? "";
    }
    document.getElementById("departmentHeadGroup").hidden = !department;
    document
      .querySelectorAll("#departmentHead option[data-dept-id]")
      .forEach((option) => {
        option.hidden =
          !department || Number(option.dataset.deptId) !== department.dept_id;
        option.disabled = option.hidden;
      });
    document.getElementById("departmentModalTitle").textContent = department
      ? "Update your department"
      : "Add a department";
    openModal("departmentModal");
  }
  document
    .getElementById("addDepartmentBtn")
    .addEventListener("click", () => openDepartment());
  document
    .querySelectorAll(".edit-department")
    .forEach((button) =>
      button.addEventListener("click", () =>
        openDepartment(JSON.parse(button.dataset.department)),
      ),
    );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (save.disabled) return;
    const data = Object.fromEntries(new FormData(form));
    const id = data.dept_id;
    delete data.dept_id;
    save.disabled = true;
    error.hidden = true;
    try {
      const response = await apiRequest(
        id ? `/api/departments/update/${id}` : "/api/departments/create",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        },
      );
      showToast(response.message);
      closeModal("departmentModal");
      location.reload();
    } catch (problem) {
      error.textContent = problem.message;
      error.hidden = false;
    } finally {
      save.disabled = false;
    }
  });
});
