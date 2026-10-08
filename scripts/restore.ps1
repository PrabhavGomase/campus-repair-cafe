param([Parameter(Mandatory=$true)][string]$InputFile)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $InputFile)) { throw 'Backup file not found' }
$container = docker compose ps -q db
if (-not $container) { throw 'Database container is not running' }
docker cp $InputFile "${container}:/tmp/repaircafe-restore.dump"
if ($LASTEXITCODE -ne 0) { throw 'Copying backup failed' }
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner /tmp/repaircafe-restore.dump'
if ($LASTEXITCODE -ne 0) { throw 'pg_restore failed' }
Write-Output 'Database restored. Restart the web service before using it.'
