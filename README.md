# 🎯 Raw Stream Checker v5.2

Stealth, dedup, bitrate, problem rehab, auto-learning, EPG, лого.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-321-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-660-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-258-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-318-purple?style=flat-square) ![HD+](https://img.shields.io/badge/HD%2B-162-success?style=flat-square) ![режим](https://img.shields.io/badge/%F0%9F%94%AC%20DEEP-2026.11.04-orange?style=flat-square)

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
| Живых | **321** (48.6%) |
| Мёртвых | **339** |
| С EPG | **258** (80.4%) |
| С лого | **318** (99.1%) |
| **HD+ (720p+)** | **162** (50.5%) |
| Отсеяно по битрейту | **3** |
| Время | **322.1 s** |
| Режим | **🔬 DEEP** |
| Low-conf | **169** |
| Обновлено | `2026-11-04T08:41:20Z` |

### Живучесть

```
LIVE  █████████░░░░░░░░░░░   48.6%  (321/660)
```

## 🎯 Методы классификации

| Метод | Confidence | Каналов |
|---|---|---|
| `api_name` | 0.95 | 177 |
| `none` | 0.00 | 60 |
| `group` | 0.70 | 35 |
| `keyword` | 0.60 | 23 |
| `fuzzy` | 0.80 | 10 |
| `api_id` | 1.00 | 9 |
| `learned` | 0.95 | 7 |

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
| 📦 Разное | 78 |
| 📡 Федеральные | 48 |
| 🎬 Кино | 41 |
| 📰 Новостные | 24 |
| 🎭 Развлекательные | 21 |
| 🎵 Музыкальные | 18 |
| 📺 Сериалы | 17 |
| 🧸 Детские | 17 |
| ⚽ Спорт | 15 |
| 🎥 Документальные | 9 |
| 🙏 Религиозные | 6 |
| 🌍 Природа | 5 |
| 🌍 Познавательные | 4 |
| 🌍 Путешествия | 4 |
| 🍳 Кулинарные | 4 |
| 🎭 Культура | 3 |
| 🎭 Классика | 3 |
| 📰 Бизнес | 2 |
| 🚗 Авто | 1 |
| 🛒 Магазины | 1 |

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Kodi` | 105 |
| `Wink` | 98 |
| `HlsWinkPlayer` | 58 |
| `TiviMate` | 27 |
| `AndroidTV` | 9 |
| `Chrome_Win` | 8 |
| `VLC` | 8 |
| `okhttp` | 5 |
| `Lavf` | 2 |
| `SmartTV` | 1 |

## ⚙️ Как это работает

**Реабилитация:** заблокированные каналы перепроверяются через 7 дней. Если чисто — разблокируются; если плохо — новый 30-дневный блок.

**Стелс:** Accept, Accept-Language, Accept-Encoding, Connection, Origin для Wink/Rutube. HEAD pre-check → GET fallback. Ротация UA.

**Дедупликация:** группировка по (norm_name + tvg_id/host) → лучшее разрешение + битрейт.

**Битрейт:** `quality_min_bitrate = 100000` (100 kbps). Ниже — слайд-шоу, отсеиваются.

**Каскад:** `api_id` (1.0) → `api_name` (0.95) → `learned` (0.95) → `fuzzy` (0.8) → `group` (0.7) → `keyword` (0.6) → `none`

**Авто-обучение:** fuzzy ≥82% → `data/learned_categories.json` (60 дней).

**Quality:** `ffmpeg` black + signalstats + static + audio. 5 фейлов в РАЗНЫХ прогонах → блок.

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-04 11:41 MSK</sub>
