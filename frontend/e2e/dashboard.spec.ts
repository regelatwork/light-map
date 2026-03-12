import { test, expect } from '@playwright/test';

test.describe('Dashboard E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the maps API
    await page.route('**/maps', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { path: '/maps/test1.jpg', name: 'test1.jpg' },
          { path: '/maps/test2.jpg', name: 'test2.jpg' },
        ]),
      });
    });

    // Mock the map load API
    await page.route('**/map/load*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    // Mock the grid config API
    await page.route('**/config/grid', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });
  });

  test('loads dashboard and displays components', async ({ page }) => {
    await page.goto('/');

    // Check title/header
    await expect(page.getByText('Light Map Control')).toBeVisible();
    await expect(page.getByText('System Status')).toBeVisible();

    // Check maps are loaded from the mock API
    await expect(page.getByText('test1.jpg').first()).toBeVisible();
    await expect(page.getByText('test2.jpg').first()).toBeVisible();

    // Check tabs
    await expect(page.getByRole('button', { name: 'Schematic View' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Calibration Wizards' })).toBeVisible();

    // Check configuration sidebar
    await expect(page.getByText('Configuration')).toBeVisible();
    await expect(page.getByText('Grid Origin X')).toBeVisible();
  });

  test('loads a map when clicked', async ({ page }) => {
    await page.goto('/');

    // Wait for maps to load
    const mapButton = page.getByTitle('/maps/test1.jpg');
    await expect(mapButton).toBeVisible();

    // Set up a promise to wait for the map load API call
    const mapLoadPromise = page.waitForRequest(
      (request) => request.url().includes('/map/load') && request.method() === 'POST'
    );

    // Click the map
    await mapButton.click();

    // Verify the API call was made
    const request = await mapLoadPromise;
    expect(request.url()).toContain('path=%2Fmaps%2Ftest1.jpg');
  });

  test('switches tabs correctly', async ({ page }) => {
    await page.goto('/');

    // Verify Schematic View is active by default
    await expect(page.getByRole('heading', { name: 'Schematic View' })).toBeVisible();

    // Switch to Calibration Wizards
    await page.getByRole('button', { name: 'Calibration Wizards' }).click();

    // Verify Schematic View is hidden and Calibration Wizard is visible
    await expect(page.getByRole('heading', { name: 'Schematic View' })).not.toBeVisible();
    await expect(page.getByText('Camera Intrinsics')).toBeVisible();
  });

  test('pans the schematic canvas', async ({ page }) => {
    await page.goto('/');

    // Wait for the SVG to be visible
    const svg = page.locator('svg.cursor-move');
    await expect(svg).toBeVisible();

    // Get initial viewBox
    const initialViewBox = await svg.getAttribute('viewBox');
    expect(initialViewBox).toBe('0 0 1000 750');

    // Pan the canvas
    const box = await svg.boundingBox();
    if (!box) throw new Error('SVG not found');

    // Move to center (clicking background)
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    // Move slowly or just move and wait
    await page.mouse.move(box.x + box.width / 2 - 100, box.y + box.height / 2 - 50, { steps: 5 });
    await page.mouse.up();

    // Get new viewBox
    const newViewBox = await svg.getAttribute('viewBox');
    expect(newViewBox).not.toBe('0 0 1000 750');

    const [x, y, w, h] = newViewBox!.split(' ').map(Number);
    expect(x).toBeGreaterThan(0);
    expect(y).toBeGreaterThan(0);
    expect(w).toBe(1000);
    expect(h).toBe(750);
  });

  test('updates UI on WebSocket message', async ({ page }) => {
    await page.addInitScript(() => {
      // Mock WebSocket
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
          setTimeout(() => {
            if (this.onopen) this.onopen(new Event('open'));
            this.dispatchEvent(new Event('open'));

            // Send initial state message
            const initialData = JSON.stringify({
              world: { scene: 'test-scene', fps: 60.5 },
              tokens: [{ id: 42, world_x: 100, world_y: 200, is_occluded: false }],
              grid_origin_svg_x: 0,
              grid_origin_svg_y: 0,
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

    await page.goto('/');

    // Verify UI updates from WebSocket message
    await expect(page.getByText('Scene: test-scene')).toBeVisible();
    await expect(page.getByText('FPS: 60.5')).toBeVisible();
    await expect(page.getByText('Tokens: 1')).toBeVisible();
  });
});
