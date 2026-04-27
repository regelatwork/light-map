import { test, expect } from '@playwright/test';

test.describe('Tactical Cover E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the tactical cover API
    await page.route('**/tactical/cover*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          "2": {
            "ac_bonus": 4,
            "reflex_bonus": 2,
            "best_apex": [50, 50],
            "segments": [{ "start_idx": 0, "end_idx": 1, "status": 2 }],
            "npc_pixels": [[100, 100], [110, 110]],
            "explanation": "Standard Cover (+4 AC): 62% obscured by obstacles."
          }
        }),
      });
    });

    // Mock the inject action API
    await page.route('**/input/action*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    // Mock WebSocket to provide initial tokens
    await page.addInitScript(() => {
      class MockWebSocket extends EventTarget {
        static OPEN = 1;
        readyState = 1;
        url: string;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onopen: any = null;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onmessage: any = null;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onclose: any = null;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        onerror: any = null;

        constructor(url: string) {
          super();
          this.url = url;
          // @ts-expect-error: MockWebSocket is not in window type
          window.mockWs = this;
          setTimeout(() => {
            if (this.onopen) this.onopen(new Event('open'));
            this.dispatchEvent(new Event('open'));

            const initialData = JSON.stringify({
              world: { 
                scene: 'VIEWING', 
                fps: 60, 
                selection: { type: 'NONE', id: null } 
              },
              tokens: [
                { id: 1, world_x: 50, world_y: 50, name: 'Attacker', type: 'PC' },
                { id: 2, world_x: 100, world_y: 100, name: 'Target', type: 'NPC' }
              ],
              config: { projector_ppi: 96.0, current_map_path: 'test.svg' },
              tactical_timestamp: 1
            });
            if (this.onmessage) this.onmessage(new MessageEvent('message', { data: initialData }));
            this.dispatchEvent(new MessageEvent('message', { data: initialData }));
          }, 100);
        }
        send() {}
        close() {}
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).WebSocket = MockWebSocket;
    });
  });

  test('displays tactical cover when a token is selected', async ({ page }) => {
    await page.goto('/');

    // Check if the dashboard at least loaded
    await expect(page.getByText('Light Map Control')).toBeVisible();

    // The dot should be Disconnected initially
    const statusDot = page.locator('div[title="Disconnected"], div[title="Connected"]');
    await expect(statusDot).toBeVisible();

    // Wait for it to become Connected
    await expect(page.getByTitle('Connected')).toBeVisible({ timeout: 10000 });

    // Verify tokens count in the status bar
    await expect(page.getByText('Tokens: 2')).toBeVisible();

    // Verify tokens are rendered on canvas
    const attackerGroup = page.getByTestId('token-group-1');
    const targetGroup = page.getByTestId('token-group-2');
    
    await expect(attackerGroup).toBeVisible();
    await expect(targetGroup).toBeVisible();

    // Click on Attacker to select it
    await attackerGroup.click();

    // Verify TacticalCoverLayer elements are visible
    // We expect a path for the wedge and a text element for the bonus
    await expect(page.locator('.tactical-cover-layer')).toBeVisible();
    await expect(page.getByText('+4 AC', { exact: true })).toBeVisible();

    // Verify tooltip on hover
    // The tooltip is implemented via <title> in our TacticalCoverLayer
    const interactionArea = page.locator('circle.cursor-help');
    await expect(interactionArea).toBeVisible();
    
    // In Playwright, we can check the title element text
    const titleText = await interactionArea.locator('title').textContent();
    expect(titleText).toContain('Standard Cover (+4 AC)');
    expect(titleText).toContain('62% obscured');
  });

  test('clears tactical cover when selection is cleared', async ({ page }) => {
    await page.goto('/');
    
    // Select attacker
    await page.getByTestId('token-group-1').click();
    await expect(page.locator('.tactical-cover-layer')).toBeVisible();

    // Click background to clear selection (SchematicCanvas.tsx handles this)
    await page.locator('rect').first().click();

    // Verify layer is gone
    await expect(page.locator('.tactical-cover-layer')).not.toBeVisible();
  });

  test('refreshes tactical cover when tokens move', async ({ page }) => {
    await page.goto('/');
    
    // Select attacker
    await page.getByTestId('token-group-1').click();
    await expect(page.getByText('+4 AC', { exact: true })).toBeVisible();

    // Mock a second API response with updated data
    await page.route('**/tactical/cover*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          "2": {
            "ac_bonus": 2,
            "reflex_bonus": 1,
            "best_apex": [55, 55],
            "segments": [{ "start_idx": 0, "end_idx": 1, "status": 2 }],
            "npc_pixels": [[100, 100], [110, 110]],
            "explanation": "Partial Cover (+2 AC)"
          }
        }),
      });
    });

    // Simulate token movement via WebSocket (this triggers tactical_timestamp update)
    await page.evaluate(() => {
      const data = JSON.stringify({
        world: { 
          scene: 'VIEWING', 
          fps: 60, 
          selection: { type: 'TOKEN', id: 1 } 
        },
        tokens: [
          { id: 1, world_x: 60, world_y: 60, name: 'Attacker', type: 'PC' },
          { id: 2, world_x: 100, world_y: 100, name: 'Target', type: 'NPC' }
        ],
        config: { projector_ppi: 96.0, current_map_path: 'test.svg' },
        tactical_timestamp: 2 // Increment version
      });
      // @ts-expect-error: MockWebSocket is not in window type
      window.mockWs.onmessage(new MessageEvent('message', { data }));
    });

    // Verify update
    await expect(page.getByText('+2 AC', { exact: true })).toBeVisible();
  });
});
