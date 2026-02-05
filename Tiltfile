# FlowForge Development Orchestration
# Run: tilt up
# UI:  http://localhost:10350

k8s_namespace('flowforge')

# Apply manifests via kustomize
k8s_yaml(kustomize('k8s/overlays/dev'))

# ─── Infrastructure (public images, no builds) ─────────────────────
k8s_resource('redpanda',
  labels=['infra'],
  port_forwards=['9092:9092', '9644:9644'])

k8s_resource('redpanda-console',
  labels=['infra'],
  port_forwards=['8180:8080'],
  resource_deps=['redpanda'])

k8s_resource('clickhouse',
  labels=['infra'],
  port_forwards=['8123:8123', '9000:9000'])

k8s_resource('materialize',
  labels=['infra'],
  port_forwards=['6875:6875'],
  resource_deps=['redpanda'])

k8s_resource('redis',
  labels=['infra'],
  port_forwards=['6379:6379'])

k8s_resource('postgres',
  labels=['infra'],
  port_forwards=['5432:5432'])

# ─── Backend (live sync, no image rebuild on code change) ──────────
docker_build(
  'flowforge-registry:5111/flowforge-backend',
  context='.',
  dockerfile='backend/Dockerfile',
  live_update=[
    sync('backend/app/', '/app/app/'),
    run('pip install -r /app/requirements.txt',
        trigger=['backend/requirements.txt']),
  ],
)

k8s_resource('backend',
  labels=['app'],
  port_forwards=['8000:8000'],
  resource_deps=['postgres', 'clickhouse', 'redis', 'materialize'])

# ─── Frontend (live sync, Vite HMR handles reload) ────────────────
docker_build(
  'flowforge-registry:5111/flowforge-frontend',
  context='.',
  dockerfile='frontend/Dockerfile',
  live_update=[
    sync('frontend/src/', '/app/src/'),
    sync('frontend/public/', '/app/public/'),
    sync('frontend/index.html', '/app/index.html'),
    run('npm install', trigger=['frontend/package.json']),
  ],
)

k8s_resource('frontend',
  labels=['app'],
  port_forwards=['5173:5173'])

# ─── Data Generator ───────────────────────────────────────────────
docker_build(
  'flowforge-registry:5111/flowforge-generator',
  context='pipeline/generator/',
  dockerfile='pipeline/generator/Dockerfile',
  live_update=[
    sync('pipeline/generator/', '/app/'),
  ],
)

k8s_resource('data-generator',
  labels=['pipeline'],
  resource_deps=['redpanda'])

# ─── Bytewax ─────────────────────────────────────────────────────
docker_build(
  'flowforge-registry:5111/flowforge-bytewax',
  context='pipeline/bytewax/',
  dockerfile='pipeline/bytewax/Dockerfile',
  live_update=[
    sync('pipeline/bytewax/flows/', '/app/flows/'),
  ],
)

k8s_resource('bytewax-vwap',
  labels=['pipeline'],
  resource_deps=['redpanda', 'clickhouse', 'redis'])

# ─── Airflow ─────────────────────────────────────────────────────
k8s_resource('airflow',
  labels=['pipeline'],
  port_forwards=['8280:8080'],
  resource_deps=['postgres', 'clickhouse'])

# ─── One-Off Jobs (manual trigger only) ──────────────────────────
local_resource(
  'init-materialize',
  cmd='kubectl create -f k8s/base/pipeline/init-materialize-job.yaml --namespace flowforge 2>/dev/null || kubectl replace --force -f k8s/base/pipeline/init-materialize-job.yaml --namespace flowforge',
  labels=['jobs'],
  auto_init=False,
  resource_deps=['materialize', 'redpanda'])

local_resource(
  'seed-historical',
  cmd='kubectl exec deploy/backend -n flowforge -- python /workspace/scripts/seed_historical.py',
  labels=['jobs'],
  auto_init=False,
  resource_deps=['backend', 'clickhouse', 'redis'])

local_resource(
  'dbt-run',
  cmd='kubectl exec deploy/airflow -n flowforge -- dbt run --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt',
  labels=['jobs'],
  auto_init=False,
  resource_deps=['airflow', 'clickhouse'])

local_resource(
  'health-check',
  cmd='kubectl exec deploy/backend -n flowforge -- bash /workspace/scripts/check-connectivity.sh',
  labels=['jobs'],
  auto_init=False)
