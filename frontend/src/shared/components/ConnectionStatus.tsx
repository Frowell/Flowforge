/**
 * WebSocket connection status indicator.
 *
 * Small, unobtrusive dot in the bottom-right corner.
 * Green = connected, yellow = reconnecting, red = disconnected.
 */

import { useEffect, useState } from "react";
import { cn } from "@/shared/lib/cn";
import { wsManager } from "@/shared/websocket/manager";

type ConnectionState = "connected" | "reconnecting" | "disconnected";

export default function ConnectionStatus() {
  const [state, setState] = useState<ConnectionState>("disconnected");
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    const unsubscribe = wsManager.onConnectionChange((connected) => {
      if (connected) {
        setState("connected");
        setAttempts(0);
      } else {
        setState((prev) => {
          if (prev === "connected") {
            setAttempts(1);
            return "reconnecting";
          }
          setAttempts((a) => a + 1);
          return "reconnecting";
        });
      }
    });

    return unsubscribe;
  }, []);

  const dotColor = {
    connected: "bg-emerald-400",
    reconnecting: "bg-yellow-400 animate-pulse",
    disconnected: "bg-red-400",
  }[state];

  const label = {
    connected: "Connected",
    reconnecting: `Reconnecting${attempts > 0 ? ` (${attempts})` : ""}`,
    disconnected: "Disconnected",
  }[state];

  return (
    <div className="fixed bottom-3 right-3 z-40 flex items-center gap-1.5 px-2 py-1 rounded-full bg-black/40 backdrop-blur-sm border border-white/5">
      <span className={cn("inline-block w-1.5 h-1.5 rounded-full", dotColor)} />
      <span className="text-[10px] text-white/40">{label}</span>
    </div>
  );
}
