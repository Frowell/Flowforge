/**
 * Embed page — minimal shell, API key auth, single widget filling viewport.
 *
 * No navigation shell, sidebar, or header.
 * No React Flow imports. No Zustand. Minimal bundle via React.lazy.
 */

import { useParams, useSearchParams } from "react-router-dom";
import EmbedWidget from "./EmbedWidget";

export default function EmbedRoot() {
  const { widgetId } = useParams<{ widgetId: string }>();
  const [searchParams] = useSearchParams();
  const apiKey = searchParams.get("api_key");

  if (!widgetId) {
    return <EmbedError message="Missing widget ID" />;
  }

  if (!apiKey) {
    return <EmbedError message="Missing API key" />;
  }

  return (
    <div className="h-screen w-screen bg-canvas-bg">
      <EmbedWidget widgetId={widgetId} apiKey={apiKey} filterParams={Object.fromEntries(searchParams)} />
    </div>
  );
}

function EmbedError({ message }: { message: string }) {
  return (
    <div className="h-screen w-screen bg-canvas-bg flex items-center justify-center">
      <div className="text-red-400 text-sm">{message}</div>
    </div>
  );
}
