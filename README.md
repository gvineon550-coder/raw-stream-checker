# 🎯 Raw Stream Checker v6.1

Строгая иерархия, безопасный дедуп, Deep-сброс, реабилитация, автообучение.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-303-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-660-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-249-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-300-purple?style=flat-square) ![HD+](https://img.shields.io/badge/HD%2B-158-success?style=flat-square) ![режим](https://img.shields.io/badge/%F0%9F%94%AC%20DEEP-2026.11.04-orange?style=flat-square)

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
| Живых | **303** (45.9%) |
| Мёртвых | **357** |
| С EPG | **249** (82.2%) |
| С лого | **300** (99.0%) |
| **HD+ (720p+)** | **158** (52.1%) |
| Отсеяно по битрейту | **3** |
| Время | **321.7 s** |
| Режим | **🔬 DEEP** |
| Low-conf | **67** |
| Обновлено | `2026-11-04T09:18:27Z` |

### Живучесть

```
LIVE  █████████░░░░░░░░░░░   45.9%  (303/660)
```

## 🎯 Методы классификации

| Метод | Confidence | Каналов |
|---|---|---|
| `api_name` | 0.95 | 227 |
| `none` | 0.00 | 28 |
| `group` | 0.70 | 20 |
| `learned` | 0.95 | 16 |
| `api_id` | 1.00 | 9 |
| `keyword` | 0.60 | 3 |

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
| 📡 Федеральные | 55 |
| 🎬 Кино | 42 |
| 📦 Разное | 42 |
| 🎭 Развлекательные | 30 |
| 📰 Новостные | 19 |
| 🎵 Музыкальные | 19 |
| 🧸 Детские | 16 |
| ⚽ Спорт | 16 |
| 📺 Сериалы | 15 |
| 🎥 Документальные | 13 |
| 🙏 Религиозные | 6 |
| 🌍 Путешествия | 6 |
| 🌍 Природа | 5 |
| 🎭 Культура | 4 |
| 🍳 Кулинарные | 4 |
| 🎭 Классика | 3 |
| 🌍 Познавательные | 3 |
| 🛒 Магазины | 2 |
| 📰 Бизнес | 2 |
| 🚗 Авто | 1 |

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Kodi` | 106 |
| `Wink` | 86 |
| `HlsWinkPlayer` | 51 |
| `TiviMate` | 24 |
| `AndroidTV` | 11 |
| `SmartTV` | 7 |
| `Safari_Mac` | 6 |
| `okhttp` | 5 |
| `VLC` | 4 |
| `Lavf` | 3 |

## ⚙️ Как это работает

**DEEP-режим:** полностью игнорирует `problems.json`, все каналы проверяются с нуля.

**Стелс:** Accept, Accept-Language, Accept-Encoding, Connection, Origin для Wink/Rutube. HEAD → GET fallback. Ротация UA.

**Дедупликация:** по `tvg-id` (если есть) или по паре (norm_name + host).

**Битрейт:** <100 kbps — мусор (слайд-шоу), отсеивается.

**Каскад:** `api_id` (1.0) → `api_name` (0.95) → `learned` (0.95) → `fuzzy` (0.8) → `group` (0.7) → `keyword` (0.6)

**Авто-обучение:** fuzzy ≥82% → `data/learned_categories.json` (60 дней).

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-04 12:18 MSK</sub>
