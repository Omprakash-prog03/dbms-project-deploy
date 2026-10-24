// Portable headless browser for the artwork builder and local UI regression tests.
import path from "node:path";
import { chromium as playwright } from "playwright-core";
import chromium, { inflate, setupLambdaEnvironment } from "@sparticuz/chromium";
export async function launchBrowser() {
  await inflate(
    path.resolve("node_modules/@sparticuz/chromium/bin/al2023.tar.br"),
  );
  setupLambdaEnvironment("/tmp/al2023/lib");
  return playwright.launch({
    executablePath:
      process.env.CHROMIUM_PATH || (await chromium.executablePath()),
    // Use real browser security behavior and avoid single-process context crashes.
    args: chromium.args.filter(
      (arg) =>
        ![
          "--single-process",
          "--disable-web-security",
          "--allow-running-insecure-content",
        ].includes(arg),
    ),
    headless: true,
  });
}
