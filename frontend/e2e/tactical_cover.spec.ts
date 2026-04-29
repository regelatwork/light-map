import { test, expect } from '@playwright/test';
import { MockWebSocket } from './utils/mock-socket';
import { E2EWindow } from './types/e2e';
import { SystemState } from '../src/types/system';

/**
 * Tactical Cover E2E Test
 */
test.describe('Tactical Cover Integration', () => {
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

    // Mock the config API
    await page.route('**/config', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ 
            proj_res: [1000, 750],
            projector_ppi: 96.0, 
            current_map_path: 'tactical_map.svg',
            map_width: 800,
            map_height: 600
        })
      });
    });

    // Mock the tactical cover API
    await page.route('**/tactical/cover*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          '2': { 
            ac_bonus: 2, 
            reflex_bonus: 1, 
            explanation: 'Partial Cover',
            best_apex: [50, 50],
            npc_pixels: [[100, 100], [110, 110]],
            segments: [{ start_idx: 0, end_idx: 1, status: 0 }]
          }
        })
      });
    });

    // Mock WebSocket to provide initial tokens
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
              selection: { type: 'NONE', id: null } as any
            } as any,
            tokens: [
              { id: 1, world_x: 50, world_y: 50, name: 'Attacker', type: 'PC' },
              { id: 2, world_x: 100, world_y: 100, name: 'Target', type: 'NPC' }
            ] as any,
            config: { 
                proj_res: [1000, 750],
                projector_ppi: 96.0, 
                current_map_path: 'tactical_map.svg',
                map_width: 800,
                map_height: 600
            } as any,
            tactical_timestamp: 1
          };
          instance.triggerMessage(JSON.stringify(initialData));
        }, 100);

        return instance;
      } as any;
      Object.assign(win.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
    }, MockWebSocket.toString());
  });

  test('displays tactical cover when a token is selected', async ({ page }) => {
    await page.goto('/');

    // 1. Wait for map to load
    const mapLayer = page.getByTestId('map-image');
    await expect(mapLayer).toBeVisible();

    // 2. Tokens should be visible
    const attackerGroup = page.getByTestId('token-group-1');
    const targetGroup = page.getByTestId('token-group-2');
    await expect(attackerGroup).toBeVisible();
    await expect(targetGroup).toBeVisible();

    // 3. Click to select.
    await attackerGroup.click();

    // 4. Update selection state via WebSocket
    await page.evaluate(() => {
      const win = window as unknown as E2EWindow;
      const data: Partial<SystemState> = {
        world: { 
          scene: 'VIEWING', 
          fps: 60, 
          selection: { type: 'TOKEN', id: '1' } as any,
          tactical_bonuses: {
            '2': { 
                ac_bonus: 2, 
                reflex_bonus: 1, 
                explanation: 'Partial Cover',
                best_apex: [50, 50],
                npc_pixels: [[100, 100], [110, 110]],
                segments: [{ start_idx: 0, end_idx: 1, status: 0 }]
            }
          }
        } as any,
        tokens: [
          { id: 1, world_x: 50, world_y: 50, name: 'Attacker', type: 'PC' },
          { id: 2, world_x: 100, world_y: 100, name: 'Target', type: 'NPC' }
        ] as any,
        config: { 
            proj_res: [1000, 750],
            projector_ppi: 96.0, 
            current_map_path: 'tactical_map.svg' 
        } as any,
        tactical_timestamp: 2
      };
      win.mockWs?.triggerMessage(JSON.stringify(data));
    });

    // Verify update - The TacticalCoverLayer renders bonuses
    await expect(page.getByText('+2 AC', { exact: true })).toBeVisible();
  });
});
