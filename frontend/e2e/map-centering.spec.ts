import { test, expect } from '@playwright/test';
import { MockWebSocket } from './utils/mock-socket';
import { E2EWindow } from './types/e2e';
import { SystemState } from '../src/types/system';

test.describe('Map Centering E2E', () => {
  test.beforeEach(async ({ page }) => {
    page.on('console', msg => console.log('BROWSER:', msg.text()));
    page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));

    // Mock the maps API
    await page.route('**/maps', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ path: '/maps/test.svg', name: 'test.svg' }])
      });
    });
  });

  test('centers on grid origin with rotation', async ({ page }) => {
    // Mock the config API with the target map
    await page.route('**/config', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ 
          proj_res: [1000, 750], 
          current_map_path: 'map_rotated.svg',
          map_width: 800,
          map_height: 600
        })
      });
    });

    await page.addInitScript((MockWebSocketSource) => {
      const MockWebSocketClass = new Function(`return ${MockWebSocketSource}`)();
      const win = window as unknown as E2EWindow;
      
      win.WebSocket = function(url: string) {
        const instance = new (MockWebSocketClass as any)(url);
        win.mockWs = instance;

        setTimeout(() => {
          instance.triggerOpen();
          const initialData: Partial<SystemState> = {
            world: { 
              scene: 'VIEWING', 
              fps: 60,
              viewport: { x: 500, y: 375, zoom: 1.0, rotation: 90 }
            } as any,
            config: {
                proj_res: [1000, 750], 
                current_map_path: 'map_rotated.svg',
                map_width: 800,
                map_height: 600
            } as any,
            grid_origin_svg_x: 400,
            grid_origin_svg_y: 300,
            isConnected: true,
          };
          instance.triggerMessage(JSON.stringify(initialData));
        }, 50);

        return instance;
      } as any;
      Object.assign(win.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
    }, MockWebSocket.toString());

    await page.goto('/');

    const svg = page.locator('svg[data-testid="schematic-svg"]');
    await expect(svg).toBeVisible();
    
    // Calculation:
    // rotatePoint(400, 300, 500, 375, 90)
    // dx = 400 - 500 = -100
    // dy = 300 - 375 = -75
    // rotated: x = 500 - (-75) = 575, y = 375 + (-100) = 275
    // viewBox: x = 575 - 500 = 75, y = 275 - 375 = -100
    
    await expect(svg).toHaveAttribute('viewBox', '75 -100 1000 750');
  });

  test('falls back to map center if no grid origin provided', async ({ page }) => {
    await page.route('**/config', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ 
          proj_res: [1000, 750], 
          current_map_path: 'map_fallback.svg',
          map_width: 800,
          map_height: 600
        })
      });
    });

    await page.addInitScript((MockWebSocketSource) => {
      const MockWebSocketClass = new Function(`return ${MockWebSocketSource}`)();
      const win = window as unknown as E2EWindow;
      
      win.WebSocket = function(url: string) {
        const instance = new (MockWebSocketClass as any)(url);
        win.mockWs = instance;

        setTimeout(() => {
          instance.triggerOpen();
          const initialData: Partial<SystemState> = {
            world: { 
              scene: 'VIEWING', 
              fps: 60,
              viewport: { x: 400, y: 300, zoom: 1.0, rotation: 0 }
            } as any,
            config: {
              proj_res: [1000, 750],
              current_map_path: 'map_fallback.svg',
              map_width: 800,
              map_height: 600,
            } as any,
            grid_origin_svg_x: 0,
            grid_origin_svg_y: 0,
            isConnected: true,
          };
          instance.triggerMessage(JSON.stringify(initialData));
        }, 50);

        return instance;
      } as any;
      Object.assign(win.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
    }, MockWebSocket.toString());

    await page.goto('/');

    const svg = page.locator('svg[data-testid="schematic-svg"]');
    await expect(svg).toBeVisible();
    
    await expect(svg).toHaveAttribute('viewBox', '-100 -75 1000 750');
  });
});
