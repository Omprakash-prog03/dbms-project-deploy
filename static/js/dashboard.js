document.addEventListener("DOMContentLoaded", () => {
  const tabs = [...document.querySelectorAll(".workspace-tab")];
  const cards = [...document.querySelectorAll(".module-card")];
  tabs.forEach((tab, index) => {
    const category = tab.dataset.category;
    tab.querySelector("span").textContent =
      category === "all"
        ? cards.length
        : cards.filter((card) =>
            card.dataset.categories.split(" ").includes(category),
          ).length;
    tab.addEventListener("click", () => {
      tabs.forEach((t) => {
        t.setAttribute("aria-selected", String(t === tab));
        t.tabIndex = t === tab ? 0 : -1;
      });
      document
        .getElementById("moduleGrid")
        .setAttribute("aria-labelledby", tab.id);
      cards.forEach((card) => {
        card.hidden =
          category !== "all" &&
          !card.dataset.categories.split(" ").includes(category);
      });
    });
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      event.preventDefault();
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? tabs.length - 1
            : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
              tabs.length;
      tabs[next].click();
      tabs[next].focus();
    });
  });
  const yearSelect = document.getElementById("chartYear");
  const container = document.getElementById("activityChart");
  let sequence = 0;
  function drawChart(data) {
    const ns = "http://www.w3.org/2000/svg";
    const el = (name, attrs = {}, text) => {
      const node = document.createElementNS(ns, name);
      for (const [key, value] of Object.entries(attrs))
        node.setAttribute(key, value);
      if (text !== undefined) node.textContent = text;
      return node;
    };
    const svg = el("svg", {
      viewBox: "0 0 550 158",
      preserveAspectRatio: "none",
      "aria-hidden": "true",
    });
    const maximum = Math.max(...data.admissions, ...data.enrollments, 1);
    const step = Math.max(
      1,
      Math.ceil(maximum / 4 / (maximum > 100 ? 50 : 5)) *
        (maximum > 100 ? 50 : 5),
    );
    const max = step * 4;
    for (let i = 0; i <= 4; i++) {
      const y = 130 - i * 29;
      svg.append(
        el("line", { x1: 32, x2: 546, y1: y, y2: y, class: "chart-gridline" }),
      );
      svg.append(
        el("text", { x: 23, y: y + 3, "text-anchor": "end" }, String(step * i)),
      );
    }
    const chartWidth = 512,
      groupWidth = chartWidth / 12;
    data.labels.forEach((month, index) => {
      const x = 34 + index * groupWidth + groupWidth / 2;
      for (const [key, color, offset, label] of [
        ["admissions", "#c4afdF", -8, "admissions"],
        ["enrollments", "#7f9f9f", 3, "enrollments"],
      ]) {
        const value = Number(data[key][index]);
        const height = (value / max) * 116;
        const rect = el("rect", {
          x: x + offset,
          y: 130 - height,
          width: 7,
          height: height,
          rx: 2,
          fill: color,
          class: "chart-bar",
        });
        rect.append(
          el("title", {}, `${month} ${data.year}: ${value} ${label}`),
        );
        svg.append(rect);
      }
      svg.append(el("text", { x, y: 151, "text-anchor": "middle" }, month));
    });
    const admissions = data.admissions.reduce((a, b) => a + b, 0),
      enrollments = data.enrollments.reduce((a, b) => a + b, 0);
    container.replaceChildren(svg);
    container.setAttribute(
      "aria-label",
      `Monthly campus activity for ${data.year}: ${admissions} admissions and ${enrollments} enrollments. ${data.labels.map((m, i) => `${m}: ${data.admissions[i]} admissions, ${data.enrollments[i]} enrollments`).join("; ")}.`,
    );
    document.getElementById("chartTotal").textContent =
      `${(admissions + enrollments).toLocaleString()} milestones`;
    const caption = document.getElementById("chartCaption");
    caption.textContent =
      admissions + enrollments
        ? `${admissions.toLocaleString()} new students. ${enrollments.toLocaleString()} steps forward. One connected campus.`
        : `A blank page, ready for new beginnings. No activity in ${data.year} yet.`;
  }
  async function loadChart() {
    const current = ++sequence;
    container.setAttribute("aria-busy", "true");
    try {
      const data = await apiRequest(
        `/api/dashboard/chart?year=${yearSelect.value}`,
      );
      if (current === sequence) drawChart(data);
    } catch (error) {
      if (current === sequence) {
        const message = document.createElement("p");
        message.className = "empty-note";
        message.textContent = error.message;
        container.replaceChildren(message);
        document.getElementById("chartTotal").textContent = "";
      }
    } finally {
      if (current === sequence) container.setAttribute("aria-busy", "false");
    }
  }
  if (yearSelect && container) {
    yearSelect.addEventListener("change", loadChart);
    loadChart();
  }
});
