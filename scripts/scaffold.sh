#!/usr/bin/env bash
set -euo pipefail

echo "📁 Creating backend structure..."

# ── Backend ───────────────────────────────────────────────────────────
mkdir -p backend/app/{api/routes,core,models,schemas,services,worker/tasks}
mkdir -p backend/tests/{api,services,worker}
mkdir -p backend/alembic/versions

# Backend: Entry point
cat > backend/app/main.py << 'PYTHON'
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import workflows, executions, nodes, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    # Startup: initialize connections, warm caches
    yield
    # Shutdown: cleanup


app = FastAPI(
    title="FlowForge",
    description="Visual data workflow engine — Alteryx reimagined",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, tags=["health"])
app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["workflows"])
app.include_router(executions.router, prefix="/api/v1/executions", tags=["executions"])
app.include_router(nodes.router, prefix="/api/v1/nodes", tags=["nodes"])
PYTHON

# Backend: Config
cat > backend/app/core/config.py << 'PYTHON'
import json
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "dev-secret-change-in-prod"

    # Database
    database_url: str = "postgresql+asyncpg://flowforge:flowforge@db:5432/flowforge"
    database_url_sync: str = "postgresql://flowforge:flowforge@db:5432/flowforge"

    # Redis
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Handle JSON string from env var
        if isinstance(self.cors_origins, str):
            self.cors_origins = json.loads(self.cors_origins)


settings = Settings()
PYTHON

# Backend: Database
cat > backend/app/core/database.py << 'PYTHON'
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=settings.app_env == "development")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
PYTHON

# Backend: Celery worker
cat > backend/app/worker/__init__.py << 'PYTHON'
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "flowforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.worker.tasks.workflow.*": {"queue": "workflows"},
        "app.worker.tasks.data_processing.*": {"queue": "data_processing"},
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.worker.tasks"])
PYTHON

# Backend: Example task
cat > backend/app/worker/tasks/__init__.py << 'PYTHON'
PYTHON

cat > backend/app/worker/tasks/workflow.py << 'PYTHON'
"""
Workflow execution tasks.

Each node type in the React Flow canvas maps to a Celery task.
The workflow executor resolves the DAG topology and dispatches
tasks in dependency order.
"""
import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="workflow.execute")
def execute_workflow(self, workflow_id: str, execution_id: str):
    """Execute an entire workflow by resolving its DAG and running nodes."""
    logger.info(f"Starting workflow {workflow_id} (execution: {execution_id})")

    # TODO: Load workflow graph from DB
    # TODO: Topological sort of nodes
    # TODO: Execute each node in order, passing dataframes between them
    # TODO: Update execution status via WebSocket

    return {"status": "completed", "workflow_id": workflow_id}


@celery_app.task(bind=True, name="workflow.execute_node")
def execute_node(self, node_type: str, node_config: dict, input_data: dict):
    """Execute a single node in the workflow."""
    logger.info(f"Executing node: {node_type}")

    # Node type dispatch — this is where Alteryx tool equivalents live
    # TODO: Implement node processors (Input, Filter, Join, Formula, Output, etc.)

    return {"status": "completed", "output_schema": {}}
PYTHON

# Backend: Route stubs
for route in workflows executions nodes health; do
  if [ "$route" = "health" ]; then
    cat > "backend/app/api/routes/${route}.py" << 'PYTHON'
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "flowforge"}
PYTHON
  else
    cat > "backend/app/api/routes/${route}.py" << PYTHON
from fastapi import APIRouter

router = APIRouter()

# TODO: Implement ${route} CRUD endpoints
PYTHON
  fi
done

# Backend: Init files
touch backend/app/__init__.py
touch backend/app/api/__init__.py
touch backend/app/api/routes/__init__.py
touch backend/app/core/__init__.py
touch backend/app/models/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/services/__init__.py
touch backend/tests/__init__.py
touch backend/tests/api/__init__.py
touch backend/tests/services/__init__.py
touch backend/tests/worker/__init__.py

# Backend: pyproject.toml
cat > backend/pyproject.toml << 'TOML'
[build-system]
requires = ["setuptools>=75.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "flowforge"
version = "0.1.0"
description = "Visual data workflow engine"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "celery[redis]>=5.4.0",
    "redis>=5.2.0",
    "pandas>=2.2.0",
    "polars>=1.14.0",
    "pyarrow>=18.0.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "orjson>=3.10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "SIM"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
TOML

# Backend: Alembic config
cat > backend/alembic.ini << 'INI'
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://flowforge:flowforge@db:5432/flowforge

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
INI

cat > backend/alembic/env.py << 'PYTHON'
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.core.config import settings
from app.core.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=settings.database_url_sync, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
PYTHON

cat > backend/alembic/script.py.mako << 'MAKO'
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
MAKO

echo ""
echo "📁 Creating frontend structure..."

# ── Frontend ──────────────────────────────────────────────────────────
mkdir -p frontend/src/{components/{canvas,nodes,panels,ui},hooks,lib,stores,types}
mkdir -p frontend/public

# Frontend: package.json
cat > frontend/package.json << 'JSON'
{
  "name": "flowforge-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "lint": "eslint .",
    "format": "prettier --write ."
  },
  "dependencies": {
    "@xyflow/react": "^12.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zustand": "^5.0.0",
    "@tanstack/react-query": "^5.60.0",
    "lucide-react": "^0.460.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.6.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@eslint/js": "^9.15.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.15.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "eslint-plugin-react-refresh": "^0.4.14",
    "globals": "^15.12.0",
    "postcss": "^8.4.49",
    "prettier": "^3.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "~5.6.0",
    "typescript-eslint": "^8.15.0",
    "vite": "^6.0.0",
    "vitest": "^2.1.0"
  }
}
JSON

# Frontend: Vite config
cat > frontend/vite.config.ts << 'TS'
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
TS

# Frontend: TypeScript config
cat > frontend/tsconfig.json << 'JSON'
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
JSON

# Frontend: Tailwind
cat > frontend/tailwind.config.js << 'JS'
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: {
          bg: "#1a1a2e",
          grid: "#16213e",
          node: "#0f3460",
          accent: "#e94560",
        },
      },
    },
  },
  plugins: [],
};
JS

cat > frontend/postcss.config.js << 'JS'
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
JS

# Frontend: Index HTML
cat > frontend/index.html << 'HTML'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FlowForge — Visual Data Workflows</title>
  </head>
  <body class="bg-canvas-bg text-white antialiased">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
HTML

# Frontend: Main entry
cat > frontend/src/main.tsx << 'TSX'
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
TSX

# Frontend: App
cat > frontend/src/App.tsx << 'TSX'
import { ReactFlowProvider } from "@xyflow/react";
import { WorkflowCanvas } from "@/components/canvas/WorkflowCanvas";
import "@xyflow/react/dist/style.css";

export default function App() {
  return (
    <div className="h-screen w-screen flex flex-col">
      {/* Header */}
      <header className="h-12 bg-canvas-node border-b border-white/10 flex items-center px-4 shrink-0">
        <h1 className="text-sm font-semibold tracking-wide">
          ⚡ FlowForge
        </h1>
      </header>

      {/* Canvas */}
      <main className="flex-1 relative">
        <ReactFlowProvider>
          <WorkflowCanvas />
        </ReactFlowProvider>
      </main>
    </div>
  );
}
TSX

# Frontend: Canvas component
cat > frontend/src/components/canvas/WorkflowCanvas.tsx << 'TSX'
import { useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type OnConnect,
  BackgroundVariant,
} from "@xyflow/react";

const initialNodes = [
  {
    id: "input-1",
    type: "default",
    position: { x: 100, y: 200 },
    data: { label: "📥 CSV Input" },
    style: { background: "#0f3460", color: "white", border: "1px solid #e94560" },
  },
  {
    id: "transform-1",
    type: "default",
    position: { x: 400, y: 200 },
    data: { label: "🔄 Filter" },
    style: { background: "#0f3460", color: "white", border: "1px solid #53a8b6" },
  },
  {
    id: "output-1",
    type: "default",
    position: { x: 700, y: 200 },
    data: { label: "📤 Output" },
    style: { background: "#0f3460", color: "white", border: "1px solid #79c99e" },
  },
];

const initialEdges = [
  { id: "e1-2", source: "input-1", target: "transform-1", animated: true },
  { id: "e2-3", source: "transform-1", target: "output-1", animated: true },
];

export function WorkflowCanvas() {
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      fitView
      className="bg-canvas-bg"
    >
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#ffffff15" />
      <Controls className="!bg-canvas-node !border-white/10 !text-white [&>button]:!bg-canvas-node [&>button]:!text-white [&>button]:!border-white/10" />
      <MiniMap
        className="!bg-canvas-node !border-white/10"
        nodeColor="#e94560"
        maskColor="rgba(0,0,0,0.5)"
      />
    </ReactFlow>
  );
}
TSX

# Frontend: Global styles
cat > frontend/src/index.css << 'CSS'
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family:
    "Inter",
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Roboto,
    sans-serif;
}

/* React Flow overrides for dark theme */
.react-flow__attribution {
  display: none !important;
}
CSS

# Frontend: Type stubs
cat > frontend/src/types/workflow.ts << 'TS'
/**
 * Core workflow types — mirrors backend schemas.
 *
 * These types represent the React Flow graph structure
 * that gets serialized and sent to the backend for execution.
 */

export type NodeCategory = "input" | "transform" | "join" | "output" | "formula" | "filter" | "aggregate";

export interface WorkflowNodeData {
  label: string;
  category: NodeCategory;
  config: Record<string, unknown>;
  /** Column schema after this node executes */
  outputSchema?: ColumnSchema[];
}

export interface ColumnSchema {
  name: string;
  dtype: "string" | "int64" | "float64" | "bool" | "datetime" | "object";
  nullable: boolean;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  nodes: WorkflowNodeData[];
  edges: WorkflowEdge[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
}

export interface ExecutionStatus {
  id: string;
  workflow_id: string;
  status: "pending" | "running" | "completed" | "failed";
  started_at?: string;
  completed_at?: string;
  node_statuses: Record<string, NodeExecutionStatus>;
}

export interface NodeExecutionStatus {
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  started_at?: string;
  completed_at?: string;
  rows_processed?: number;
  error?: string;
}
TS

# Frontend: Prettier config
cat > frontend/.prettierrc << 'JSON'
{
  "semi": true,
  "trailingComma": "all",
  "singleQuote": false,
  "printWidth": 100,
  "tabWidth": 2
}
JSON

echo ""
echo "📁 Creating shared config files..."

# ── Root config files ─────────────────────────────────────────────────

cat > .gitignore << 'GIT'
# Dependencies
node_modules/
__pycache__/
*.egg-info/
.eggs/

# Build
dist/
build/
*.pyc
*.pyo

# IDE
.vscode/
!.vscode/settings.json
.idea/

# Environment
.env
.env.local
*.env

# Data
*.csv
*.xlsx
*.parquet
uploads/
outputs/

# Caches
.ruff_cache/
.mypy_cache/
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
GIT

cat > .pre-commit-config.yaml << 'YAML'
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
YAML

echo ""
echo "✅ Scaffold complete!"
