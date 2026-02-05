/**
 * Union config panel — shows input alignment status.
 * UNION ALL is implicit; no config to set.
 */

import { useNodeInputSchemas } from "../hooks/useSchemaEngine";

interface Props {
  nodeId: string;
}

export default function UnionPanel({ nodeId }: Props) {
  const inputSchemas = useNodeInputSchemas(nodeId);
  const leftSchema = inputSchemas[0] ?? [];
  const rightSchema = inputSchemas[1] ?? [];

  const leftNames = new Set(leftSchema.map((c) => c.name));
  const rightNames = new Set(rightSchema.map((c) => c.name));

  const allNames = Array.from(new Set([...leftNames, ...rightNames]));

  return (
    <div className="space-y-3">
      <p className="text-xs text-white/50">
        Combines both inputs with UNION ALL. Columns are matched by name.
      </p>

      {allNames.length > 0 && (
        <div>
          <label className="text-xs text-white/50 block mb-1">Column Alignment</label>
          <div className="space-y-0.5">
            {allNames.map((name) => {
              const inLeft = leftNames.has(name);
              const inRight = rightNames.has(name);
              const matched = inLeft && inRight;
              return (
                <div key={name} className="flex items-center gap-2 text-xs">
                  <span className={matched ? "text-green-400" : "text-yellow-400"}>
                    {matched ? "✓" : "!"}
                  </span>
                  <span className="text-white/70">{name}</span>
                  {!matched && (
                    <span className="text-white/30">({inLeft ? "left only" : "right only"})</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {allNames.length === 0 && (
        <p className="text-xs text-white/30">Connect two inputs to see column alignment.</p>
      )}
    </div>
  );
}
