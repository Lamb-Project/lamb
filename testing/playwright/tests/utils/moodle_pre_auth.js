const { chromium } = require("@playwright/test");
const fs = require("fs");
const path = require("path");
require("dotenv").config({
  path: path.join(__dirname, "../..", ".env"),
  quiet: true,
});

const MOODLE_URL = process.env.MOODLE_URL;
const MOODLE_LOGIN = process.env.MOODLE_LOGIN;
const MOODLE_PASSWORD = process.env.MOODLE_PASSWORD;
const authDir = path.join(__dirname, "..", ".auth");
const statePath = path.join(authDir, "moodle-state.json");

async function ensureMoodleAuth() {
  if (!MOODLE_URL || !MOODLE_LOGIN || !MOODLE_PASSWORD) {
    throw new Error(
      "MOODLE_URL, MOODLE_LOGIN and MOODLE_PASSWORD must be set in tests/.env"
    );
  }

  fs.mkdirSync(authDir, { recursive: true });

  if (fs.existsSync(statePath) && !process.env.FORCE_RELOGIN) {
    return;
  }

  const browser = await chromium.launch({ headless: !!process.env.CI });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Prefer the explicit Moodle login page (common path) to make selectors reliable
  const loginUrl = MOODLE_URL.endsWith("/")
    ? `${MOODLE_URL}login/index.php`
    : `${MOODLE_URL}/login/index.php`;
  await page.goto(loginUrl);
  await page.waitForLoadState("domcontentloaded");

  // If login page didn't render (no username field), try clicking "Log in" on homepage
  if (!(await page.$("#username"))) {
    await page.goto(MOODLE_URL);
    await page.waitForLoadState("domcontentloaded");
    const loginLink =
      (await page.$("a:has-text('Log in')")) ||
      (await page.$("a:has-text('Log In')"));
    if (loginLink) {
      await loginLink.click().catch(() => {});
      await page.waitForLoadState("domcontentloaded").catch(() => {});
    }
  }

  // Try several common selectors for username/password (broader set)
  const usernameSelectors = [
    "#username",
    'input[name="username"]',
    "input[id*=user]",
    "input[placeholder*='Username']",
    "input[placeholder*='username']",
  ];
  const passwordSelectors = [
    "#password",
    'input[name="password"]',
    'input[type="password"]',
    "input[placeholder*='Password']",
    "input[placeholder*='password']",
  ];

  let usernameSel = null;
  for (const sel of usernameSelectors) {
    if (await page.$(sel)) {
      usernameSel = sel;
      break;
    }
  }

  let passwordSel = null;
  for (const sel of passwordSelectors) {
    if (await page.$(sel)) {
      passwordSel = sel;
      break;
    }
  }

  if (!usernameSel || !passwordSel) {
    // Fallback: try to heuristically find username/password among inputs
    const inputs = await page.$$("input");
    let heuristicUser = null;
    let heuristicPass = null;
    for (const input of inputs) {
      const type = (await input.getAttribute("type")) || "";
      const name = (await input.getAttribute("name")) || "";
      const id = (await input.getAttribute("id")) || "";
      const placeholder = (await input.getAttribute("placeholder")) || "";

      if (
        !heuristicUser &&
        /user|email|login/i.test(name + id + placeholder) &&
        type !== "password"
      ) {
        heuristicUser = input;
      }
      if (!heuristicPass && type === "password") {
        heuristicPass = input;
      }
    }

    if (heuristicUser && heuristicPass) {
      await heuristicUser.fill(MOODLE_LOGIN);
      await heuristicPass.fill(MOODLE_PASSWORD);
    } else {
      // Dump page content for debugging
      const debugPath = path.join(authDir, "moodle-login-debug.html");
      const html = await page.content();
      try {
        fs.writeFileSync(debugPath, html);
      } catch (e) {
        /* ignore */
      }
      await browser.close();
      throw new Error(
        `Could not find Moodle login fields (username/password). Page snapshot saved to ${debugPath}`
      );
    }
  } else {
    await page.fill(usernameSel, MOODLE_LOGIN);
    await page.fill(passwordSel, MOODLE_PASSWORD);
  }

  // Try common login button selectors
  const buttonSelectors = [
    "#loginbtn",
    'button[type="submit"]',
    'button:has-text("Log in")',
    'button:has-text("Login")',
  ];
  let clicked = false;
  for (const sel of buttonSelectors) {
    const btn = await page.$(sel);
    if (btn) {
      await Promise.all([
        page.waitForLoadState("networkidle").catch(() => {}),
        btn.click(),
      ]);
      clicked = true;
      break;
    }
  }

  if (!clicked) {
    // Fallback: press Enter in the password field
    await page.keyboard.press("Enter");
    await page.waitForLoadState("networkidle").catch(() => {});
  }

  // Wait briefly for login to complete and verify by checking presence of logout link or user menu
  const successChecks = [
    "a[href*='logout']",
    "#action-menu-toggle",
    "a:has-text('Log out')",
    "a:has-text('Sign out')",
  ];
  let success = false;
  for (const sel of successChecks) {
    try {
      await page.waitForSelector(sel, { timeout: 5000 });
      success = true;
      break;
    } catch (e) {
      // continue
    }
  }

  // If success check didn't pass, still attempt to persist storage; sometimes Moodle hides the menu
  const storage = await context.storageState();
  fs.writeFileSync(statePath, JSON.stringify(storage, null, 2));

  await browser.close();

  if (!success) {
    // Not a fatal error anymore because we saved storage, but warn
    console.warn(
      "Login may have failed (logout/menu not found). Storage state saved anyway."
    );
  }
}

module.exports = { ensureMoodleAuth };
