# 🎯 Raw Stream Checker v6.0

Строгая иерархия категорий, Deep-сброс блокировок, реабилитация, автообучение, EPG, лого.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-320-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-660-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-256-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-317-purple?style=flat-square) ![HD+](https://img.shields.io/badge/HD%2B-162-success?style=flat-square) ![режим](https://img.shields.io/badge/%F0%9F%94%AC%20DEEP-2026.11.04-orange?style=flat-square)

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
| Живых | **320** (48.5%) |
| Мёртвых | **340** |
| С EPG | **256** (80.0%) |
| С лого | **317** (99.1%) |
| **HD+ (720p+)** | **162** (50.6%) |
| Отсеяно по битрейту | **3** |
| Время | **290.4 s** |
| Режим | **🔬 DEEP** |
| Low-conf | **434** |
| Обновлено | `2026-11-04T08:51:02Z` |

### Живучесть

```
LIVE  █████████░░░░░░░░░░░   48.5%  (320/660)
```

## 🎯 Методы классификации

| Метод | Confidence | Каналов |
|---|---|---|
| `none` | 0.00 | 170 |
| `keyword` | 0.60 | 67 |
| `group` | 0.70 | 57 |
| `learned` | 0.95 | 17 |
| `api_id` | 1.00 | 9 |

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
| 📦 Разное | 189 |
| 📰 Новостные | 31 |
| 📡 Федеральные | 28 |
| 🎵 Музыкальные | 13 |
| ⚽ Спорт | 11 |
| 🎬 Кино | 10 |
| 🎭 Развлекательные | 9 |
| 📺 Сериалы | 7 |
| 🌍 Познавательные | 5 |
| 🎥 Документальные | 4 |
| 🙏 Религиозные | 4 |
| 🧸 Детские | 3 |
| 🍳 Кулинарные | 2 |
| 🌍 Путешествия | 2 |
| 🎭 Классика | 1 |
| 📰 Бизнес | 1 |

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Kodi` | 104 |
| `Wink` | 98 |
| `HlsWinkPlayer` | 52 |
| `TiviMate` | 27 |
| `VLC` | 12 |
| `AndroidTV` | 7 |
| `Safari_Mac` | 6 |
| `SmartTV` | 5 |
| `okhttp` | 5 |
| `Chrome_Win` | 2 |
| `Lavf` | 2 |

## ⚙️ Как это работает

**DEEP-режим:** полностью игнорирует `problems.json` (все каналы проверяются с нуля). Проблемы не сохраняются в DEEP.

**Стелс:** Accept, Accept-Language, Accept-Encoding, Connection, Origin для Wink/Rutube. HEAD pre-check → GET fallback. Ротация UA.

**Дедупликация:** группировка по (norm_name + tvg_id/host) → лучшее разрешение + битрейт.

**Битрейт:** `quality_min_bitrate = 100000` (100 kbps). Мусор (74 bps) отсеивается.

**Каскад:** `api_id` (1.0) → `api_name` (0.95) → `learned` (0.95) → `fuzzy` (0.8) → `group` (0.7) → `keyword` (0.6) → `none`

**Авто-обучение:** fuzzy ≥82% → `data/learned_categories.json` (60 дней).

**Quality:** `ffmpeg` black + signalstats + static + audio. 5 фейлов в РАЗНЫХ прогонах → блок 30 дней.

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-04 11:51 MSK</sub>
