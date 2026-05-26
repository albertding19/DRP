/**
 * Shared WebSocket client.
 *
 * On any page that wants real-time updates, do:
 *
 *   <div x-data x-init="$store.ws.connect('/ws/feed/')"
 *        x-on:ws:score_changed.window="updateScore($event.detail)">
 *
 * The store exposes a single open WebSocket per path, auto-reconnects with
 * exponential backoff, and dispatches a `CustomEvent` per server message
 * (`ws:<type>` on `window`, with the `payload` in `detail`).
 *
 * Server messages MUST be JSON of shape: { "type": "...", "payload": {...} }
 *
 * Consumers come Thu 28 May; this client is ready for them.
 */

document.addEventListener("alpine:init", () => {
  Alpine.store("ws", {
    socket: null,
    path: null,
    backoff: 500,
    closedByUser: false,

    connect(path) {
      if (this.socket && this.path === path) return;
      this.path = path;
      this.closedByUser = false;
      this._open();
    },

    disconnect() {
      this.closedByUser = true;
      if (this.socket) this.socket.close();
      this.socket = null;
    },

    _open() {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${location.host}${this.path}`;
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        this.backoff = 500;
      };

      this.socket.onmessage = (e) => {
        let msg;
        try {
          msg = JSON.parse(e.data);
        } catch {
          return;
        }
        if (!msg.type) return;
        window.dispatchEvent(
          new CustomEvent(`ws:${msg.type}`, { detail: msg.payload || {} }),
        );
      };

      this.socket.onclose = () => {
        if (this.closedByUser) return;
        // Exponential backoff capped at ~10s
        const wait = Math.min(this.backoff, 10000);
        this.backoff = Math.min(this.backoff * 2, 10000);
        setTimeout(() => this._open(), wait);
      };

      this.socket.onerror = () => {
        if (this.socket) this.socket.close();
      };
    },
  });
});
