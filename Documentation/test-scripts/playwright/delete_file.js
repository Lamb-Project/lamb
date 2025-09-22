const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
    const browser = await chromium.launch({ headless: false, slowMo: 1000 });
    const context = await browser.newContext({
        viewport: { width: 1438, height: 1148 },
    });
    const page = await context.newPage();
    const timeout = 5000;

    // Set default timeout
    page.setDefaultTimeout(timeout);

    // Load session data from session_data.json if available
    try {
        if (fs.existsSync('session_data.json')) {
            const sessionData = JSON.parse(fs.readFileSync('session_data.json', 'utf-8'));
            console.log('Loaded session data.');

            // Set localStorage and sessionStorage data
            await page.goto('http://localhost:5173/');
            await page.evaluate((data) => {
                for (const [key, value] of Object.entries(data.localStorage)) {
                    localStorage.setItem(key, value);
                }
                for (const [key, value] of Object.entries(data.sessionStorage)) {
                    sessionStorage.setItem(key, value);
                }
            }, sessionData);

            // Reload to apply the session data
            await page.reload();
            await page.waitForLoadState('networkidle');
        }
    } catch (err) {
        console.error('Failed to load session data:', err);
    }

    // Navigate to the knowledge base detail page
    await page.goto('http://localhost:5173/knowledgebases?view=detail&id=1');

    // Click on the main div area (likely selecting a file)
    await page.locator('main > div').click({
        position: { x: 953, y: 461 }
    });

    // Set up dialog handler for native browser confirmation dialogs
    page.on('dialog', async dialog => {
        console.log(`Dialog message: ${dialog.message()}`);
        await dialog.accept(); // Click OK
    });


    // Click the Delete button
    await page.getByRole('button', { name: 'Delete' }).click({
        position: { x: 4.7421875, y: 12 }
    });

    // create a screenshot after deletion
    await page.screenshot({ path: 'delete_file_screenshot.png', fullPage: true });
    console.log('Screenshot saved as delete_file_screenshot.png');
    
    await browser.close();

})().catch(err => {
    console.error(err);
    process.exit(1);
});