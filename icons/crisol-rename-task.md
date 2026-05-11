# Tarea: Renombrar app a Crisol e integrar nuevo logo

## Contexto

- **Nombre antiguo:** "tracking finance" (y todas sus variantes: `tracking-finance`, `trackingfinance`, `TrackingFinance`)
- **Nombre nuevo:** **Crisol**
- **Convenciones a aplicar:**
  - Display name (UI, marketing, README): `Crisol`
  - Identifier/slug (package name, URLs, paths): `crisol`
  - Bundle ID candidato: `com.crisol.app` (ajusta a la convención de tu stack)
- **Logo:** he extraído `logo-package.zip` en `./assets/branding/`. Los archivos que tienes que usar (no necesitas el resto del paquete):

| Archivo | Para qué |
|---|---|
| `assets/branding/svg/logo-favicon.svg` | Favicon web (hex relleno, sin Y interna — optimizado para ≤32px) |
| `assets/branding/favicon.ico` | Favicon multi-resolución 16/32/48 (Windows tiles, navegadores legacy) |
| `assets/branding/png/apple-touch-icon.png` | iOS Safari "añadir a inicio" (180×180) |
| `assets/branding/png/icon-1024.png` | App icon iOS/Android (master, el stack genera el resto) |
| `assets/branding/png/icon-192.png` | PWA manifest (si aplica) |
| `assets/branding/png/icon-512.png` | PWA manifest (si aplica) |

El resto de PNGs (`icon-48.png`, `icon-64.png`, etc.) y SVGs (`logo-icon-color.svg`, `logo-mark-*.svg`) **NO se usan en este rename** — son para usos manuales (marketing, embeds, exports puntuales). El stack regenera todos los tamaños intermedios automáticamente desde `icon-1024.png`.

---

## Fase 1 — Audit (NO modifiques nada)

1. Detecta el stack del proyecto (Node/React/RN/Expo/Flutter/Vue/etc.).
2. Lista TODAS las ocurrencias case-insensitive de `tracking finance`, `tracking-finance`, `trackingfinance`, `TrackingFinance` en:
   - `package.json`, `app.json`, `expo.json`, `manifest.json`, `pubspec.yaml`
   - `AndroidManifest.xml`, `Info.plist`, `MainActivity.*`, `*.iml`
   - `README*`, `CHANGELOG*`, dotfiles, `.env.example`
   - Todo el código fuente (incluye comentarios, strings, JSDoc)
   - Configs de CI/CD (`.github/`, `.gitlab-ci.yml`, `vercel.json`, `netlify.toml`)
3. Reporta: tabla con `archivo : línea : contexto`. **Para aquí. Espera mi confirmación.**

---

## Fase 2 — Rename (tras confirmación explícita)

1. Sustituye según convención (Display name vs identifier según contexto).
2. Actualiza específicamente:
   - `package.json`: `name`, `displayName`, `description` si aplica
   - `app.json/expo`: `name`, `slug`, `scheme`, `ios.bundleIdentifier`, `android.package`
   - Manifest Android: `package`, `android:label`
   - `Info.plist`: `CFBundleDisplayName`, `CFBundleName`, `CFBundleIdentifier`
   - `index.html` head: `<title>`, meta tags
   - README: títulos, badges, URLs de repo
3. **NO TOQUES:** `package-lock.json`, `yarn.lock`, `Podfile.lock`, `node_modules/`, `vendor/`, `.git/`, ficheros `.env` reales con secrets.
4. Tras los cambios, ejecuta el comando de package manager apropiado para regenerar lockfiles (`npm install` / `yarn` / `pod install`).

---

## Fase 3 — Integración del logo

> **Principio:** un solo archivo por canal cuando sea posible. El stack genera los tamaños intermedios mejor que pasarle todos los PNGs manualmente.

### Si hay frontend web (`public/`, `static/`, `index.html`)

Copia estos **3 archivos** (no más):

```
assets/branding/svg/logo-favicon.svg     → public/favicon.svg
assets/branding/favicon.ico              → public/favicon.ico
assets/branding/png/apple-touch-icon.png → public/apple-touch-icon.png
```

Actualiza `<head>` de `index.html`:

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="apple-mobile-web-app-title" content="Crisol">
<title>Crisol</title>
```

**Por qué los tres y no solo el SVG:** el SVG cubre Chrome/Firefox/Edge/Safari modernos (>95% del tráfico). El `.ico` cubre Windows pinned tiles y navegadores legacy. El `apple-touch-icon` lo usa iOS Safari cuando el usuario añade la web a la pantalla de inicio.

### Si hay app mobile

Pasa **únicamente** `assets/branding/png/icon-1024.png` al stack. Genera el resto desde ahí:

| Stack | Cómo |
|---|---|
| **Expo** | En `app.json`: `"icon": "./assets/branding/png/icon-1024.png"` y `"splash.image": "./assets/branding/png/icon-1024.png"`. EAS build genera todos los tamaños iOS/Android automáticamente. |
| **React Native bare** | `npx @bam.tech/react-native-make set-icon --path ./assets/branding/png/icon-1024.png` |
| **Flutter** | Añade `flutter_launcher_icons` a `pubspec.yaml` con `image_path: "assets/branding/png/icon-1024.png"`, luego `flutter pub run flutter_launcher_icons`. |
| **Android Studio nativo** | File → New → Image Asset → selecciona `icon-1024.png`. Genera mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}. |
| **iOS Xcode nativo** | Arrastra `icon-1024.png` al slot 1024×1024 (App Store) en `Assets.xcassets/AppIcon.appiconset`. Xcode 14+ genera el resto. |

**Splash screen:** mismo `icon-1024.png` con `background_color: "#0f0f0f"` (grafito) para garantizar contraste con el cobre.

**No le pases iconos pre-redimensionados (`icon-48`, `icon-64`, etc.).** El algoritmo de scaling del stack es mejor que el pre-redimensionado manual — pasarlos por separado degrada la calidad al inyectar resampling adicional.

### Si hay PWA manifest (`manifest.json` o `manifest.webmanifest`)

Copia los dos PNGs canónicos:

```
assets/branding/png/icon-192.png → public/icons/icon-192.png
assets/branding/png/icon-512.png → public/icons/icon-512.png
```

Actualiza el manifest:

```json
{
  "name": "Crisol",
  "short_name": "Crisol",
  "theme_color": "#0f0f0f",
  "background_color": "#0f0f0f",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

192 y 512 son los dos tamaños obligatorios del PWA standard; el resto los infiere el navegador.

---

## Fase 4 — Verificación

1. Corre tests (`npm test` / `yarn test` / `flutter test` / lo que aplique).
2. Si hay tests rotos: NO committees, reporta y para.
3. Si pasan: build local rápido para confirmar que la app arranca con el nuevo nombre.

---

## Fase 5 — Commit

Si todo verde, commit atómico:

```
chore(brand): rename project to Crisol and integrate logo assets

- Replace all "tracking finance" references with "Crisol"
- Update bundle identifiers and package names
- Integrate logo assets (favicon, app icon, apple-touch-icon)
- Update HTML meta tags and PWA manifest
```

NO hagas push, NO hagas force, NO hagas rebase.

---

## Fase 6 — Reporte final

Lista en tu último mensaje:

1. **Archivos modificados** (con línea count diff)
2. **Archivos NO modificados que requieren acción manual mía** (fuera de tu scope):
   - Cuentas de despliegue (Vercel/Netlify/Heroku project name)
   - Dominio DNS y certificados
   - App Store Connect / Play Console (bundle ID, listing)
   - Secrets/env vars en CI
   - GitHub repo rename
3. **Comandos pendientes** que debo ejecutar yo manualmente (`git mv` del root folder, etc.)

---

## Constraints duros

- No commits si tests rotos
- No fuerces git
- No toques credentials/secrets reales
- No instales nuevas dependencies sin justificarlo en el reporte
