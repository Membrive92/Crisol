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

    LIMPIEZA DE RESTOS

    Antes de nada barre lo que quedara vivo de una sesión anterior, mire o no
    a un puerto. Los dos no son lo mismo: matar al dueño del 3000 deja en pie
    la VENTANA que lo lanzó —que sigue abierta a propósito, para que se pueda
    leer el error—, así que sin este paso se acumula una ventana muerta por
    arranque. Se cierran los servicios (uvicorn y sus workers, next, turbo,
    pnpm, expo) y las ventanas que abrió este script.

    Lo que NO cierra, aunque también sea "del proyecto": un `pytest`, un
    `alembic` o un script de datos corriendo en el venv. Pertenecen al repo
    pero no son restos del arranque, y tumbarlos a media escritura sería mucho
    peor que dejarlos. Por eso el barrido busca los SERVICIOS por su línea de
    comandos, no todo lo que toque la carpeta.

    Y nunca se toca a sí mismo ni a quien lo lanzó: la ruta del repo aparece
    también en la línea de comandos de tu terminal y en la de VS Code (que se
    abre con la carpeta del workspace como argumento). Comprobado en esta
    máquina: sin esa exclusión, "limpiar restos" cierra el editor.

    LIBERACIÓN AUTOMÁTICA DE PUERTOS

    Después revisa los puertos que necesita y los libera. Pero no mata
    a ciegas lo que haya escuchando: distingue si el proceso es DEL PROYECTO
    (por su línea de comandos o la de sus padres) o ajeno.

      - Del proyecto  -> lo cierra sin preguntar. Es un resto de otra sesión.
      - Ajeno         -> lo dice y PREGUNTA. Podría ser otro proyecto tuyo en
                         el 3000, o un Postgres del sistema en el 5432, y
                         matarlo por sorpresa sería peor que no arrancar.

    Los puertos de los contenedores (5432, 9000, 9001, 11434) se revisan pero
    NUNCA se matan solos: si los ocupa algo que no es nuestro contenedor, lo más
    probable es que sea un servicio del sistema. Se avisa y se decide a mano.

    DOCKER DESKTOP SE ARRANCA SOLO

    Que `docker` esté en el PATH no significa que haya motor detrás: el CLI y el
    demonio son cosas distintas, y en Windows el segundo se apaga al cerrar
    sesión o al reiniciar. Antes, el script se limitaba a decir "Docker no
    responde" y abortaba — o sea que el arranque más frecuente (el primero del
    día) no arrancaba nada. Ahora lo abre él y espera al motor.

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

#: Marcadores que identifican un proceso como "de ESTE proyecto". Sólo valen
#: los que no puede llevar el proyecto de al lado.
#:
#: Aquí había también `next dev`, `turbo run dev`, `expo start` y
#: `app.main:app`, que son genéricos: los lleva idéntico cualquier otro repo
#: tuyo con Next o FastAPI. Mientras esto sólo decidía si PREGUNTAR antes de
#: liberar un puerto, el precio de equivocarse era una pregunta de menos. Desde
#: que gobierna el barrido, decide a quién se cierra sin avisar — y un `next
#: dev` de otro proyecto, en otro puerto, cumplía el criterio.
#:
#: No se pierde nada al quitarlos: lo que de verdad ata un proceso a este repo
#: es su ejecutable dentro de la carpeta (el `python.exe` del venv,
#: `turbo.exe`) o la ruta del repo en la línea de comandos, y los eslabones que
#: no tienen ninguna de las dos la heredan del padre. Verificado en la cadena
#: real `powershell -> pnpm -> cmd -> turbo -> node -> next`, donde la prueba
#: aparece a dos niveles del más pobre.
$script:ProjectMarkers = @(
    'crisol'
)

#: Marca que llevan las ventanas que abre este script, para reconocerlas sin
#: adivinar. El título ya era casi único, pero un título se cambia por estética
#: y entonces el barrido dejaría de encontrarlas en silencio.
$script:DevWindowMarker = 'CRISOL_DEV_WINDOW'

#: Los argumentos EXACTOS con que se lanza una ventana de dev. La lista la usa
#: `Start-DevWindow` para abrirla y `Test-DevWindow` para reconocerla, y por eso
#: es una constante y no dos literales: si alguien añade un flag al lanzador y
#: el detector se queda con la cadena vieja, el barrido deja de encontrar sus
#: propias ventanas — y no falla, simplemente no limpia.
#:
#: Reconocer por la firma CONTIGUA y no sólo por el marcador tiene un motivo
#: medido: cualquier consola que MENCIONE el marcador —la que usas para
#: comprobar que la marca funciona— lo lleva también en su línea de comandos.
#: `-NoExit -NoProfile -Command` seguidos sólo los produce `Start-Process` aquí;
#: una consola de herramientas trae `-NoProfile -NonInteractive`, que no casa.
$script:DevWindowArgs      = @('-NoExit', '-NoProfile', '-Command')
$script:DevWindowSignature = $script:DevWindowArgs -join ' '

#: Qué línea de comandos delata a un SERVICIO de la app —lo que este script
#: arranca— frente al resto de cosas que uno ejecuta en el repo. Se comparan en
#: minúsculas contra la línea entera, así que valen tanto el argumento
#: (`run dev`) como el trozo de ruta del binario (`turbo`, `next`).
#: Deliberadamente NO están aquí `pytest`, `alembic`, `mypy` ni los scripts de
#: datos: corren con el mismo `python.exe` del venv y son igual de "del
#: proyecto", pero matarlos no limpia nada — rompe lo que estuvieras haciendo.
$script:AppProcessMarkers = @(
    'app.main:app',
    'uvicorn',
    'run dev',
    'dev:web',
    'dev:mobile',
    'next',
    'turbo',
    'expo'
)

#: Ejecutables que el barrido se permite tocar. Lista CERRADA: el criterio de
#: pertenencia es la ruta del repo, y esa ruta también sale en la línea de
#: comandos de VS Code y del terminal desde el que lanzas esto.
$script:SweepableNames = @('python', 'pythonw', 'node', 'turbo', 'esbuild', 'uvicorn', 'pnpm')

function Get-ProcessSnapshot {
    <#
    .SYNOPSIS
        Una foto de todos los procesos, indexada por PID.
    .DESCRIPTION
        Una sola consulta a CIM en vez de una por proceso y nivel de ancestro.
        Además de ser más rápida, es COHERENTE: recorrer el árbol con consultas
        sueltas puede ver un padre que ya murió a medio recorrido y decidir con
        media verdad.
    #>
    $map = @{}
    foreach ($proc in Get-CimInstance Win32_Process -ErrorAction SilentlyContinue) {
        $map[[int]$proc.ProcessId] = $proc
    }
    return $map
}

function Get-SelfAndAncestorIds {
    <#
    .SYNOPSIS
        El PID de este script y toda su cadena de padres: intocables.
    .DESCRIPTION
        Sin esto, el barrido se suicida. Está verificado en esta máquina: el
        proceso que ejecuta el script tiene la ruta del repo en su propia línea
        de comandos —igual que el terminal que lo lanzó y que VS Code—, así que
        cumple el criterio de "es del proyecto" tan bien como uvicorn.

        El `HashSet` corta también los ciclos: Windows recicla PIDs, y un padre
        reciclado puede apuntar de vuelta a un descendiente y hacer bucle.
    #>
    param([hashtable]$Snapshot, [int]$MaxDepth = 12)

    $ids = New-Object 'System.Collections.Generic.HashSet[int]'
    $null = $ids.Add($PID)
    $current = $PID
    for ($depth = 0; $depth -lt $MaxDepth; $depth++) {
        $proc = $Snapshot[$current]
        if ($null -eq $proc) { break }
        $parent = [int]$proc.ParentProcessId
        if ($parent -le 4) { break }          # 0/4 = kernel
        if (-not $ids.Add($parent)) { break } # ya visto: ciclo por PID reciclado
        $current = $parent
    }
    return $ids
}

function Test-ProjectProcess {
    <#
    .SYNOPSIS
        ¿El proceso pertenece a este proyecto?
    .DESCRIPTION
        Mira su ejecutable y su línea de comandos y, si no concluye, SUBE POR
        SUS PADRES. Hace falta: el worker de `uvicorn --reload` se lanza como
        `python.exe -c "from multiprocessing..."`, que no menciona ni el repo ni
        la app. Sin mirar al padre, el proceso más característico del proyecto
        parecería ajeno y el script pediría permiso para matar lo que él mismo
        había arrancado.

        Las dos señales hacen falta, no una: `turbo.exe` vive DENTRO del repo
        (`node_modules/.pnpm/...`) pero `node.exe` es el global de
        `Program Files` y sólo la línea de comandos lo delata.

        Un socket cuyo dueño ya murió se considera del proyecto: es el zombi de
        uvicorn descrito en `Stop-PortHolder`.

        La profundidad es 6 y no 4 porque la cadena real de la web mide siete
        eslabones (`powershell -> pnpm -> cmd -> turbo -> node -> cmd -> node`)
        y algunos de ellos —`cmd.exe` lanzando `pnpm.cmd`— no dicen ni el repo
        ni nada: sólo el abuelo los delata.
    #>
    param([int]$ProcessId, [int]$MaxDepth = 6, [hashtable]$Snapshot)

    $root = $RepoRoot.ToLowerInvariant()
    $currentId = $ProcessId
    for ($depth = 0; $depth -lt $MaxDepth; $depth++) {
        if ($Snapshot) {
            $proc = $Snapshot[$currentId]
        } else {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $currentId" -ErrorAction SilentlyContinue
        }
        if ($null -eq $proc) {
            # Sin proceso: o es el huérfano de uvicorn (nuestro), o el padre ya
            # no existe y no se puede seguir subiendo.
            return ($depth -eq 0)
        }
        if ($proc.ExecutablePath -and $proc.ExecutablePath.ToLowerInvariant().StartsWith($root)) {
            return $true
        }
        $cmd = $proc.CommandLine
        if ($cmd) {
            $lower = $cmd.ToLowerInvariant()
            if ($lower.Contains($root)) { return $true }
            foreach ($marker in $script:ProjectMarkers) {
                if ($lower.Contains($marker.ToLowerInvariant())) { return $true }
            }
        }
        if ($proc.ParentProcessId -le 4) { return $false }  # 0/4 = kernel
        $currentId = [int]$proc.ParentProcessId
    }
    return $false
}

function Test-AppServiceProcess {
    <#
    .SYNOPSIS
        ¿Es uno de los SERVICIOS que arranca este script (y no otra cosa del repo)?
    .DESCRIPTION
        Se pregunta después de `Test-ProjectProcess`, no en su lugar: aquélla
        dice "es de este repo" y ésta "es del arranque". Separarlas es lo que
        deja vivo un `pytest` del venv mientras se cierra un uvicorn huérfano.

        Sube por los padres por el mismo motivo que la otra: el worker de
        `--reload` no menciona uvicorn, pero su supervisor sí. Y cualquier
        descendiente de una ventana de dev cuenta como servicio — es la cadena
        `powershell -> pnpm -> node -> turbo -> next`, donde los eslabones de en
        medio no dicen nada por sí mismos.
    #>
    param([int]$ProcessId, [hashtable]$Snapshot, [int]$MaxDepth = 6)

    $marker = $script:DevWindowMarker.ToLowerInvariant()
    $currentId = $ProcessId
    for ($depth = 0; $depth -lt $MaxDepth; $depth++) {
        $proc = $Snapshot[$currentId]
        if ($null -eq $proc) { return $false }
        $cmd = $proc.CommandLine
        if ($cmd) {
            $lower = $cmd.ToLowerInvariant()
            if ($lower.Contains($marker)) { return $true }
            foreach ($appMarker in $script:AppProcessMarkers) {
                if ($lower.Contains($appMarker)) { return $true }
            }
        }
        if ($proc.ParentProcessId -le 4) { return $false }
        $currentId = [int]$proc.ParentProcessId
    }
    return $false
}

function Test-DevWindow {
    <#
    .SYNOPSIS
        ¿Es una de las ventanas que abre este script?
    .DESCRIPTION
        Acepta también el título, y no sólo el marcador, porque las ventanas ya
        abiertas cuando se añadió el marcador no lo llevan: sin esta segunda
        vía, el primer arranque tras el cambio no limpiaría justo los restos que
        motivaron el cambio. Se compara la parte del título SIN el separador
        `·`, que viaja distinto según la codificación de la consola.

        Se exige ADEMÁS la firma de lanzamiento (`$script:DevWindowSignature`),
        que es lo que distingue una ventana ABIERTA por `Start-DevWindow` de
        cualquier consola que simplemente MENCIONE el marcador. No es
        hipotético y no basta con pedir `-NoExit` suelto: buscar
        `CRISOL_DEV_WINDOW` para comprobar que la marca funciona mete el
        literal —y el `-NoExit` de la propia consulta— en la línea de comandos
        de la consola desde la que buscas. Las dos versiones de esta condición
        se probaron contra procesos reales, y la primera se la tragaba.
    #>
    param($Proc)

    $name = [System.IO.Path]::GetFileNameWithoutExtension($Proc.Name).ToLowerInvariant()
    if ($name -ne 'powershell' -and $name -ne 'pwsh') { return $false }
    $cmd = $Proc.CommandLine
    if (-not $cmd) { return $false }
    if (-not $cmd.Contains($script:DevWindowSignature)) { return $false }
    return ($cmd.Contains($script:DevWindowMarker) -or $cmd.Contains("WindowTitle = 'Crisol"))
}

function Invoke-ProjectSweep {
    <#
    .SYNOPSIS
        Cierra todo resto del proyecto que siga vivo, retenga un puerto o no.
    .DESCRIPTION
        Tres criterios, en este orden:

          1. Nunca a sí mismo ni a sus ancestros (ver `Get-SelfAndAncestorIds`).
          2. Ventanas de dev -> se cierran enteras, con su árbol. Van primero
             porque `taskkill /T` sobre la ventana se lleva ya la cadena
             `pnpm -> node -> turbo -> next` y evita rematar uno a uno.
          3. Ejecutable de la lista + del repo + con pinta de servicio.

        Lo que es del repo pero no es un servicio se REPORTA y se deja vivo: si
        un resto sobrevive al barrido, mejor saber por qué que descubrirlo
        cuando el puerto siga ocupado.
    .OUTPUTS
        [int] cuántos procesos se cerraron.
    #>
    $snapshot  = Get-ProcessSnapshot
    $protected = Get-SelfAndAncestorIds -Snapshot $snapshot

    $victims = @()
    $spared  = @()

    foreach ($proc in $snapshot.Values) {
        $id = [int]$proc.ProcessId
        if ($id -le 4 -or $protected.Contains($id)) { continue }

        if (Test-DevWindow -Proc $proc) {
            $victims += [pscustomobject]@{ Id = $id; Name = $proc.Name; Why = 'ventana de dev'; First = 0 }
            continue
        }

        $name = ($proc.Name -replace '\.exe$', '').ToLowerInvariant()
        if ($script:SweepableNames -notcontains $name) { continue }
        if (-not (Test-ProjectProcess -ProcessId $id -Snapshot $snapshot)) { continue }

        if (Test-AppServiceProcess -ProcessId $id -Snapshot $snapshot) {
            $victims += [pscustomobject]@{ Id = $id; Name = $proc.Name; Why = 'servicio de la app'; First = 1 }
        } else {
            $spared += [pscustomobject]@{ Id = $id; Name = $proc.Name }
        }
    }

    if ($spared.Count -gt 0) {
        $list = ($spared | ForEach-Object { "$($_.Name) (PID $($_.Id))" }) -join ', '
        Write-Warn2 "Del repo pero no del arranque, los dejo vivos: $list"
    }

    if ($victims.Count -eq 0) {
        Write-Ok 'No quedaban restos de sesiones anteriores.'
        return 0
    }

    foreach ($victim in ($victims | Sort-Object -Property First, Id)) {
        Write-Warn2 "Cierro $($victim.Name) (PID $($victim.Id)) — $($victim.Why)."
        # `/T` para el árbol; que un hijo ya no exista porque lo mató el padre
        # es lo ESPERADO, y por eso va silenciado (ver `Invoke-Quiet`).
        Invoke-Quiet { taskkill /PID $victim.Id /T /F } | Out-Null
    }

    $alive = @()
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        $alive = @($victims | Where-Object { Get-Process -Id $_.Id -ErrorAction SilentlyContinue })
        if ($alive.Count -eq 0) { break }
        Start-Sleep -Milliseconds 400
    }

    if ($alive.Count -gt 0) {
        $list = ($alive | ForEach-Object { "$($_.Name) (PID $($_.Id))" }) -join ', '
        Write-Warn2 "Siguen vivos tras el cierre: $list"
    } else {
        Write-Ok "Restos cerrados: $($victims.Count)."
    }
    return ($victims.Count - $alive.Count)
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
    .DESCRIPTION
        El guion generado empieza por un comentario con `$script:DevWindowMarker`.
        No es decorativo: ese comentario viaja en la LÍNEA DE COMANDOS de la
        ventana, y es lo que permite al barrido reconocerla como suya sin
        heurísticas. La ventana no se cierra al terminar el proceso (a
        propósito, para poder leer el error), así que sin una marca fiable cada
        arranque dejaría una ventana muerta más.
    #>
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    $script = @"
# $script:DevWindowMarker
`$host.UI.RawUI.WindowTitle = '$Title'
Set-Location '$WorkingDirectory'
Write-Host '--- $Title ---' -ForegroundColor Cyan
$Command
Write-Host ''
Write-Host 'El proceso ha terminado. Esta ventana queda abierta para que leas el error.' -ForegroundColor Yellow
"@
    Start-Process -FilePath 'powershell.exe' `
                  -ArgumentList ($script:DevWindowArgs + $script) `
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

#: Dónde vive el ejecutable de Docker Desktop. Se busca a mano porque el
#: instalador NO lo pone en el PATH: lo que sí está es `docker`, el CLI, que
#: vive en otra carpeta y responde igual de bien con el motor apagado. Esa
#: diferencia es justo la que hace falta salvar aquí.
#: Se interpolan sin `Join-Path` a propósito: en una máquina de 32 bits
#: `${env:ProgramFiles(x86)}` es $null y `Join-Path` con $null LANZA — con
#: `$ErrorActionPreference = 'Stop'` eso mataría el script al cargarlo. Una
#: cadena con el prefijo vacío sólo produce una ruta que `Test-Path` descarta.
$script:DockerDesktopPaths = @(
    "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
    "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
    "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
)

function Test-DockerEngine {
    <#
    .SYNOPSIS
        ¿Responde el motor de Docker? (no el CLI: el motor)
    .DESCRIPTION
        Va por `Invoke-Quiet` porque con el demonio apagado `docker info`
        escribe en stderr, y redirigir la stderr de un nativo con
        `$ErrorActionPreference = 'Stop'` aborta el script — que es la trampa
        documentada arriba en `Invoke-Quiet`.
    #>
    Invoke-Quiet { docker info } | Out-Null
    return ($script:QuietExit -eq 0)
}

function Start-DockerEngine {
    <#
    .SYNOPSIS
        Deja el motor de Docker respondiendo: lo abre si hace falta y espera.
    .DESCRIPTION
        Tres situaciones distintas que se ven igual desde `docker info`:

          - Motor vivo            -> no se toca nada.
          - Docker Desktop ABIERTO pero todavía inicializando -> sólo esperar.
            Lanzar una segunda instancia no acelera nada y en Windows saca un
            diálogo de "ya se está ejecutando" que hay que cerrar a mano.
          - Docker Desktop cerrado -> abrirlo y esperar.

        El arranque en frío del backend WSL2 tarda de 30 s a más de un minuto,
        así que el margen es generoso: agotarlo antes de tiempo devolvería un
        "no responde" que sólo significa "aún no".
    .OUTPUTS
        [bool] $true si el motor acabó respondiendo.
    #>
    param([int]$TimeoutSeconds = 180)

    if (Test-DockerEngine) { return $true }

    $running = @(Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)
    if ($running.Count -gt 0) {
        Write-Warn2 'Docker Desktop está abierto pero el motor aún no responde; espero…'
    } else {
        $exe = $script:DockerDesktopPaths |
               Where-Object { $_ -and (Test-Path $_) } |
               Select-Object -First 1
        if (-not $exe) {
            Write-Err 'Docker no responde y no encuentro Docker Desktop para arrancarlo.'
            Write-Host '       Ábrelo a mano y repite. Lo he buscado en:' -ForegroundColor Yellow
            foreach ($path in $script:DockerDesktopPaths) {
                Write-Host "         $path" -ForegroundColor Yellow
            }
            return $false
        }
        Write-Warn2 'Docker no responde. Abro Docker Desktop (el arranque en frío tarda ~1 min)…'
        Start-Process -FilePath $exe | Out-Null
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        if (Test-DockerEngine) { return $true }
    }

    Write-Err "El motor de Docker no respondió en $TimeoutSeconds s."
    Write-Host '       Mira la ventana de Docker Desktop: suele estar pidiendo una actualización,' -ForegroundColor Yellow
    Write-Host '       la contraseña de WSL o aceptar los términos, y se queda ahí esperando.' -ForegroundColor Yellow
    return $false
}

# ─────────────────────────────────────────────────────────────────────────
# Parada
# ─────────────────────────────────────────────────────────────────────────

function Invoke-StopAll {
    Write-Step 'Cerrando restos del proyecto'
    # Primero el barrido y después los puertos, no al revés: el barrido cierra
    # las ventanas con su árbol, así que para cuando se revisan los puertos ya
    # no suele quedar nadie escuchando. Al revés funcionaría igual, pero
    # dejaría las ventanas abiertas — que es justo lo que se acumulaba.
    Invoke-ProjectSweep | Out-Null

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
    # Con el motor apagado no hay nada que parar, y `docker compose down`
    # escupiría un error de conexión que se lee como si algo hubiera fallado.
    # Aquí NO se arranca Docker: abrirlo para acto seguido bajar sus
    # contenedores sería lo contrario de lo que pide `-Stop`.
    if (-not (Test-DockerEngine)) {
        Write-Ok 'Docker no está corriendo: los contenedores ya están parados.'
    } else {
        Set-Location $RepoRoot
        docker compose down
        if ($LASTEXITCODE -eq 0) { Write-Ok 'Contenedores parados.' }
        else { Write-Warn2 'docker compose down devolvió error.' }
    }

    Write-Host "`nEntorno parado.`n" -ForegroundColor Green
}

# ─────────────────────────────────────────────────────────────────────────
# Principal
# ─────────────────────────────────────────────────────────────────────────

# Los finales son `exit <código>` y no `return` a propósito. Sin un código
# explícito, el script hereda el `$LASTEXITCODE` del último comando nativo que
# se ejecutara — y varios de ellos son SONDEOS cuyo fallo es el resultado
# esperado: `docker info` con el motor apagado devuelve 1, así que un `-Stop`
# que había terminado perfectamente salía con código de error.
if ($Stop) {
    Invoke-StopAll
    exit 0
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
    exit 1
}
Write-Ok 'docker y pnpm disponibles.'

if (-not (Test-Path $VenvPython)) {
    Write-Err "No existe el venv del backend: $VenvPython"
    Write-Host '       Créalo con:' -ForegroundColor Yellow
    Write-Host '         cd backend; python -m venv .venv' -ForegroundColor Yellow
    Write-Host '         .venv\Scripts\python.exe -m pip install -e ".[dev]" -c constraints.txt' -ForegroundColor Yellow
    exit 1
}
$pyVersion = & $VenvPython -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
Write-Ok "venv del backend: Python $pyVersion"

if (-not (Test-Path (Join-Path $RepoRoot 'node_modules'))) {
    Write-Warn2 'No hay node_modules. Ejecutando pnpm install…'
    Set-Location $RepoRoot
    pnpm install
    if ($LASTEXITCODE -ne 0) { Write-Err 'pnpm install falló.'; exit 1 }
}
Write-Ok 'Dependencias de Node instaladas.'

if (-not (Start-DockerEngine)) { exit 1 }
Write-Ok 'Docker responde.'

# --- 2. Puerto del backend ----------------------------------------------

Write-Step 'Resolviendo el puerto del backend'
$backendInfo = Get-BackendPort
$BackendPort = $backendInfo.Port
Write-Ok "Puerto $BackendPort (según $($backendInfo.Source))."
Write-Host '       La web proxea /api/* a ese puerto; uvicorn arrancará justo ahí.' -ForegroundColor DarkGray

# --- 2b. Revisión y liberación de puertos --------------------------------

Write-Step 'Limpiando restos de sesiones anteriores'

if ($NoKill) {
    Write-Warn2 '-NoKill activo: no cierro nada (si algo sigue vivo, el arranque abortará).'
} else {
    Invoke-ProjectSweep | Out-Null
}

# --- 2c. Revisión de puertos ---------------------------------------------

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
    exit 1
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
    exit 1
}

if (Wait-ForContainerHealth -Container 'crisol-postgres') {
    Write-Ok 'Postgres listo (healthcheck en verde).'
} else {
    Write-Err 'Postgres no llegó a healthy. Revisa: docker compose logs postgres'
    exit 1
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
        exit 1
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

# Si un servicio no llegó a responder, el arranque NO ha ido bien por mucho que
# se haya impreso el resumen: las ventanas siguen abiertas con su error dentro.
if ($backendUp -and $webUp) { exit 0 }
exit 1
