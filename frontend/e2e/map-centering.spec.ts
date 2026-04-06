import { test, expect } from '@playwright/test';

test.describe('Map Centering E2E', () => {
  test('centers on grid origin with rotation', async ({ page }) => {
    // 1. Setup mock WebSocket with initial state
    await page.addInitScript(() => {
      class MockWebSocket extends EventTarget {
        static OPEN = 1;
        readyState = 1;
        url: string;
        onopen: ((event: Event) => void) | null = null;
        onmessage: ((event: MessageEvent) => void) | null = null;
        onclose: ((event: CloseEvent) => void) | null = null;
        onerror: ((event: Event) => void) | null = null;

        constructor(url: string) {
          super();
          this.url = url;
          setTimeout(() => {
            if (this.onopen) this.onopen(new Event('open'));
            this.dispatchEvent(new Event('open'));

            // Mock state: grid origin at (250, 350), rotation 90
            // centerX=500, centerY=375 (default for 1000x750)
            const initialData = JSON.stringify({
              world: { 
                scene: 'VIEWING', 
                fps: 60,
                viewport: { rotation: 90, x: 0, y: 0, zoom: 1 }
              },
              config: {
                proj_res: [1000, 750],
                current_map_path: 'test.svg',
                map_width: 1000,
                map_height: 750,
              },
              grid_origin_svg_x: 250,
              grid_origin_svg_y: 350,
              isConnected: true,
            });
            if (this.onmessage) this.onmessage(new MessageEvent('message', { data: initialData }));
          }, 50);
        }
        send() {}
        close() {}
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).WebSocket = MockWebSocket;
    });

    await page.goto('/');

    // 2. Wait for the SVG and check viewBox
    const svg = page.locator('svg[data-testid="schematic-svg"]');
    await expect(svg).toBeVisible();

    // The calculation from our plan:
    // Rotate (250, 350) 90 deg around (500, 375)
    // dx = -250, dy = -25
    // x' = -250 * cos(90) - (-25) * sin(90) + 500 = 0 + 25 + 500 = 525
    // y' = -250 * sin(90) + (-25) * cos(90) + 375 = -250 + 0 + 375 = 125
    // viewBox.x = 525 - 500 = 25
    // viewBox.y = 125 - 375 = -250
    
    // We expect viewBox to be "25 -250 1000 750"
    await expect(svg).toHaveAttribute('viewBox', '25 -250 1000 750');
  });

  test('falls back to map center if no grid origin provided', async ({ page }) => {
    // 1. Setup mock WebSocket with 0,0 grid origin (uncalibrated)
    await page.addInitScript(() => {
      class MockWebSocket extends EventTarget {
        static OPEN = 1;
        readyState = 1;
        url: string;
        onopen: ((event: Event) => void) | null = null;
        onmessage: ((event: MessageEvent) => void) | null = null;

        constructor(url: string) {
          super();
          this.url = url;
          setTimeout(() => {
            if (this.onopen) this.onopen(new Event('open'));
            const initialData = JSON.stringify({
              world: { scene: 'VIEWING', fps: 60 },
              config: {
                proj_res: [1000, 750],
                current_map_path: 'test.svg',
                map_width: 800,
                map_height: 600,
              },
              grid_origin_svg_x: 0,
              grid_origin_svg_y: 0,
              isConnected: true,
            });
            if (this.onmessage) this.onmessage(new MessageEvent('message', { data: initialData }));
          }, 50);
        }
        send() {}
        close() {}
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (window as any).WebSocket = MockWebSocket;
    });

    await page.goto('/');

    const svg = page.locator('svg[data-testid="schematic-svg"]');
    await expect(svg).toBeVisible();

    // If it falls back to map center (800/2, 600/2) = (400, 300)
    // x = 400 - 500 = -100
    // y = 300 - 375 = -75
    // Wait, the user said "If no grid origin I guess we can fall back to the center of the map."
    // Currently it centers on (0,0) if origin is 0,0.
    // Let's see if it fails (it should if I haven't implemented fallback yet).
    // I expect it currently to be "-500 -375 1000 750" (centered on 0,0)
    await expect(svg).toHaveAttribute('viewBox', '-100 -75 1000 750');
  });
});
