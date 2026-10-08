param([string]$Output = "backups/repaircafe.dump")
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path (Split-Path $Output) | Out-Null
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/repaircafe.dump'
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed' }
$container = docker compose ps -q db
if (-not $container) { throw 'Database container is not running' }
docker cp "${container}:/tmp/repaircafe.dump" $Output
if ($LASTEXITCODE -ne 0) { throw 'Copying backup failed' }
Write-Output "Backup saved to $Output"
