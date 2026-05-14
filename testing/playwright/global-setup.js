const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

module.exports = async (config) => {
  const baseURL = config.projects[0]?.use?.baseURL || 'http://localhost:5173/';
  const email = process.env.LOGIN_EMAIL || 'admin@owi.com';
  const password = process.env.LOGIN_PASSWORD || 'admin';

  // Derive the API base from the baseURL (frontend proxies /creator to the backend).
  const apiBase = baseURL.replace(/\/$/, '');

  const authDir = path.join(__dirname, '.auth');
  const statePath = path.join(authDir, 'state.json');

  fs.mkdirSync(authDir, { recursive: true });

  // If a prior state exists, reuse it. This keeps local dev fast.
  if (fs.existsSync(statePath) && !process.env.FORCE_RELOGIN) {
    return;
  }

  // Call the login API directly — avoids fighting the form's missing preventDefault().
  const formData = new URLSearchParams({ email, password });
  const resp = await fetch(`${apiBase}/creator/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData.toString(),
  });

  if (!resp.ok) {
    throw new Error(`Login API returned HTTP ${resp.status}`);
  }

  const json = await resp.json();
  if (!json.success || !json.data?.token) {
    throw new Error(`Login failed: ${json.error || JSON.stringify(json)}`);
  }

  const token = json.data.token;

  // Build the storageState manually with the token and all related keys
  // so the Svelte app considers itself logged in from the first page load.
  const storage = {
    cookies: [],
    origins: [
      {
        origin: new URL(baseURL).origin,
        localStorage: [
          { name: 'userToken', value: token },
          { name: 'userName', value: json.data.name || '' },
          { name: 'userEmail', value: json.data.email || email },
          { name: 'userData', value: JSON.stringify(json.data) },
        ],
      },
    ],
  };

  if (json.data.launch_url) {
    storage.origins[0].localStorage.push({ name: 'OWI_url', value: json.data.launch_url });
  }

  fs.writeFileSync(statePath, JSON.stringify(storage, null, 2));
  console.log(`[global-setup] Logged in as ${email}, state saved to ${statePath}`);
};
