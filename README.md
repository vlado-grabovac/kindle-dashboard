# Kindle dashboard

E-ink dashboard za Kindle Paperwhite 2 (758x1024): vrijeme za Sarajevo (Open-Meteo),
vanjski PM2.5 i podaci iz Xiaomi Smart Air Purifier 4 Pro (temperatura, vlaga, PM2.5, filter).

- `render.py` generise `dashboard.png`
- `xiaomi.py` cita preciscac preko Xiaomi clouda
- `.github/workflows/dashboard.yml` pokrece sve svakih 15 min i objavljuje na GitHub Pages
- `kindle/` fajlovi idu na Kindle (`dashboard/` u root, `documents/` u documents)

Secrets: `XIAOMI_USER`, `XIAOMI_PASS`. Opcione varijable: `XIAOMI_SERVER` (npr. `de`), `PURIFIER_MAP` (JSON).

Slika: https://vlado-grabovac.github.io/kindle-dashboard/dashboard.png

Fontovi: Inter (SIL Open Font License 1.1).
