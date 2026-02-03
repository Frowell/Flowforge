/**
 * WebSocket connection manager with auto-reconnect.
 *
 * Handles two message types:
 * 1. Execution status: pending -> running -> complete/error per node
 * 2. Live data: streaming results from Materialize-backed sources
 *
 * Supports channel subscriptions: subscribe/unsubscribe to specific
 * server-side Redis pub/sub channels for targeted message delivery.
 */

type MessageHandler = (data: unknown) => void;
type ConnectionHandler = (connected: boolean) => void;

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers = new Map<string, Set<MessageHandler>>();
  private connectionHandlers = new Set<ConnectionHandler>();
  private subscribedChannels = new Set<string>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(url: string = `ws://${window.location.host}/ws`) {
    this.url = url;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.notifyConnectionChange(true);
      // Re-subscribe to all channels after reconnect
      for (const channel of this.subscribedChannels) {
        this.send({ action: "subscribe", channel });
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as { type: string; [key: string]: unknown };
        const typeHandlers = this.handlers.get(message.type);
        if (typeHandlers) {
          for (const handler of typeHandlers) {
            handler(message);
          }
        }
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.notifyConnectionChange(false);
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = this.maxReconnectAttempts;
    this.ws?.close();
    this.ws = null;
  }

  subscribe(messageType: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(messageType)) {
      this.handlers.set(messageType, new Set());
    }
    this.handlers.get(messageType)!.add(handler);

    return () => {
      this.handlers.get(messageType)?.delete(handler);
    };
  }

  /**
   * Subscribe to a server-side channel (e.g., "widget:{widgetId}" or "execution:{executionId}").
   * The server prepends the tenant prefix automatically.
   */
  subscribeChannel(channel: string): void {
    this.subscribedChannels.add(channel);
    this.send({ action: "subscribe", channel });
  }

  /**
   * Unsubscribe from a server-side channel.
   */
  unsubscribeChannel(channel: string): void {
    this.subscribedChannels.delete(channel);
    this.send({ action: "unsubscribe", channel });
  }

  /**
   * Register a handler for connection state changes.
   */
  onConnectionChange(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);
    return () => {
      this.connectionHandlers.delete(handler);
    };
  }

  send(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  private notifyConnectionChange(connected: boolean): void {
    for (const handler of this.connectionHandlers) {
      handler(connected);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }
}

export const wsManager = new WebSocketManager();
