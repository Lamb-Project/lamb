const { chromium } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

module.exports = async (config) => {
  const baseURL = config.projects[0]?.use?.baseURL || "http://localhost:9099/";
  const email = process.env.LOGIN_EMAIL || "admin@owi.com";
  const password = process.env.LOGIN_PASSWORD || "admin";

  const authDir = path.join(__dirname, ".auth");
  const statePath = path.join(authDir, "state.json");

  fs.mkdirSync(authDir, { recursive: true });

  // If a prior state exists, reuse it, but only if it already contains data
  // for the current baseURL origin (so we don't reuse localhost creds when
  // running tests against a different host). If it doesn't, back it up and
  // proceed to re-login.
  if (fs.existsSync(statePath) && !process.env.FORCE_RELOGIN) {
    try {
      const content = fs.readFileSync(statePath, "utf-8");
      const json = JSON.parse(content);
      const desiredOrigin = new URL(baseURL).origin;
      const hasMatchingOrigin = (json.origins || []).some((o) => {
        try {
          return new URL(o.origin).origin === desiredOrigin;
        } catch {
          return o.origin === desiredOrigin;
        }
      });

      if (hasMatchingOrigin) {
        // Found a matching origin; reuse the state and skip login.
        return;
      }

      // No matching origin found: back up existing state and proceed to re-login
      const backupPath = `${statePath}.bak.${Date.now()}`;
      fs.renameSync(statePath, backupPath);
      console.log(
        `Backed up existing state to ${backupPath} because it lacked origin ${desiredOrigin}`
      );
    } catch (err) {
      console.warn(
        "Existing state file is invalid or unreadable; proceeding to re-login.",
        err
      );
    }
  }

  const browser = await chromium.launch({ headless: !!process.env.CI });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(baseURL);
  await page.waitForLoadState("domcontentloaded");

  // If already authenticated in some environments, just persist storage.
  const existingToken = await page.evaluate(() =>
    localStorage.getItem("userToken")
  );
  if (!existingToken) {
    await page.waitForSelector("#email", { timeout: 30_000 });
    await page.fill("#email", email);
    await page.fill("#password", password);

    // Matches your current scripts: login is "form > button".
    await Promise.all([
      page.waitForLoadState("networkidle").catch(() => {}),
      page.click("form > button"),
    ]);

    // Give time for localStorage token to be set.
    await page.waitForTimeout(1500);
  }

  const tokenAfter = await page.evaluate(() =>
    localStorage.getItem("userToken")
  );
  if (!tokenAfter) {
    await browser.close();
    throw new Error(
      "Login did not produce localStorage.userToken. Check UI selectors or credentials (LOGIN_EMAIL/LOGIN_PASSWORD)."
    );
  }

  await context.storageState({ path: statePath });
  await browser.close();
};
