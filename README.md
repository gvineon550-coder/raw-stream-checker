# 🎯 Raw Stream Checker

Автономный парсер и чекер IPTV: фильтрация URL (mcquack, cinerama, IP, :8080), контента (geo/regional/kids), EPG, лого, детект чёрного экрана, звука и статики.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-270-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-384-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-197-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-270-purple?style=flat-square) ![режим](https://img.shields.io/badge/%F0%9F%94%AC%20DEEP-2026.11.03-orange?style=flat-square)

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
| Всего каналов | **384** |
| Живых | **270** (70.3%) |
| Мёртвых | **114** |
| С EPG | **197** (73.0%) |
| С лого | **270** (100.0%) |
| Время | **178.8 s** |
| Режим | **🔬 DEEP** |
| Обновлено | `2026-11-03T21:25:54Z` |

### Живучесть

```
LIVE  ██████████████░░░░░░   70.3%  (270/384)
```

## 🚫 Отфильтровано при парсинге

| Причина | Каналов |
|---|---:|
| word | 67 |
| group | 14 |

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Wink` | 163 |
| `HlsWinkPlayer` | 74 |
| `TiviMate` | 23 |
| `AndroidTV` | 4 |
| `Lavf` | 3 |
| `VLC` | 1 |
| `OTT` | 1 |
| `SmartTV` | 1 |

## 🗂 Категории

| Категория | Каналов |
|---|---:|
| 📡 Федеральные | 94 |
| 📦 Разное | 47 |
| 📰 Новостные | 32 |
| 🎵 Музыкальные | 15 |
| 🎭 Развлекательные | 14 |
| 🎬 Кино | 13 |
| 🧸 Детские | 12 |
| 🙏 Религиозные | 12 |
| 📺 Сериалы | 10 |
| ⚽ Спорт | 7 |
| 🎥 Документальные | 4 |
| 📰 Бизнес | 3 |
| 🎭 Культура | 3 |
| Outdoor | 2 |
| 🍳 Кулинарные | 1 |
| Legislative | 1 |

## 🎛 Управление

**URL-фильтры:** `blocklist.json` (mcquack, cinerama, :8080, IP)
**Контент-фильтры:** `checker.py` — блоки `BAD_GROUPS`, `BAD_TLD`, `BAD_WORDS`
**Разблокировать канал:** `problems.json` → `"blocked_until": null`
**Сменить EPG:** `config.json` → `epg_url`, `epg_url_fallback`
**Запустить:** Actions → Raw Check → Run workflow (галочка `deep` = игнор quality cache)

## ⚙️ Как это работает

- **Источники:** из `sources.txt`
- **Фильтр URL:** blocklist (расширения, порты, хосты, префиксы, IP)
- **Фильтр контента:** группы (kids/regional/shop), TLD (.ua/.kz/...), слова в названии
- **Категории:** M3U → API iptv-org → `📦 Разное`
- **Логотипы:** M3U (HTTPS) → API iptv-org
- **EPG:** iptvx.one (+ fallback), fuzzy-матч, русские имена
- **Quality checks** (опц.): `ffmpeg` black + signalstats + static + audio
- **Quality cache:** чистые каналы не проверяются 7 дней (в deep — все)
- **Трекинг:** 5 фейлов в РАЗНЫХ прогонах → блок на 30 дней

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Все потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-04 00:25 MSK</sub>
