# Lumière mobile app (Expo SDK 58)

React Native client of the skincare companion. This first version contains the account screens and
the AI skin check, built from the final Figma design (colours, fonts, icons and photos come from the
design file).

Screens: Welcome, Sign up, Log in, Reset password, Today, Skin check intro, Privacy consent, Choose
area, Capture photo, five questions, Analysing, Result, Result uncertain, Photo not usable, Past checks
and Me. Scan and Routine are placeholders until the scanner and routine modules are built.

Informational tool only; not a medical device.

## Run

```bash
npm install
npx expo start            # scan the QR code with Expo Go (Android) or the Camera app (iOS)
npx expo start --web      # browser version on http://localhost:8081
npx tsc --noEmit && npx eslint src
```

## Testing the skin check on a phone

The photo is analysed by the ML service in `api/ml_service`. Start it from the repository root so the
phone can reach it over Wi-Fi:

```bash
ml/.venv/Scripts/python -m uvicorn api.ml_service.app:app --host 0.0.0.0 --port 8001
```

- The phone and the computer must be on the same Wi-Fi. The app calls port 8001 on the computer that
  runs the Expo dev server; set `EXPO_PUBLIC_ML_URL` (for example `http://192.168.1.20:8001`) to use
  another address. The address in use is shown at the bottom of the Me tab.
- Windows may ask to allow Python through the firewall on private networks; allow it.
- For the browser version also set `ML_CORS_ORIGINS=http://localhost:8081` when starting the service.
- If the service requires a key (`ML_SERVICE_KEY`), set the same value in `EXPO_PUBLIC_ML_SERVICE_KEY`
  (development only; in production the backend calls the service).

The model was trained on close-up photos of skin (SCIN), so a close photo of one zone (cheek, chin,
forehead) works best. A whole-face portrait is usually reported as "photo not usable", which is the
out-of-scope detector doing its job.

## Notes

- Accounts are stored on the device until the backend exists (salted SHA-256, never the password;
  12-character minimum; sign-in paused for 15 minutes after 5 failed attempts). The session id is kept
  in the platform keychain/keystore (`expo-secure-store`).
- Photos are downscaled on the phone (longest side 1024 px, JPEG), sent once and never saved. Results
  can be saved to the history on the device.
- With several zones each photo is analysed separately with the service's validated rule; the result
  is answered if at least one photo is answered (probabilities averaged over the answered photos).
