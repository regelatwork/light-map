import { test, expect } from '@playwright/test';
import { MockWebSocket } from './utils/mock-socket';
import { E2EWindow } from './types/e2e';

test.describe('Dashboard E2E', () => {
  test.beforeEach(async ({ page }) => {
    page.on('console', msg => console.log('BROWSER:', msg.text()));
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));

    // Mock WebSocket MUST be injected before anything else
    await page.addInitScript((MockWebSocketSource) => {
      const MockWebSocketClass = new Function(`return ${MockWebSocketSource}`)();
      const win = window as unknown as E2EWindow;
      
      win.WebSocket = function(url: string) {
        const instance = new (MockWebSocketClass as any)(url);
        win.mockWs = instance;
        setTimeout(() => { instance.triggerOpen(); }, 50);
        return instance;
      } as any;
      
      Object.assign(win.WebSocket, {
        CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3
      });
    }, MockWebSocket.toString());

    // Mock the maps API
    await page.route('**/maps', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { path: '/maps/test1.jpg', name: 'test1.jpg' },
        ]),
      });
    });

    // Mock the config API
    await page.route('**/config', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          cam_res: [1280, 720],
          proj_res: [1920, 1080],
          debug_mode: false,
        }),
      });
    });
  });

  test('loads dashboard and displays components', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Light Map Control')).toBeVisible();
    await expect(page.getByText('FPS: 0.0')).toBeVisible();
    await expect(page.getByText('Tokens: 0')).toBeVisible();
  });

  test('loads a map when clicked', async ({ page }) => {
    await page.goto('/');

    // Find the map item in the library
    const mapItem = page.locator('div').filter({ hasText: /^test1\.jpg$/ }).first();
    await expect(mapItem).toBeVisible();
    await mapItem.click();

    await expect(page.getByText('Light Map Control')).toBeVisible();
  });

  test('switches tabs correctly', async ({ page }) => {
    await page.goto('/');

    // Switch to Calibration tab
    const calibTab = page.getByRole('button', { name: 'Calibration Wizards' });
    await expect(calibTab).toBeVisible();
    await calibTab.click();

    // Verify calibration view
    await expect(page.getByText('Camera Intrinsics')).toBeVisible();
  });

  test('pans the schematic canvas', async ({ page }) => {
    await page.goto('/');

    const canvas = page.locator('svg[data-testid="schematic-svg"]');
    await expect(canvas).toBeVisible();

    const box = await canvas.boundingBox();
    if (!box) throw new Error('Canvas bounding box not found');

    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;

    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(x + 100, y + 100);
    await page.mouse.up();

    await expect(canvas).toBeVisible();
  });

  test('updates UI on WebSocket message', async ({ page }) => {
    await page.goto('/');

    await page.evaluate(() => {
        const win = window as unknown as E2EWindow;
        if (!win.mockWs) throw new Error('mockWs not found on window');

        const data = {
          world: { scene: 'test-scene', fps: 60.5 },
          tokens: [{ id: 42, world_x: 100, world_y: 200, is_occluded: false }],
          grid_origin_svg_x: 0,
          grid_origin_svg_y: 0,
        };
        win.mockWs.triggerMessage(JSON.stringify(data));
    });

    await expect(page.getByText('Scene: test-scene')).toBeVisible();
    await expect(page.getByText('FPS: 60.5')).toBeVisible();
    await expect(page.getByText('Tokens: 1')).toBeVisible();
  });
});
