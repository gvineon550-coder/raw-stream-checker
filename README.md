# 🎯 Raw Stream Checker v5.0

Stealth-заголовки (Accept, Origin, Language), умная дедупликация по качеству, проверка битрейта, HEAD→GET fallback, ротация UA, авто-обучение категорий, детект чёрного экрана (signalstats), EPG, лого.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-324-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-660-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-260-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-321-purple?style=flat-square) ![HD+](https://img.shields.io/badge/HD%2B-165-success?style=flat-square) ![режим](https://img.shields.io/badge/%F0%9F%94%AC%20DEEP-2026.11.03-orange?style=flat-square)

## 🔗 Ссылки

**Плейлист:**
```
https://raw.githubusercontent.com/gvineon550-coder/raw-stream-checker/main/playlist.m3u
```

**Отчёт:**
```
https://raw.githubusercontent.com/gvineon550-coder/raw-stream-checker/main/report.json
```

## 📊 Сводка

| Показатель | Значение |
|---|---|
| Всего каналов | **660** |
| Живых | **324** (49.1%) |
| Мёртвых | **336** |
| С EPG | **260** (80.2%) |
| С лого | **321** (99.1%) |
| **HD+ (720p+)** | **165** (50.9%) |
| Время | **322.2 s** |
| Режим | **🔬 DEEP** |
| Low-conf | **192** |
| Обновлено | `2026-11-03T22:36:58Z` |

### Живучесть

```
LIVE  █████████░░░░░░░░░░░   49.1%  (324/660)
```

## 🎯 Методы классификации

| Метод | Confidence | Каналов |
|---|---|---|
| `api_name` | 0.95 | 180 |
| `none` | 0.00 | 69 |
| `group` | 0.70 | 34 |
| `keyword` | 0.60 | 26 |
| `api_id` | 1.00 | 10 |
| `fuzzy` | 0.80 | 5 |

## 🚫 Топ причин фильтрации

| Причина | Каналов | Пример |
|---|---:|---|
| `tld` | 111 | _.ua_ |
| `word` | 108 | _carousel_ |
| `group` | 29 | _kids_ |
| `tvid` | 3 | _carousel.ru@plus4_ |

## 🗂 Категории

| Категория | Каналов |
|---|---:|
| 📦 Разное | 87 |
| 📡 Федеральные | 48 |
| 🎬 Кино | 40 |
| 📰 Новостные | 25 |
| 🎭 Развлекательные | 21 |
| 🎵 Музыкальные | 17 |
| 🧸 Детские | 16 |
| ⚽ Спорт | 15 |
| 📺 Сериалы | 15 |
| 🎥 Документальные | 8 |
| 🙏 Религиозные | 6 |
| 🌍 Природа | 5 |
| 🍳 Кулинарные | 4 |
| 🌍 Познавательные | 4 |
| 🌍 Путешествия | 4 |
| 🎭 Классика | 3 |
| 🎭 Культура | 3 |
| 🚗 Авто | 1 |
| 📰 Бизнес | 1 |
| 🛒 Магазины | 1 |

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Wink` | 207 |
| `HlsWinkPlayer` | 65 |
| `TiviMate` | 22 |
| `AndroidTV` | 7 |
| `Chrome_Win` | 6 |
| `VLC` | 6 |
| `okhttp` | 5 |
| `Lavf` | 2 |
| `Kodi` | 2 |
| `OTT` | 1 |
| `SmartTV` | 1 |

## ⚙️ Как это работает

**Стелс:** Accept, Accept-Language, Accept-Encoding, Connection, Origin для Wink/Rutube. HEAD pre-check → GET fallback. Ротация UA (learned первый, остальные — random).

**Дедупликация:** каналы с одинаковым именем группируются, выбирается лучшее разрешение. Остальные URLs — как fallback для плеера.

**Битрейт:** ffprobe извлекает `format=bit_rate`. В report.json у каждого канала есть `bitrate`.

**Каскад:** `api_id` (1.0) → `api_name` (0.95) → `learned` (0.95) → `fuzzy` (0.8) → `group` (0.7) → `keyword` (0.6) → `none`

**Авто-обучение:** fuzzy ≥88% → `data/learned_categories.json` (60 дней). Следующий прогон — `learned` метод (мгновенно).

**`#EXTHTTP` и `#KODIPROP`:** парсятся и передаются в заголовки ffprobe/ffmpeg.

**Quality:** `ffmpeg` black + signalstats + static + audio. 5 фейлов в РАЗНЫХ прогонах → блок 30 дней.

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-04 01:36 MSK</sub>
