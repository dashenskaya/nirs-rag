param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ServerArgs
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot

Set-Location -LiteralPath $Root

Write-Host ''
Write-Host '=== Meme Helper: подготовка и запуск ===' -ForegroundColor Cyan


# ==========================================
# 1. Проверяем .env
# ==========================================

if (-not (Test-Path -LiteralPath (Join-Path $Root '.env'))) {

    Copy-Item `
        -LiteralPath (Join-Path $Root '.env.example') `
        -Destination (Join-Path $Root '.env')

    Write-Host 'Создан .env из .env.example.' -ForegroundColor Yellow

    Write-Host 'Заполните настройки и повторите запуск.' -ForegroundColor Yellow

    exit 1
}


# ==========================================
# 2. Создаём виртуальное окружение
# ==========================================

$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $VenvPython)) {

    Write-Host '[1/5] Создаю виртуальное окружение...'

    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue

    if ($PyLauncher) {

        & $PyLauncher.Source -3 -m venv (Join-Path $Root '.venv')

    } else {

        $Python = Get-Command python -ErrorAction SilentlyContinue

        if (-not $Python) {
            throw 'Python не найден. Установите Python 3.10+.'
        }

        & $Python.Source -m venv (Join-Path $Root '.venv')
    }

    if ($LASTEXITCODE -ne 0) {
        throw 'Не удалось создать виртуальное окружение.'
    }

} else {

    Write-Host '[1/5] Виртуальное окружение уже существует.'
}


# ==========================================
# 3. Устанавливаем зависимости
# ==========================================

Write-Host '[2/5] Устанавливаю Python-зависимости...'

& $VenvPython -m pip install `
    --disable-pip-version-check `
    -r (Join-Path $Root 'requirements.txt')

if ($LASTEXITCODE -ne 0) {
    throw 'Не удалось установить зависимости.'
}


# ==========================================
# 4. Создание администратора
# ==========================================

if ($ServerArgs -contains '--create-admin') {

    Write-Host 'Создаю администратора...'

    & $VenvPython (Join-Path $Root 'run.py') @ServerArgs

    if ($LASTEXITCODE -ne 0) {
        throw 'Не удалось создать администратора.'
    }

    exit 0
}


# ==========================================
# 5. Проверяем Docker
# ==========================================

Write-Host '[3/5] Проверяю Docker Desktop...'

$Docker = Get-Command docker -ErrorAction SilentlyContinue

if (-not $Docker) {
    throw 'Docker Desktop не установлен.'
}

& docker info *> $null

if ($LASTEXITCODE -ne 0) {
    throw 'Запустите Docker Desktop.'
}

& docker compose version *> $null

if ($LASTEXITCODE -ne 0) {
    throw 'Не найден Docker Compose v2.'
}


# ==========================================
# 6. Читаем настройки .env
# ==========================================

function Read-DotEnvValue([string]$Name) {

    $Line = Get-Content `
        -LiteralPath (Join-Path $Root '.env') |
        Where-Object {
            $_ -match ('^\s*' + [regex]::Escape($Name) + '=')
        } |
        Select-Object -First 1

    if (-not $Line) {
        return ''
    }

    $Value = ($Line -split '=', 2)[1].Trim()

    if (
        $Value.Length -ge 2 -and
        (
            ($Value.StartsWith('"') -and $Value.EndsWith('"')) -or
            ($Value.StartsWith("'") -and $Value.EndsWith("'"))
        )
    ) {

        $Value = $Value.Substring(
            1,
            $Value.Length - 2
        )
    }

    return $Value
}


$MinioAccessKey = Read-DotEnvValue 'MINIO_ACCESS_KEY'

$MinioSecretKey = Read-DotEnvValue 'MINIO_SECRET_KEY'

$LlmApiBase = Read-DotEnvValue 'LLM_API_BASE'

$LlmApiKey = Read-DotEnvValue 'LLM_API_KEY'

$LlmModel = Read-DotEnvValue 'LLM_MODEL'


if (
    -not $MinioAccessKey -or
    -not $MinioSecretKey -or
    $MinioSecretKey -match 'CHANGE_THIS|replace_with'
) {

    throw 'Заполните MINIO_ACCESS_KEY и MINIO_SECRET_KEY в .env.'
}

if (-not $LlmApiBase -or -not $LlmModel) {

    throw 'Заполните LLM_API_BASE и LLM_MODEL в .env.'
}

if (
    $LlmApiBase -match '^https://api\.openai\.com' -and
    -not $LlmApiKey
) {

    throw 'Для OpenAI API необходим LLM_API_KEY.'
}


# ==========================================
# 7. Запускаем Ollama
# ==========================================

$UseLocalOllama = $LlmApiBase -match '^https?://(127\.0\.0\.1|localhost):11434(/|$)'

if ($UseLocalOllama) {

    Write-Host '[3a/5] Проверяю Ollama...'

    $OllamaReady = $false

    try {

        $null = Invoke-RestMethod `
            -Uri 'http://127.0.0.1:11434/api/tags' `
            -TimeoutSec 3

        $OllamaReady = $true

    } catch {

        $OllamaReady = $false
    }


    if (-not $OllamaReady) {

        & docker compose `
            -f (Join-Path $Root 'compose.yaml') `
            --profile local-llm up -d ollama

        if ($LASTEXITCODE -ne 0) {
            throw 'Не удалось запустить Ollama.'
        }

        for ($Attempt = 0; $Attempt -lt 90; $Attempt++) {

            try {

                $null = Invoke-RestMethod `
                    -Uri 'http://127.0.0.1:11434/api/tags' `
                    -TimeoutSec 3

                $OllamaReady = $true

                break

            } catch {

                Start-Sleep -Seconds 2
            }
        }
    }


    if (-not $OllamaReady) {
        throw 'Ollama не стала доступна.'
    }


    # Проверяем наличие модели.

    $Tags = Invoke-RestMethod `
        -Uri 'http://127.0.0.1:11434/api/tags' `
        -TimeoutSec 10

    $ModelInstalled = @(
        $Tags.models |
        Where-Object {
            $_.name -eq $LlmModel -or $_.model -eq $LlmModel
        }
    ).Count -gt 0


    if (-not $ModelInstalled) {

        Write-Host "[Ollama] Загружаю модель $LlmModel..."

        $OllamaContainer = & docker ps -a `
            --filter 'name=^/memehelper-ollama$' `
            --format '{{.Names}}'

        if ($OllamaContainer) {

            & docker exec memehelper-ollama ollama pull $LlmModel

        } else {

            $OllamaCommand = Get-Command ollama -ErrorAction SilentlyContinue

            if (-not $OllamaCommand) {
                throw 'Не найдена команда Ollama.'
            }

            & $OllamaCommand.Source pull $LlmModel
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Не удалось загрузить модель $LlmModel."
        }

    } else {

        Write-Host "[Ollama] Модель $LlmModel уже загружена."
    }
}


# ==========================================
# 8. Запускаем MinIO
# ==========================================

Write-Host '[4/5] Запускаю MinIO...'

$ExistingMinio = & docker ps -a `
    --filter 'name=^/memehelper-minio$' `
    --format '{{.Names}}'

if ($ExistingMinio) {

    $MinioRunning = & docker inspect `
        --format '{{.State.Running}}' `
        memehelper-minio 2>$null

    if ($MinioRunning -ne 'true') {

        & docker start memehelper-minio | Out-Null

        if ($LASTEXITCODE -ne 0) {
            throw 'Не удалось запустить MinIO.'
        }
    }

} else {

    & docker compose `
        -f (Join-Path $Root 'compose.yaml') `
        up -d minio

    if ($LASTEXITCODE -ne 0) {
        throw 'Не удалось запустить MinIO.'
    }
}


# ==========================================
# 9. Миграции и демонстрационные данные
# ==========================================

Write-Host '[5/5] Инициализирую базу и изображения...'

& $VenvPython -m app.backend.bootstrap

if ($LASTEXITCODE -ne 0) {
    throw 'Не удалось инициализировать базу или MinIO.'
}


# ==========================================
# 10. Запуск сервера
# ==========================================

Write-Host ''

Write-Host 'Запускаю веб-сервер...' -ForegroundColor Green

& $VenvPython (Join-Path $Root 'run.py') @ServerArgs

if ($LASTEXITCODE -ne 0) {
    throw 'Сервер завершился с ошибкой.'
}
