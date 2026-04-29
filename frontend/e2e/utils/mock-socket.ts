/**
 * MockWebSocket implements a basic WebSocket interface for E2E testing.
 * It is designed to be stringified and injected into the browser via playwright.
 */
export class MockWebSocket extends EventTarget {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readyState: number = 0; // CONNECTING
  url: string;
  sentMessages: string[] = [];

  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    super();
    this.url = url;
  }

  send(data: string): void {
    this.sentMessages.push(data);
  }

  close(code: number = 1000, reason: string = ''): void {
    this.readyState = 2; // CLOSING
    setTimeout(() => {
      this.readyState = 3; // CLOSED
      const event = new CloseEvent('close', { code, reason, wasClean: true });
      if (this.onclose) this.onclose(event);
      this.dispatchEvent(event);
    }, 0);
  }

  triggerOpen(): void {
    this.readyState = 1; // OPEN
    const event = new Event('open');
    if (this.onopen) this.onopen(event);
    this.dispatchEvent(event);
  }

  triggerMessage(data: string): void {
    const event = new MessageEvent('message', { data });
    if (this.onmessage) this.onmessage(event);
    this.dispatchEvent(event);
  }

  triggerError(): void {
    const event = new Event('error');
    if (this.onerror) this.onerror(event);
    this.dispatchEvent(event);
  }

  triggerClose(code: number = 1000, reason: string = ''): void {
    this.readyState = 3; // CLOSED
    const event = new CloseEvent('close', { code, reason, wasClean: true });
    if (this.onclose) this.onclose(event);
    this.dispatchEvent(event);
  }
}
