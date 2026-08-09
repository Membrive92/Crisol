<#
.SYNOPSIS
    Levanta el entorno de desarrollo completo de Crisol.

.DESCRIPTION
    Arranca, en orden y comprobando cada paso: los contenedores (Postgres,
    MinIO, Ollama), las migraciones y, en ventanas separadas, el backend
    (FastAPI) y la web (Next.js). Opcionalmente el móvil (Expo).

    Cada servicio va en su propia ventana para que sus logs se lean por
    separado y se pueda reiniciar uno sin matar el resto.

    DOS COSAS QUE ESTE SCRIPT RESUELVE Y CONVIENE SABER:

    1. El puerto del backend NO está hardcodeado: se DERIVA de
       `apps/web/.env.local` (BACKEND_ORIGIN). El repo tiene tres valores
       distintos —`next.config.mjs` dice 8001, el Makefile arranca uvicorn en
       8000 y `.env.local` dice 8002— y el que manda en desarrollo es el
       último, porque Next.js carga `.env.local` por encima del default del
       config. Arrancar uvicorn en otro puerto deja la web proxeando al vacío:
       los cambios del backend "no aparecen" y no hay ningún error que lo diga.

    2. Comprueba si el puerto ya está ocupado ANTES de arrancar. En Windows es
       fácil dejar un uvicorn zombi de una sesión anterior: el nuevo falla al
       bindear, la ventana se cierra en un parpadeo, y la web sigue hablando
       con el proceso viejo —que sirve código antiguo—.

    LIBERACIÓN AUTOMÁTICA DE PUERTOS

    Antes de arrancar revisa los puertos que necesita y los libera. Pero no mata
    a ciegas lo que haya escuchando: distingue si el proceso es DEL PROYECTO
    (por su línea de comandos o la de sus padres) o ajeno.

      - Del proyecto  -> lo cierra sin preguntar. Es un resto de otra sesión.
      - Ajeno         -> lo dice y PREGUNTA. Podría ser otro proyecto tuyo en
                         el 3000, o un Postgres del sistema en el 5432, y
                         matarlo por sorpresa sería peor que no arrancar.

    Los puertos de los contenedores (5432, 9000, 9001, 11434) se revisan pero
    NUNCA se matan solos: si los ocupa algo que no es nuestro contenedor, lo más
    probable es que sea un servicio del sistema. Se avisa y se decide a mano.

.PARAMETER Mobile
    Arranca también Expo (móvil) en su propia ventana.

.PARAMETER Force
    No pregunta: libera los puertos de la app aunque el proceso sea ajeno.

.PARAMETER NoKill
    No libera nada. Si un puerto está ocupado, aborta (comportamiento antiguo).

.PARAMETER NoBrowser
    No abre el navegador al terminar.

.PARAMETER SkipMigrations
    Se salta `alembic upgrade head`.

.PARAMETER Stop
    En vez de arrancar, para los contenedores y los procesos de desarrollo.

.EXAMPLE
    .\dev.ps1
    Levanta contenedores + backend + web y abre el navegador.

.EXAMPLE
    .\dev.ps1 -Mobile
    Igual, y además Expo.

.EXAMPLE
    .\dev.ps1 -Stop
    Para todo lo que este script levantó.
#>

[CmdletBinding()]
param(
    [switch]$Mobile,
    [switch]$NoBrowser,
    [switch]$SkipMigrations,
    [switch]$Stop,
    [switch]$Force,
    [switch]$NoKill
)

$ErrorActionPreference = 'Stop'
$RepoRoot = $PSScriptRoot
$WebPort = 3000
$ExpoPort = 8081

# El venv del backend, NO el `python` del PATH. Son cosas distintas y el del
# PATH puede tener otra versión y otras dependencias: verificar contra el
# intérprete equivocado da un verde que no vale (lección PHASE-44.6).
$VenvPython = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'

# ─────────────────────────────────────────────────────────────────────────
# Salida
# ─────────────────────────────────────────────────────────────────────────

function Invoke-Quiet {
    <#
    .SYNOPSIS
        Ejecuta un comando nativo silenciando su stderr, sin abortar el script.
    .DESCRIPTION
        En PowerShell 5.1, si se REDIRIGE la stderr de un ejecutable nativo
        (`2>$null`, `2>&1`), cada línea se envuelve en un `ErrorRecord`. Con
        `$ErrorActionPreference = 'Stop'` —que este script activa arriba— el
        primero de esos registros **termina el script**, aunque el comando haya
        hecho su trabajo. La trampa es que redirigir para «no hacer ruido» es
        justo lo que lo vuelve fatal: sin redirección, la misma stderr va a la
        consola y no pasa nada.

        Mordió de verdad al parar el entorno: `taskkill /T` mata el árbol, así
        que cuando el bucle siguiente intentaba matar a los hijos uno a uno,
        `taskkill` escribía «no se encontró el proceso» —el caso NORMAL— y el
        script moría ahí, dejando la web viva y los contenedores en pie.

        Los tres sitios que redirigían están en caminos de «algo va mal»
        (parar procesos, Docker caído, contenedor inexistente): justo donde el
        manejo amable existía para dar un mensaje, y donde en su lugar se caía.
    .OUTPUTS
        Las líneas de stdout. El código de salida queda en `$script:QuietExit`.
    #>
    param([scriptblock]$Command)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Command 2>$null
        $script:QuietExit = $LASTEXITCODE
        return $output
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Write-Step  { param([string]$m) Write-Host "`n=> $m" -ForegroundColor Cyan }
function Write-Ok    { param([string]$m) Write-Host "   OK  $m" -ForegroundColor Green }
function Write-Warn2 { param([string]$m) Write-Host "   !   $m" -ForegroundColor Yellow }
function Write-Err   { param([string]$m) Write-Host "   X   $m" -ForegroundColor Red }

# ─────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────

function Get-BackendPort {
    <#
    .SYNOPSIS
        Puerto del backend, derivado de BACKEND_ORIGIN.
    .DESCRIPTION
        Fuente de verdad: `apps/web/.env.local`, que es lo que Next.js usa
        para el rewrite `/api/* -> backend`. Si el fichero no existe se cae al
        default de `next.config.mjs` (8001) y se avisa, porque entonces el
        valor efectivo depende de qué lea Next.js y no de este script.
    #>
    $envLocal = Join-Path $RepoRoot 'apps\web\.env.local'
    if (Test-Path $envLocal) {
        $line = Select-String -Path $envLocal -Pattern '^\s*BACKEND_ORIGIN\s*=\s*(.+)$' |
                Select-Object -First 1
        if ($line) {
            $origin = $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
            try {
                $parsed = [System.Uri]$origin
                if ($parsed.Port -gt 0) {
                    return [pscustomobject]@{ Port = $parsed.Port; Source = 'apps/web/.env.local' }
                }
            } catch {
                Write-Warn2 "BACKEND_ORIGIN no es una URL válida: '$origin'"
            }
        }
    }
    Write-Warn2 "No hay BACKEND_ORIGIN en apps/web/.env.local; asumo 8001 (default de next.config.mjs)."
    return [pscustomobject]@{ Port = 8001; Source = 'default de next.config.mjs' }
}

function Get-PortOwner {
    <#
    .SYNOPSIS
        Quién escucha en un puerto, o $null si está libre.
    .DESCRIPTION
        `Alive` distingue dos situaciones que se ven igual en la tabla TCP y
        piden respuestas opuestas: un proceso VIVO ocupando el puerto (hay que
        pararlo) frente a un socket cuyo dueño ya murió y que Windows todavía
        no ha reciclado (sólo hay que esperar). Aconsejar `Stop-Process` sobre
        un PID que ya no existe manda al usuario a perseguir un fantasma.
    #>
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if ($null -eq $conn) { return $null }
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    if ($proc) {
        return [pscustomobject]@{ Pid = $conn.OwningProcess; Name = $proc.ProcessName; Alive = $true }
    }
    return [pscustomobject]@{ Pid = $conn.OwningProcess; Name = 'proceso ya terminado'; Alive = $false }
}

#: Marcadores que identifican un proceso como "de este proyecto" por su línea
#: de comandos. La ruta del repo cubre casi todo; los demás están porque el
#: gestor de paquetes y el bundler se lanzan desde la raíz y no siempre la
#: repiten en los argumentos.
$script:ProjectMarkers = @(
    'app.main:app',
    'crisol',
    'turbo run dev',
    'next dev',
    'expo start'
)

function Test-ProjectProcess {
    <#
    .SYNOPSIS
        ¿El proceso que ocupa el puerto pertenece a este proyecto?
    .DESCRIPTION
        Mira su línea de comandos y, si no concluye, SUBE POR SUS PADRES. Hace
        falta: el worker de `uvicorn --reload` se lanza como
        `python.exe -c "from multiprocessing..."`, que no menciona ni el repo ni
        la app. Sin mirar al padre, el proceso más característico del proyecto
        parecería ajeno y el script pediría permiso para matar lo que él mismo
        había arrancado.

        Un socket cuyo dueño ya murió se considera del proyecto: es el zombi de
        uvicorn descrito en `Stop-PortHolder`.
    #>
    param([int]$ProcessId, [int]$MaxDepth = 4)

    $currentId = $ProcessId
    for ($depth = 0; $depth -lt $MaxDepth; $depth++) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $currentId" -ErrorAction SilentlyContinue
        if ($null -eq $proc) {
            # Sin proceso: o es el huérfano de uvicorn (nuestro), o el padre ya
            # no existe y no se puede seguir subiendo.
            return ($depth -eq 0)
        }
        $cmd = $proc.CommandLine
        if ($cmd) {
            $lower = $cmd.ToLowerInvariant()
            if ($lower.Contains($RepoRoot.ToLowerInvariant())) { return $true }
            foreach ($marker in $script:ProjectMarkers) {
                if ($lower.Contains($marker.ToLowerInvariant())) { return $true }
            }
        }
        if ($proc.ParentProcessId -le 4) { return $false }  # 0/4 = kernel
        $currentId = [int]$proc.ParentProcessId
    }
    return $false
}

function Resolve-PortConflict {
    <#
    .SYNOPSIS
        Deja libre un puerto de la app, preguntando sólo cuando toca.
    .OUTPUTS
        [bool] $true si el puerto quedó (o ya estaba) libre.
    #>
    param([int]$Port, [string]$Label)

    $owner = Get-PortOwner -Port $Port
    if ($null -eq $owner) { return $true }

    $mine = Test-ProjectProcess -ProcessId $owner.Pid

    if ($NoKill) {
        Write-Err "Puerto $Port ($Label) ocupado por '$($owner.Name)' (PID $($owner.Pid)). -NoKill activo, no lo toco."
        return $false
    }

    if (-not $mine -and -not $Force) {
        Write-Warn2 "Puerto $Port ($Label) ocupado por '$($owner.Name)' (PID $($owner.Pid)), que NO parece de este proyecto."
        if (-not [Environment]::UserInteractive) {
            Write-Err 'Sesión no interactiva: no puedo preguntar. Usa -Force si de verdad quieres cerrarlo.'
            return $false
        }
        $answer = Read-Host "       ¿Lo cierro igualmente? (s/N)"
        if ($answer -notmatch '^[sSyY]') {
            Write-Err "Puerto $Port sin liberar. Ciérralo tú o usa otro puerto."
            return $false
        }
    }

    if ($mine) {
        Write-Warn2 "Puerto $Port ($Label) ocupado por un resto del proyecto (PID $($owner.Pid)); lo cierro."
    }

    if (Stop-PortHolder -Port $Port) {
        Write-Ok "Puerto $Port liberado."
        return $true
    }
    Write-Err "No se pudo liberar el puerto $Port. Comprueba con:"
    Write-Host "         Get-NetTCPConnection -LocalPort $Port -State Listen" -ForegroundColor Yellow
    return $false
}

#: Procesos por los que Docker Desktop publica los puertos de un contenedor.
#: `wslrelay` y `wslhost` son los del backend WSL2, que es el habitual en
#: Windows: sin ellos, los cuatro puertos de infraestructura se reportarían como
#: "ocupados por algo que no es Docker" en cada arranque correcto. Un aviso que
#: siempre salta y siempre miente entrena a ignorar los avisos de verdad.
$script:DockerHostProcesses = @(
    'wslrelay', 'wslhost', 'com.docker.backend', 'Docker Desktop Backend',
    'vpnkit', 'dockerd', 'com.docker.service'
)

function Show-InfraPortDiagnosis {
    <#
    .SYNOPSIS
        Explica por qué pudo fallar `docker compose up`, mirando sus puertos.
    .DESCRIPTION
        Sólo se llama cuando compose YA ha fallado, no en el camino feliz:
        avisar de estos puertos cuando todo va bien es ruido garantizado,
        porque el caso normal es justo que estén ocupados — por Docker.

        Nunca mata nada. Un Postgres del sistema en el 5432 no es un resto de
        esta app y puede tener datos detrás.
    #>
    $ports = @()
    $ports += @{ Port = 5432;  Label = 'Postgres' }
    $ports += @{ Port = 9000;  Label = 'MinIO API' }
    $ports += @{ Port = 9001;  Label = 'MinIO consola' }
    $ports += @{ Port = 11434; Label = 'Ollama' }

    $found = $false
    foreach ($p in $ports) {
        $owner = Get-PortOwner -Port $p.Port
        if ($null -eq $owner) { continue }
        if ($script:DockerHostProcesses -contains $owner.Name) { continue }
        $found = $true
        Write-Warn2 "$($p.Label) ($($p.Port)): lo ocupa '$($owner.Name)' (PID $($owner.Pid)), que no es Docker."
    }
    if ($found) {
        Write-Host '       Ése es probablemente el motivo del fallo: el contenedor no puede publicar' -ForegroundColor Yellow
        Write-Host '       su puerto. No lo cierro por mi cuenta — puede ser un servicio del sistema' -ForegroundColor Yellow
        Write-Host '       con datos detrás.' -ForegroundColor Yellow
    }
}

function Stop-PortHolder {
    <#
    .SYNOPSIS
        Libera un puerto de verdad: mata el árbol y recoge huérfanos.
    .DESCRIPTION
        `uvicorn --reload` arranca un supervisor que crea el socket y un worker
        hijo. Matar sólo al dueño del socket deja vivo al hijo, que sigue
        reteniendo el puerto — y la tabla TCP sigue mostrando el PID del padre,
        ya muerto. El resultado es el «listener zombi» clásico de Windows: el
        arranque siguiente falla al bindear, su ventana se cierra de golpe, y la
        web queda hablando con un backend viejo que nadie sabe que sigue ahí.
        Verificado en esta máquina: PID 39500 (supervisor) muerto, PID 17128
        (worker, `ParentProcessId = 39500`) vivo y con el puerto cogido.

        Por eso se mata el ÁRBOL (`taskkill /T`) y, si el dueño ya no existe, se
        buscan los hijos que quedaron colgando de él.
    .OUTPUTS
        [bool] $true si el puerto quedó libre.
    #>
    param([int]$Port, [int]$TimeoutSeconds = 20)

    $owner = Get-PortOwner -Port $Port
    if ($null -eq $owner) { return $true }

    # Hijos del dueño (vivo o muerto): son los que retienen el socket heredado.
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($owner.Pid)" -ErrorAction SilentlyContinue)

    if ($owner.Alive) {
        # /T mata también los descendientes; /F sin contemplaciones.
        Invoke-Quiet { taskkill /PID $owner.Pid /T /F } | Out-Null
    }
    # Los hijos ya suelen estar muertos por el /T de arriba: aquí se recogen los
    # que quedaron colgando de un dueño que ya no existe. Que `taskkill` no los
    # encuentre es lo ESPERADO, no un fallo — por eso va por `Invoke-Quiet`.
    foreach ($child in $children) {
        if (Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue) {
            Invoke-Quiet { taskkill /PID $child.ProcessId /T /F } | Out-Null
        }
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($null -eq (Get-PortOwner -Port $Port)) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Start-DevWindow {
    <#
    .SYNOPSIS
        Abre una ventana de PowerShell persistente ejecutando un comando.
    #>
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    $script = @"
`$host.UI.RawUI.WindowTitle = '$Title'
Set-Location '$WorkingDirectory'
Write-Host '--- $Title ---' -ForegroundColor Cyan
$Command
Write-Host ''
Write-Host 'El proceso ha terminado. Esta ventana queda abierta para que leas el error.' -ForegroundColor Yellow
"@
    Start-Process -FilePath 'powershell.exe' `
                  -ArgumentList '-NoExit', '-NoProfile', '-Command', $script `
                  -WorkingDirectory $WorkingDirectory | Out-Null
}

function Wait-ForUrl {
    <#
    .SYNOPSIS
        Espera a que una URL responda. Devuelve $true si respondió a tiempo.
    #>
    param([string]$Url, [int]$TimeoutSeconds = 90, [string]$Label = 'servicio')
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            return $true
        } catch {
            Start-Sleep -Milliseconds 800
        }
    }
    Write-Warn2 "$Label no respondió en $TimeoutSeconds s ($Url). Mira su ventana."
    return $false
}

function Wait-ForContainerHealth {
    <#
    .SYNOPSIS
        Espera al healthcheck de un contenedor en vez de dormir a ciegas.
    .DESCRIPTION
        Postgres acepta conexiones bastante después de que el contenedor
        exista, así que `docker compose up -d` + migraciones falla si no se
        espera. Un `Start-Sleep` fijo sería adivinar; el healthcheck ya está
        definido en docker-compose.yml.
    #>
    param([string]$Container, [int]$TimeoutSeconds = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        # Mientras el contenedor no existe todavía, `docker inspect` escribe en
        # stderr — que es el caso normal en los primeros segundos, no un fallo.
        $status = Invoke-Quiet {
            docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $Container
        }
        if ($script:QuietExit -eq 0) {
            if ($status -eq 'healthy') { return $true }
            # Un contenedor sin healthcheck definido (Ollama) no se puede
            # esperar así: se da por bueno en cuanto existe.
            if ($status -eq 'none') { return $true }
        }
        Start-Sleep -Milliseconds 1000
    }
    return $false
}

# ─────────────────────────────────────────────────────────────────────────
# Parada
# ─────────────────────────────────────────────────────────────────────────

function Invoke-StopAll {
    Write-Step 'Parando procesos de desarrollo'
    $backend = Get-BackendPort
    $targets = @()
    $targets += @{ Port = $backend.Port; Label = 'backend' }
    $targets += @{ Port = $WebPort;      Label = 'web' }
    $targets += @{ Port = $ExpoPort;     Label = 'expo' }

    foreach ($p in $targets) {
        $owner = Get-PortOwner -Port $p.Port
        if ($null -eq $owner) {
            Write-Ok "$($p.Label): nada escuchando en $($p.Port)."
            continue
        }
        if (Stop-PortHolder -Port $p.Port) {
            Write-Ok "$($p.Label): puerto $($p.Port) liberado."
        } else {
            Write-Warn2 "$($p.Label): el puerto $($p.Port) sigue ocupado. Comprueba con:"
            Write-Host "         Get-NetTCPConnection -LocalPort $($p.Port) -State Listen" -ForegroundColor Yellow
        }
    }

    Write-Step 'Parando contenedores'
    Set-Location $RepoRoot
    docker compose down
    if ($LASTEXITCODE -eq 0) { Write-Ok 'Contenedores parados.' }
    else { Write-Warn2 'docker compose down devolvió error.' }

    Write-Host "`nEntorno parado.`n" -ForegroundColor Green
}

# ─────────────────────────────────────────────────────────────────────────
# Principal
# ─────────────────────────────────────────────────────────────────────────

if ($Stop) {
    Invoke-StopAll
    return
}

Write-Host ''
Write-Host '  Crisol — entorno de desarrollo' -ForegroundColor White
Write-Host '  ------------------------------' -ForegroundColor DarkGray

# --- 1. Prerrequisitos ---------------------------------------------------

Write-Step 'Comprobando prerrequisitos'

$missing = @()
foreach ($tool in @('docker', 'pnpm')) {
    if ($null -eq (Get-Command $tool -ErrorAction SilentlyContinue)) { $missing += $tool }
}
if ($missing.Count -gt 0) {
    Write-Err "Falta en el PATH: $($missing -join ', ')"
    return
}
Write-Ok 'docker y pnpm disponibles.'

if (-not (Test-Path $VenvPython)) {
    Write-Err "No existe el venv del backend: $VenvPython"
    Write-Host '       Créalo con:' -ForegroundColor Yellow
    Write-Host '         cd backend; python -m venv .venv' -ForegroundColor Yellow
    Write-Host '         .venv\Scripts\python.exe -m pip install -e ".[dev]" -c constraints.txt' -ForegroundColor Yellow
    return
}
$pyVersion = & $VenvPython -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
Write-Ok "venv del backend: Python $pyVersion"

if (-not (Test-Path (Join-Path $RepoRoot 'node_modules'))) {
    Write-Warn2 'No hay node_modules. Ejecutando pnpm install…'
    Set-Location $RepoRoot
    pnpm install
    if ($LASTEXITCODE -ne 0) { Write-Err 'pnpm install falló.'; return }
}
Write-Ok 'Dependencias de Node instaladas.'

Invoke-Quiet { docker info } | Out-Null
if ($script:QuietExit -ne 0) {
    Write-Err 'Docker no responde. ¿Está Docker Desktop arrancado?'
    return
}
Write-Ok 'Docker responde.'

# --- 2. Puerto del backend ----------------------------------------------

Write-Step 'Resolviendo el puerto del backend'
$backendInfo = Get-BackendPort
$BackendPort = $backendInfo.Port
Write-Ok "Puerto $BackendPort (según $($backendInfo.Source))."
Write-Host '       La web proxea /api/* a ese puerto; uvicorn arrancará justo ahí.' -ForegroundColor DarkGray

# --- 2b. Revisión y liberación de puertos --------------------------------

Write-Step 'Revisando puertos'

$appPorts = @()
$appPorts += @{ Port = $BackendPort; Label = 'backend' }
$appPorts += @{ Port = $WebPort;     Label = 'web' }
if ($Mobile) { $appPorts += @{ Port = $ExpoPort; Label = 'expo' } }

$portsOk = $true
foreach ($p in $appPorts) {
    if (-not (Resolve-PortConflict -Port $p.Port -Label $p.Label)) { $portsOk = $false }
}
if (-not $portsOk) {
    Write-Host ''
    Write-Err 'Aborto: quedan puertos ocupados.'
    Write-Host '       Opciones:  .\dev.ps1 -Stop      (cierra lo del proyecto)' -ForegroundColor Yellow
    Write-Host '                  .\dev.ps1 -Force     (cierra también lo ajeno)' -ForegroundColor Yellow
    return
}
Write-Ok 'Puertos de la app libres.'
Write-Host '       Los de infraestructura (5432, 9000/9001, 11434) los gestiona Docker;' -ForegroundColor DarkGray
Write-Host '       sólo se diagnostican si compose falla.' -ForegroundColor DarkGray

# --- 3. Contenedores -----------------------------------------------------

Write-Step 'Levantando contenedores (Postgres, MinIO, Ollama)'
Set-Location $RepoRoot
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Err 'docker compose up falló.'
    Show-InfraPortDiagnosis
    return
}

if (Wait-ForContainerHealth -Container 'crisol-postgres') {
    Write-Ok 'Postgres listo (healthcheck en verde).'
} else {
    Write-Err 'Postgres no llegó a healthy. Revisa: docker compose logs postgres'
    return
}
if (Wait-ForContainerHealth -Container 'crisol-minio' -TimeoutSeconds 45) {
    Write-Ok 'MinIO listo.'
} else {
    Write-Warn2 'MinIO no llegó a healthy; los tickets con imagen fallarán.'
}
Write-Ok 'Ollama arrancado (sin healthcheck; la IA local puede tardar en cargar el modelo).'

# --- 4. Migraciones ------------------------------------------------------

if ($SkipMigrations) {
    Write-Step 'Migraciones omitidas (-SkipMigrations)'
} else {
    Write-Step 'Aplicando migraciones'
    Set-Location (Join-Path $RepoRoot 'backend')
    & $VenvPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Err 'alembic upgrade head falló. El backend arrancaría contra un schema viejo.'
        Set-Location $RepoRoot
        return
    }
    Write-Ok 'Schema al día.'
    Set-Location $RepoRoot
}

# --- 5. Servicios --------------------------------------------------------

Write-Step 'Arrancando servicios en ventanas separadas'

Start-DevWindow -Title 'Crisol · backend (FastAPI)' `
                -WorkingDirectory (Join-Path $RepoRoot 'backend') `
                -Command "& '$VenvPython' -m uvicorn app.main:app --reload --host 0.0.0.0 --port $BackendPort"
Write-Ok "Backend lanzado en el puerto $BackendPort."

Start-DevWindow -Title 'Crisol · web (Next.js)' `
                -WorkingDirectory $RepoRoot `
                -Command 'pnpm dev:web'
Write-Ok "Web lanzada en el puerto $WebPort."

if ($Mobile) {
    Start-DevWindow -Title 'Crisol · movil (Expo)' `
                    -WorkingDirectory $RepoRoot `
                    -Command 'pnpm dev:mobile'
    Write-Ok "Expo lanzado en el puerto $ExpoPort."
}

# --- 6. Espera y comprobación -------------------------------------------

Write-Step 'Esperando a que respondan'

$backendUp = Wait-ForUrl -Url "http://localhost:$BackendPort/health" -Label 'Backend'
if ($backendUp) { Write-Ok "Backend responde en http://localhost:$BackendPort/health" }

$webUp = Wait-ForUrl -Url "http://localhost:$WebPort" -TimeoutSeconds 120 -Label 'Web'
if ($webUp) { Write-Ok "Web responde en http://localhost:$WebPort" }

# El rewrite es lo que de verdad importa: backend y web pueden estar vivos por
# separado y aun así no hablarse si el puerto no cuadra. Esto lo prueba.
if ($backendUp -and $webUp) {
    if (Wait-ForUrl -Url "http://localhost:$WebPort/api/health" -TimeoutSeconds 30 -Label 'Proxy web->backend') {
        Write-Ok 'El proxy /api de la web alcanza al backend.'
    } else {
        Write-Warn2 "La web no alcanza al backend por /api. Revisa BACKEND_ORIGIN en apps/web/.env.local (esperado: puerto $BackendPort)."
    }
}

# --- 7. Resumen ----------------------------------------------------------

Write-Host ''
Write-Host '  Todo arriba' -ForegroundColor Green
Write-Host '  -----------' -ForegroundColor DarkGray
Write-Host "  Web         http://localhost:$WebPort"
Write-Host "  API         http://localhost:$BackendPort"
Write-Host "  API docs    http://localhost:$BackendPort/docs"
Write-Host '  MinIO       http://localhost:9001  (consola)'
Write-Host '  Ollama      http://localhost:11434'
if ($Mobile) { Write-Host "  Expo        http://localhost:$ExpoPort" }
Write-Host ''
Write-Host '  Parar todo:  .\dev.ps1 -Stop' -ForegroundColor DarkGray
Write-Host ''

if (-not $NoBrowser -and $webUp) {
    Start-Process "http://localhost:$WebPort"
}
