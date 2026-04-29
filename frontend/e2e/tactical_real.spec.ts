import { test, expect } from '@playwright/test';

/**
 * Real Backend E2E Test
 * 
 * This test expects a real backend running at http://localhost:8000
 * and a frontend at http://localhost:5173.
 * It DOES NOT mock API calls or WebSockets.
 */
test.describe('Tactical Cover Real Integration', () => {
  test.beforeEach(async ({ page }) => {
    // Inject the real API host from environment variable
    const apiHost = process.env.VITE_API_HOST || 'localhost:8000';
    await page.addInitScript((host) => {
      (window as unknown as { VITE_API_HOST: string }).VITE_API_HOST = host;
    }, apiHost);

    // Clear any existing mocks/routes to ensure we hit the real backend
    await page.unroute('**/*');
    page.on('console', msg => console.log('BROWSER:', msg.text()));
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  });

  test('backend survives selection and returns tactical data', async ({ page }) => {
    const apiHost = process.env.VITE_API_HOST || '127.0.0.1:8000';
    await page.goto('/');

    // 1. Wait for system to connect to real backend
    await expect(page.getByTitle('Connected')).toBeVisible({ timeout: 20000 });

    // Wait for initial data to settle
    await page.waitForTimeout(2000);

    // 2. Ensure we have tokens
    const tokensText = page.getByText(/Tokens: [2-9]/);
    await expect(tokensText).toBeVisible({ timeout: 15000 });

    // 3. Find a token on the canvas. 
    // We injected token 1 and 2 in our setup script.
    const attackerGroup = page.getByTestId('token-group-1');
    await expect(attackerGroup).toBeVisible();

    // 4. Click to select.
    await attackerGroup.click();
    console.log('Clicked attacker token');

    // 5. Verify the backend survives and returns data via API check (with retries for calculation time)
    let data: Record<string, unknown> = {};
    for (let i = 0; i < 10; i++) {
        const response = await page.request.get(`http://${apiHost}/tactical/cover?attacker_id=1`);
        expect(response.ok()).toBeTruthy();
        data = await response.json() as Record<string, unknown>;
        console.log(`POLL ${i} API DATA keys:`, Object.keys(data));
        if (Object.keys(data).length > 0) break;
        await page.waitForTimeout(2000);
    }
    expect(Object.keys(data).length).toBeGreaterThan(0);

    // 6. Verify tactical layer appears
    const tacticalLayer = page.locator('.tactical-cover-layer');
    await expect(tacticalLayer.locator('*').first()).toBeVisible({ timeout: 30000 });

    // 7. Verify we got real bonuses (e.g., +4 AC or similar from test_blocker.svg)
    // We check for any bonus label
    await expect(page.getByText(/AC/)).toBeVisible();
  });
});
