const { chromium } = require('playwright');
const fs = require('fs');

const baseUrl = process.argv[2] || 'http://localhost:9099/';

(async () => {
    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext();
    const page = await context.newPage();

    // Step 1: Go to localhost:9099 first
    await page.goto(baseUrl);

    // (Optional) Load session data if needed (kept from previous logic but moved after initial navigation)
    try {
        if (fs.existsSync('session_data.json')) {
            const sessionData = JSON.parse(fs.readFileSync('session_data.json', 'utf-8'));
            console.log('Loaded session data. Applying to page...');
            await page.evaluate((data) => {
                for (const [key, value] of Object.entries(data.localStorage)) localStorage.setItem(key, value);
                for (const [key, value] of Object.entries(data.sessionStorage)) sessionStorage.setItem(key, value);
            }, sessionData);
            await page.reload();
            await page.waitForLoadState('networkidle');
        }
    } catch (err) {
        console.error('Failed to load session data:', err);
    }

    // Step 2: Click the OpenWebUI external link (opens a new tab/window)
    // We capture the popup created by clicking the link whose visible text is 'OpenWebUI'
    let owuiPage;
    try {
        const [popup] = await Promise.all([
            context.waitForEvent('page'),
            page.getByRole('link', { name: 'OpenWebUI' }).click()
        ]);
        owuiPage = popup;
        await owuiPage.waitForLoadState('domcontentloaded');
        console.log('Opened OpenWebUI page at URL:', owuiPage.url());
    } catch (e) {
        console.error('Failed to open OpenWebUI link:', e);
        await browser.close();
        process.exit(1);
    }

    // If the link already authenticated us via token, proceed; otherwise we might need to wait a bit
    await owuiPage.waitForLoadState('networkidle').catch(()=>{});

    try {
        // Step 3: Go directly to admin settings in the new OpenWebUI page
        await owuiPage.goto('http://10.243.22.162:8080/admin/settings');

        // Click on Connections tab
        await owuiPage.getByRole('button', { name: 'Connections' }).click();

        // Click on the gear icon (Configure) for Manage OpenAI API Connections
        await owuiPage.getByRole('button').filter({ hasText: /^$/ }).nth(3).click();

        // Fill the API Base URL
        await owuiPage.locator('form').filter({ hasText: 'URL Key Prefix ID Model IDs' }).getByPlaceholder('API Base URL').fill('http://10.243.22.162:9099');

        // Fill the API Key
        await owuiPage.locator('form').filter({ hasText: 'URL Key Prefix ID Model IDs' }).getByPlaceholder('API Key').fill('0p3n-w3bu!');

        // Click Save
        await owuiPage.getByRole('button', { name: 'Save' }).nth(1).click();

        // Wait for the success notification
        await owuiPage.waitForSelector('text=OpenAI API settings updated', { timeout: 10000 });

        console.log('OpenWebUI OpenAI connection configured successfully via external auth link.');
    } catch (err) {
        console.error('Configuration steps failed:', err);
        process.exit(1);
    } finally {
        await browser.close();
    }
})();
