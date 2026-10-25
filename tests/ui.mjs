// UI smoke/regression tests against a locally running demo. Run: npm run test:ui
// TEST_BASE_URL may point at a separate seeded test server; production is not recommended.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { launchBrowser } from "../scripts/browser.mjs";
const base = process.env.TEST_BASE_URL || "http://127.0.0.1:5000";
const browser = await launchBrowser();
const errors = [];
let context;
try {
  context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 500)
      errors.push(`${response.status()} ${response.url()}`);
  });
  const visit = async (path) => {
    const response = await page.goto(base + path);
    assert.equal(response.status(), 200, path);
    assert.ok(
      (await page.title()).includes("NIST University Portal Management"),
      `Portal title at ${path}`,
    );
  };
  const noOverflow = async () =>
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      `Horizontal page overflow at ${page.url()}`,
    );
  const audit = async () => {
    if (!(await page.evaluate(() => Boolean(window.axe)))) {
      await page.addScriptTag({ path: "node_modules/axe-core/axe.min.js" });
    }
    const issues = await page.evaluate(async () =>
      (
        await axe.run({
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
        })
      ).violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => n.target),
      })),
    );
    assert.deepEqual(issues, [], `${page.url()} accessibility violations`);
  };
  await visit("/login");
  await page.getByLabel("Username or roll number").fill("admin");
  await page.getByLabel("Password", { exact: true }).fill("admin123");
  await page.getByRole("button", { name: "Step into your workspace" }).click();
  await page.waitForURL("**/dashboard");
  await page.waitForSelector("#activityChart svg");
  assert.equal(await page.locator(".module-card:visible").count(), 6);
  await page.getByRole("tab", { name: /People/ }).click();
  assert.equal(await page.locator(".module-card:visible").count(), 3);
  await page.getByRole("tab", { name: /Academics/ }).click();
  assert.equal(await page.locator(".module-card:visible").count(), 2);
  await page.getByRole("tab", { name: /For you/ }).click();
  if (await page.locator(".approve-btn").count()) {
    await page.locator(".approve-btn").first().click();
    await page.waitForSelector("#confirm-dob");
    await audit();
    assert.ok(
      await page.getByLabel("Applicant date of birth (age 15+) *").isVisible(),
    );
    await page
      .getByRole("button", { name: "Approve application", exact: true })
      .click();
    assert.ok(await page.locator("#confirmModal").isVisible());
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    assert.ok((await page.locator("#confirmModal").count()) === 0);
  }

  await page.selectOption("#chartYear", "2025");
  await page.waitForFunction(() =>
    document
      .getElementById("activityChart")
      .getAttribute("aria-label")
      .includes("2025"),
  );
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .click();
  assert.ok(await page.locator("#notificationsPanel").isVisible());
  await page.keyboard.press("Escape");
  assert.ok(await page.locator("#notificationsPanel").isHidden());
  await page.keyboard.press("Control+k");
  await page.locator("#globalSearchInput").fill("Aarav Sharma");
  await page.waitForSelector(".command-result");
  assert.match(
    await page.locator(".command-result").first().innerText(),
    /Aarav Sharma/,
  );
  await page.locator(".command-result").first().click();
  await page.waitForURL("**/students/1");
  await visit("/students");
  await page.getByRole("button", { name: "Show SQL", exact: true }).click();
  await page.waitForSelector("#sqlModal.active");
  assert.match(await page.locator("#sqlModalContent").innerText(), /SELECT/);
  await page.keyboard.press("Escape");
  assert.ok(await page.locator("#sqlModal").isHidden());
  await page.getByRole("button", { name: "Add student", exact: true }).click();
  assert.ok(await page.locator("#studentModal").isVisible());
  // Staff choose the student's portal password; it is never generated silently.
  assert.ok(await page.locator("#studentPassword").isVisible());
  await audit();
  await page.keyboard.press("Escape");
  await page.locator(".edit-student").first().click();
  assert.ok(await page.locator("#dob").inputValue());
  assert.ok(await page.locator("#address").inputValue());
  assert.ok(await page.locator("#studentPasswordGroup").isHidden());
  await page.keyboard.press("Escape");
  await page
    .getByLabel("Search students", { exact: true })
    .fill("Aarav Sharma");
  await page.getByRole("button", { name: "Apply", exact: true }).click();
  await page.waitForURL("**/students?**");
  assert.equal(await page.locator(".sims-table tbody tr").count(), 1);
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export filtered CSV" }).click();
  const download = await downloadEvent;
  // Campus and student PDFs download from live records.
  await visit("/reports");
  let pdfEvent = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download campus PDF" }).click();
  let pdf = await pdfEvent;
  let bytes = await fs.readFile(await pdf.path());
  assert.equal(bytes.subarray(0, 5).toString(), "%PDF-");
  assert.ok(bytes.length > 2000, "campus PDF size");
  assert.equal(pdf.suggestedFilename(), "nist-campus-report.pdf");

  await visit("/students/1");
  pdfEvent = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download report PDF" }).click();
  pdf = await pdfEvent;
  bytes = await fs.readFile(await pdf.path());
  assert.equal(bytes.subarray(0, 5).toString(), "%PDF-");
  assert.ok(bytes.length > 2000, "student PDF size");
  assert.match(pdf.suggestedFilename(), /^nist-student-.*\.pdf$/);
  assert.equal(download.suggestedFilename(), "hogwards_students_export.csv");
  const csv = await fs.readFile(await download.path(), "utf8");
  assert.match(csv, /Aarav/);
  assert.equal(csv.trim().split("\n").length, 2);

  // A private, unseeded installation needs these creation screens.
  for (const [path, button, modal, heading] of [
    ["/departments", "Add department", "#departmentModal", "Add a department"],
    ["/admissions", "New application", "#applicationModal", "A new beginning"],
    ["/results", "Add examination", "#examModal", "Add an examination"],
  ]) {
    await visit(path);
    await page.getByRole("button", { name: button, exact: true }).click();
    assert.ok(await page.locator(modal).isVisible());
    assert.ok(
      await page
        .getByRole("heading", { name: heading, exact: true })
        .isVisible(),
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await noOverflow();
    await audit();
    await page.keyboard.press("Escape");
    assert.ok(await page.locator(modal).isHidden());
    await page.setViewportSize({ width: 1440, height: 1000 });
  }

  await fs.mkdir(".artifacts", { recursive: true });
  for (const path of [
    "/dashboard",
    "/students",
    "/students/1",
    "/faculty",
    "/departments",
    "/courses",
    "/offerings",
    "/enrollments",
    "/attendance",
    "/results",
    "/fees",
    "/admissions",
    "/insights",
    "/reports",
    "/raw-data",
    "/raw-data?table=student",
  ]) {
    await visit(path);
    await noOverflow();
    await page.setViewportSize({ width: 390, height: 844 });
    await noOverflow();
    if (path === "/dashboard") {
      await page.waitForSelector("#activityChart svg");
      await page.screenshot({
        path: ".artifacts/dashboard-mobile.png",
        fullPage: true,
      });
      await page.getByRole("button", { name: "Open navigation" }).click();
      assert.equal(
        await page
          .getByRole("button", { name: "Open navigation" })
          .getAttribute("aria-expanded"),
        "true",
      );
      await page.keyboard.press("Escape");
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
  }
  await visit("/dashboard");
  await page.waitForSelector("#activityChart svg");
  await page.screenshot({
    path: ".artifacts/dashboard-desktop.png",
    fullPage: true,
  });
  await visit("/students");
  await page.screenshot({
    path: ".artifacts/students-desktop.png",
    fullPage: true,
  });

  // Audit both responsive layouts, in addition to the actual dialogs above.
  for (const path of ["/dashboard", "/students"]) {
    await visit(path);
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await audit();
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.waitForURL("**/login");
  for (const [role, destination] of [
    ["faculty", "/dashboard"],
    ["student", "/students/1"],
  ]) {
    await page.getByLabel("Username or roll number").fill(role);
    await page.getByLabel("Password", { exact: true }).fill(role + "123");
    await page
      .getByRole("button", { name: "Step into your workspace" })
      .click();
    await page.waitForURL("**" + destination);
    assert.equal(
      await page
        .getByRole("link", { name: "Fees & payments", exact: true })
        .count(),
      0,
    );
    if (role === "faculty") {
      // Faculty must be able to run roll-call for their own class. This also
      // guards the shared fetch wrapper that attaches the CSRF token.
      await visit("/attendance");
      await page.waitForSelector("#rosterTable");
      assert.ok(
        (await page
          .locator("#rosterTable tbody tr[data-enrollment-id]")
          .count()) > 0,
        "faculty should have a class to mark",
      );
      await page.getByRole("button", { name: "Mark All Present" }).click();
      const saveEvent = page.waitForResponse((response) =>
        response.url().endsWith("/api/attendance/mark"),
      );
      await page.getByRole("button", { name: "Save Roll-Call" }).click();
      const saved = await saveEvent;
      assert.equal(saved.status(), 200, "faculty roll-call save");
      assert.equal((await saved.json()).success, true);
      await page.waitForLoadState("networkidle");
    }
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await page.waitForURL("**/login");
  }
  await audit();
  await page.screenshot({
    path: ".artifacts/login-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow();
  await audit();
  await page.screenshot({
    path: ".artifacts/login-mobile.png",
    fullPage: true,
  });
  if (process.env.TEST_EMBEDDED === "true") {
    const embeddedPage = await context.newPage();
    try {
      await embeddedPage.setViewportSize({ width: 1440, height: 1000 });
      embeddedPage.on("pageerror", (error) => errors.push(error.message));
      // Emulate two separate HTTPS sites entirely locally; no external DNS/TLS
      // service is needed. The browser still applies its real cookie policies.
      await embeddedPage.route(
        "https://campus-embedded.test/**",
        async (route) => {
          const url = new URL(route.request().url());
          const requestHeaders = await route.request().allHeaders();
          const response = await route.fetch({
            url: base + url.pathname + url.search,
            // Forward only the real browser cookie, never the API client's jar.
            headers: { ...requestHeaders, cookie: requestHeaders.cookie || "" },
            maxRedirects: 0,
          });
          if (
            [302, 303].includes(response.status()) &&
            response.headers().location
          ) {
            // Mocked redirects are not rerouted by Playwright. Preserve Set-Cookie
            // and issue the equivalent fresh GET without resolving the test host.
            const headers = Object.fromEntries(
              Object.entries(response.headers()).filter(
                ([name]) =>
                  ![
                    "location",
                    "content-length",
                    "content-encoding",
                    "content-type",
                  ].includes(name),
              ),
            );
            await route.fulfill({
              status: 200,
              headers: { ...headers, "content-type": "text/html" },
              body: `<!doctype html><script>location.replace(${JSON.stringify(response.headers().location)})</script>`,
            });
          } else {
            await route.fulfill({ response });
          }
        },
      );
      await embeddedPage.route("https://preview-frame.test/**", (route) =>
        route.fulfill({
          contentType: "text/html",
          body: '<iframe title="Campus preview" src="https://campus-embedded.test/login" style="width:1200px;height:900px"></iframe>',
        }),
      );
      await embeddedPage.goto("https://preview-frame.test/");
      const frame = embeddedPage.frameLocator("iframe");
      await frame.getByLabel("Username or roll number").fill("admin");
      await frame.getByLabel("Password", { exact: true }).fill("admin123");
      const loginResponse = embeddedPage.waitForResponse((response) =>
        response.url().endsWith("/api/auth/login"),
      );
      await frame
        .getByRole("button", { name: "Step into your workspace" })
        .click();
      assert.equal(
        (await loginResponse).status(),
        200,
        "Embedded preview login",
      );
      await frame.locator(".module-card").first().waitFor();
      assert.equal(await frame.locator(".module-card").count(), 6);
      await frame
        .getByRole("button", { name: "Sign out", exact: true })
        .click();
      await frame.getByLabel("Username or roll number").waitFor();
    } finally {
      await embeddedPage.close();
    }
  }
  assert.deepEqual(errors, [], "Browser/runtime errors");
  console.log(
    `${process.env.TEST_EMBEDDED === "true" ? "PASS: HTTPS cross-site iframe login/logout. " : ""}PASS: login/logout (3 roles), dashboard filters, chart year, notifications, search, SQL inspector, student dialogs, faculty roll-call save, filtered CSV, campus/student PDFs, 16 routes at desktop/mobile, keyboard navigation, accessibility.`,
  );
} finally {
  await context?.close();
  await browser.close();
}
