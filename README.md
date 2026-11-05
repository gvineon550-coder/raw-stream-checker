# 🎯 Raw Stream Checker v6.1

Строгая иерархия, безопасный дедуп, Deep-сброс, реабилитация, автообучение.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-298-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-660-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-246-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-295-purple?style=flat-square) ![HD+](https://img.shields.io/badge/HD%2B-156-success?style=flat-square) ![режим](https://img.shields.io/badge/%E2%9A%A1%20normal-2026.11.05-orange?style=flat-square)

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
| Живых | **298** (45.2%) |
| Мёртвых | **362** |
| С EPG | **246** (82.6%) |
| С лого | **295** (99.0%) |
| **HD+ (720p+)** | **156** (52.3%) |
| Отсеяно по битрейту | **0** |
| Время | **79.2 s** |
| Режим | **⚡ normal** |
| Low-conf | **67** |
| Обновлено | `2026-11-05T10:05:49Z` |

### Живучесть

```
LIVE  █████████░░░░░░░░░░░   45.2%  (298/660)
```

## 🎯 Методы классификации

| Метод | Confidence | Каналов |
|---|---|---|
| `api_name` | 0.95 | 221 |
| `none` | 0.00 | 28 |
| `learned` | 0.95 | 18 |
| `group` | 0.70 | 17 |
| `api_id` | 1.00 | 9 |
| `keyword` | 0.60 | 5 |

## 🚫 Топ причин фильтрации

| Причина | Каналов | Пример |
|---|---:|---|
| `tld` | 111 | _.ua_ |
| `word` | 108 | _baby_ |
| `group` | 29 | _kids_ |
| `tvid` | 3 | _carousel.ru@plus4_ |

## 🗂 Категории

| Категория | Каналов |
|---|---:|
| 📡 Федеральные | 55 |
| 🎬 Кино | 42 |
| 📦 Разное | 40 |
| 🎭 Развлекательные | 29 |
| 📰 Новостные | 19 |
| 🎵 Музыкальные | 18 |
| ⚽ Спорт | 16 |
| 🧸 Детские | 16 |
| 📺 Сериалы | 15 |
| 🎥 Документальные | 13 |
| 🙏 Религиозные | 6 |
| 🌍 Путешествия | 5 |
| 🌍 Природа | 5 |
| 🎭 Культура | 4 |
| 🍳 Кулинарные | 4 |
| 🎭 Классика | 3 |
| 🌍 Познавательные | 3 |
| 📰 Бизнес | 2 |
| 🛒 Магазины | 2 |
| 🚗 Авто | 1 |

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Kodi` | 104 |
| `Wink` | 81 |
| `HlsWinkPlayer` | 52 |
| `TiviMate` | 29 |
| `VLC` | 13 |
| `AndroidTV` | 8 |
| `Safari_Mac` | 5 |
| `Lavf` | 5 |
| `OTT` | 1 |

## ⚙️ Как это работает

**DEEP-режим:** полностью игнорирует `problems.json`, все каналы проверяются с нуля.

**Стелс:** Accept, Accept-Language, Accept-Encoding, Connection, Origin для Wink/Rutube. HEAD → GET fallback. Ротация UA.

**Дедупликация:** по `tvg-id` (если есть) или по паре (norm_name + host).

**Битрейт:** <100 kbps — мусор (слайд-шоу), отсеивается.

**Каскад:** `api_id` (1.0) → `api_name` (0.95) → `learned` (0.95) → `fuzzy` (0.8) → `group` (0.7) → `keyword` (0.6)

**Авто-обучение:** fuzzy ≥82% → `data/learned_categories.json` (60 дней).

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-05 13:05 MSK</sub>
