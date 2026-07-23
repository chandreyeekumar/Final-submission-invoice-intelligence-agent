$ErrorActionPreference = "Stop"

$directories = @(
    "app/agents",
    "app/api",
    "app/core",
    "app/db/models",
    "app/db/repositories",
    "app/schemas",
    "app/services",
    "app/workflows",
    "alembic/versions",
    "data/synthetic",
    "data/vendor_master",
    "data/vendor_templates",
    "data/public",
    "data/chroma",
    "data/runtime",
    "eval/adapters",
    "eval/reports",
    "frontend",
    "scripts",
    "tests"
)

foreach ($directory in $directories) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

$packages = @(
    "app",
    "app/agents",
    "app/api",
    "app/core",
    "app/db",
    "app/db/models",
    "app/db/repositories",
    "app/schemas",
    "app/services",
    "app/workflows",
    "eval",
    "eval/adapters",
    "tests"
)

foreach ($package in $packages) {
    New-Item -ItemType File -Force -Path (Join-Path $package "__init__.py") | Out-Null
}

Write-Host "Project folders and Python package files created successfully."