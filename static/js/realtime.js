/**
 * Shared WebSocket client.
 *
 * Pages can open multiple concurrent sockets — the store keeps an entry
 * per path, with its own backoff/reconnect state. Most pages still open
 * one; the dashboard opens two (`/ws/feed/` + `/ws/matchmaking/<uid>/`).
 *
 * Usage:
 *
 *   <div x-data
 *        x-init="$store.ws.connect('/ws/feed/')"
 *        x-on:ws:score_changed.window="updateScore($event.detail)">
 *
 *   <!-- multiple sockets on one page -->
 *   <div x-init="$store.ws.connect('/ws/feed/');
 *                $store.ws.connect('/ws/matchmaking/{{ user.id }}/')">
 *
 *   <!-- targeted disconnect -->
 *   $store.ws.disconnect('/ws/feed/');
 *   <!-- back-compat: no-arg disconnects all -->
 *   $store.ws.disconnect();
 *
 * Server messages MUST be JSON of shape: { "type": "...", "payload": {...} }.
 * Each message is fan-out to `window` as a `CustomEvent` named `ws:<type>`
 * with the payload in `detail`. Listeners do NOT need to know which socket
 * delivered the event — message types are globally unique.
 */

// htmx 1.9.x does not swap 4xx responses by default. The tasks add-task /
// add-busy forms intentionally reply 422 + HX-Retarget/HX-Reswap to replace
// themselves with inline validation errors (apps/tasks/views.py
// `_form_error_response`). 422 is used for that flow only, so opt it in here.
document.addEventListener("htmx:beforeSwap", (event) => {
  if (event.detail.xhr && event.detail.xhr.status === 422) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});

// ---------------------------------------------------------------------------
// Live "X min to go" countdown for the in-progress task banner.
//
// The banner's <span data-countdown-to="<epoch ms>"> carries the moment the
// task is due to finish. ONE global timer re-renders the label every second
// and survives HTMX swaps of #full-region — it just reads whatever banner is
// in the DOM, so there are no per-element intervals to leak. With JS off the
// server-rendered fallback text stands.
// ---------------------------------------------------------------------------
function renderCountdowns() {
  for (const el of document.querySelectorAll("[data-countdown-to]")) {
    const endsAt = Number(el.dataset.countdownTo);
    if (!endsAt) continue;
    const mins = Math.max(0, Math.ceil((endsAt - Date.now()) / 60000));
    el.textContent = mins > 0 ? `${mins} min to go` : "time's up";
  }
}
setInterval(renderCountdowns, 1000);
document.addEventListener("DOMContentLoaded", renderCountdowns);
document.addEventListener("htmx:afterSwap", renderCountdowns);

document.addEventListener("alpine:init", () => {
  Alpine.store("ws", {
    /** path → { socket, backoff, closedByUser } */
    sockets: {},

    connect(path) {
      if (this.sockets[path]) return;
      this.sockets[path] = { socket: null, backoff: 500, closedByUser: false };
      this._open(path);
    },

    disconnect(path) {
      if (path) {
        const entry = this.sockets[path];
        if (!entry) return;
        entry.closedByUser = true;
        if (entry.socket) entry.socket.close();
        delete this.sockets[path];
      } else {
        // Back-compat: no-arg disconnects every socket. Old callers
        // (single-socket pages) still work without changes.
        for (const p of Object.keys(this.sockets)) this.disconnect(p);
      }
    },

    _open(path) {
      const entry = this.sockets[path];
      if (!entry) return;
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      entry.socket = new WebSocket(`${proto}//${location.host}${path}`);

      entry.socket.onopen = () => {
        entry.backoff = 500;
      };

      entry.socket.onmessage = (e) => {
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

      entry.socket.onclose = () => {
        if (entry.closedByUser) return;
        // Exponential backoff capped at ~10s, per-socket.
        const wait = Math.min(entry.backoff, 10000);
        entry.backoff = Math.min(entry.backoff * 2, 10000);
        setTimeout(() => this._open(path), wait);
      };

      entry.socket.onerror = () => {
        if (entry.socket) entry.socket.close();
      };
    },
  });
});
