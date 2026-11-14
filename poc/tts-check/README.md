# TTS check (throwaway, task 8)

This lists the Bangla/Arabic voices installed on a phone and speaks sample translations through the device TTS (`expo-speech`).
It runs in **Expo Go**, so no native build is needed. It is not the base of the Week 3 app.

```bash
npm ci
python3 scripts/export_samples.py ../bench/results/<e2e-run>/results.jsonl   # replace placeholder samples
npx expo start            # scan the QR code with Expo Go on the Android / iOS test device
```

On each device:
1. Note the voices listed under Arabic and Bangla, with each voice's locale (e.g. `ar-SA`, `ar-EG`). Any Arabic locale is acceptable.
2. Have a native listener play the samples and judge intelligibility and accent.
3. Tap **Share voice report** and paste the JSON plus the verdict into `poc/reports/tts.md`.

When a language has no voice, the app shows the text with a "No voice" notice instead of speaking.
