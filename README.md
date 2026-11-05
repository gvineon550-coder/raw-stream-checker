# 🎯 Raw Stream Checker v6.1

Строгая иерархия, безопасный дедуп, Deep-сброс, реабилитация, автообучение.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-298-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-660-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-247-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-295-purple?style=flat-square) ![HD+](https://img.shields.io/badge/HD%2B-156-success?style=flat-square) ![режим](https://img.shields.io/badge/%F0%9F%94%AC%20DEEP-2026.11.05-orange?style=flat-square)

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
| С EPG | **247** (82.9%) |
| С лого | **295** (99.0%) |
| **HD+ (720p+)** | **156** (52.3%) |
| Отсеяно по битрейту | **0** |
| Время | **338.8 s** |
| Режим | **🔬 DEEP** |
| Low-conf | **67** |
| Обновлено | `2026-11-05T00:42:31Z` |

### Живучесть

```
LIVE  █████████░░░░░░░░░░░   45.2%  (298/660)
```

## 🎯 Методы классификации

| Метод | Confidence | Каналов |
|---|---|---|
| `api_name` | 0.95 | 222 |
| `none` | 0.00 | 27 |
| `group` | 0.70 | 21 |
| `learned` | 0.95 | 17 |
| `api_id` | 1.00 | 8 |
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
| 📡 Федеральные | 53 |
| 📦 Разное | 43 |
| 🎬 Кино | 42 |
| 🎭 Развлекательные | 29 |
| 🎵 Музыкальные | 18 |
| 📰 Новостные | 17 |
| ⚽ Спорт | 16 |
| 🧸 Детские | 16 |
| 📺 Сериалы | 15 |
| 🎥 Документальные | 13 |
| 🌍 Путешествия | 6 |
| 🙏 Религиозные | 6 |
| 🌍 Природа | 5 |
| 🍳 Кулинарные | 4 |
| 🎭 Культура | 4 |
| 🎭 Классика | 3 |
| 🌍 Познавательные | 3 |
| 📰 Бизнес | 2 |
| 🛒 Магазины | 2 |
| 🚗 Авто | 1 |

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Kodi` | 109 |
| `Wink` | 87 |
| `HlsWinkPlayer` | 49 |
| `TiviMate` | 25 |
| `AndroidTV` | 7 |
| `okhttp` | 6 |
| `Safari_Mac` | 6 |
| `VLC` | 5 |
| `SmartTV` | 2 |
| `Lavf` | 2 |

## ⚙️ Как это работает

**DEEP-режим:** полностью игнорирует `problems.json`, все каналы проверяются с нуля.

**Стелс:** Accept, Accept-Language, Accept-Encoding, Connection, Origin для Wink/Rutube. HEAD → GET fallback. Ротация UA.

**Дедупликация:** по `tvg-id` (если есть) или по паре (norm_name + host).

**Битрейт:** <100 kbps — мусор (слайд-шоу), отсеивается.

**Каскад:** `api_id` (1.0) → `api_name` (0.95) → `learned` (0.95) → `fuzzy` (0.8) → `group` (0.7) → `keyword` (0.6)

**Авто-обучение:** fuzzy ≥82% → `data/learned_categories.json` (60 дней).

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-05 03:42 MSK</sub>
