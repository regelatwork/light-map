import { MockWebSocket } from '../utils/mock-socket';

/**
 * E2EWindow extends the global Window interface with properties used in E2E tests.
 */
export interface E2EWindow extends Window {
  /**
   * API host used by the frontend to connect to the backend.
   */
  VITE_API_HOST?: string;

  /**
   * Reference to the MockWebSocket instance used in tests.
   */
  mockWs?: MockWebSocket;
}
