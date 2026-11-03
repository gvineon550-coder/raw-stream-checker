# 🎯 Raw Stream Checker

Автономный парсер и чекер IPTV: URL и контент-фильтры, EPG, лого, детект чёрного экрана, звука и статики.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-496-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-657-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-417-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-493-purple?style=flat-square) ![режим](https://img.shields.io/badge/%F0%9F%94%AC%20DEEP-2026.11.03-orange?style=flat-square)

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
| Всего каналов | **657** |
| Живых | **496** (75.5%) |
| Мёртвых | **161** |
| С EPG | **417** (84.1%) |
| С лого | **493** (99.4%) |
| Время | **301.8 s** |
| Режим | **🔬 DEEP** |
| Обновлено | `2026-11-03T21:44:21Z` |

### Живучесть

```
LIVE  ███████████████░░░░░   75.5%  (496/657)
```

## 🚫 Отфильтровано при парсинге

| Причина | Каналов |
|---|---:|
| word | 111 |
| tld | 111 |
| group | 29 |
| tvid | 3 |

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `HlsWinkPlayer` | 219 |
| `Wink` | 203 |
| `TiviMate` | 42 |
| `Lavf` | 16 |
| `Chrome_Win` | 7 |
| `AndroidTV` | 5 |
| `OTT` | 2 |
| `VLC` | 1 |
| `SmartTV` | 1 |

## 🗂 Категории

| Категория | Каналов |
|---|---:|
| 📡 Федеральные | 102 |
| 📦 Разное | 71 |
| 🎭 Развлекательные | 61 |
| 🎬 Кино | 59 |
| 📰 Новостные | 30 |
| 🎵 Музыкальные | 29 |
| 🧸 Детские | 27 |
| ⚽ Спорт | 26 |
| 🎥 Документальные | 20 |
| 📺 Сериалы | 17 |
| 🙏 Религиозные | 13 |
| 🎭 Культура | 8 |
| 🍳 Кулинарные | 7 |
| 🌍 Путешествия | 7 |
| outdoor | 6 |
| classic | 5 |
| 📰 Бизнес | 3 |
| 🌍 Познавательные | 2 |
| 🚗 Авто | 1 |
| legislative | 1 |
| Classic | 1 |

## 🎛 Управление

**URL-фильтры:** `blocklist.json`
**Контент-фильтры:** `checker.py` — `BAD_GROUPS`, `BAD_TLD`, `BAD_WORDS`
**Разблокировать:** `problems.json` → `"blocked_until": null`
**Сменить EPG:** `config.json` → `epg_url`, `epg_url_fallback`
**Запустить:** Actions → Raw Check → Run workflow (галочка `deep`)

## ⚙️ Как это работает

- **Источники:** `sources.txt`
- **URL-фильтр:** расширения, порты, хосты, префиксы, приватные IP
- **Контент-фильтр:** группы, TLD, слова в `name`+`tvg-id`+`tvg-name`+`group`
- **Категории:** M3U → API iptv-org → `📦 Разное`
- **Логотипы:** M3U (HTTPS) → API iptv-org
- **EPG:** iptvx.one (+ fallback), fuzzy, русские имена
- **Quality:** `ffmpeg` black + signalstats + static + audio
- **Quality cache:** 7 дней (deep игнорирует)
- **Трекинг:** 5 фейлов в РАЗНЫХ прогонах → блок 30 дней

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-04 00:44 MSK</sub>
