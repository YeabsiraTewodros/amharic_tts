Android APK build (Capacitor)
================================

This folder contains helper files to package the existing web app into an Android APK using Capacitor.

Prerequisites (local machine):
- Node.js + npm
- Java JDK 11+
- Android SDK and Android Studio (for building/signing)
- Android platform tools available on PATH (`adb`, `sdkmanager`, `avdmanager`) if you want CLI builds.

Steps (local):

1. Install npm deps

```bash
npm install
```

2. Prepare web assets (copies `static/` → `www/` and writes index.html)

```bash
npm run prepare:web
```

3. Initialize Capacitor (only once)

```bash
npm run cap:init
```

4. Add Android (only once)

```bash
npm run cap:add:android
```

5. Copy web assets into native project and open Android Studio

```bash
npm run cap:copy
npm run open:android
```

6. In Android Studio: select a device/emulator and Build → Build Bundle(s) / APK(s) → Build APK(s).

Notes:
- For automated CI builds you can run Gradle `assembleDebug` to produce an unsigned debug APK. For Play Store release, configure signing in Android Studio or Gradle.
- If you want me to create a GitHub Actions workflow to build an unsigned debug APK automatically, I can add that.
