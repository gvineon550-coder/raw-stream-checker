# 🎯 Raw Stream Checker

Автономный парсер и чекер IPTV с EPG, лого, детектом чёрного экрана, отсутствия звука и статичной картинки.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-717-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-1051-blue?style=flat-square) ![EPG](https://img.shields.io/badge/EPG-489-cyan?style=flat-square) ![лого](https://img.shields.io/badge/%D1%81%20%D0%BB%D0%BE%D0%B3%D0%BE-714-purple?style=flat-square) ![режим](https://img.shields.io/badge/%F0%9F%94%AC%20DEEP-2026.11.03-orange?style=flat-square)

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
| Всего каналов | **1051** |
| Живых | **717** (68.2%) |
| Мёртвых | **334** |
| С EPG | **489** (68.2%) |
| С лого | **714** (99.6%) |
| Время | **283.0 s** |
| Режим | **🔬 DEEP** |
| Обновлено | `2026-11-03T15:16:37Z` |

### Живучесть

```
LIVE  █████████████░░░░░░░   68.2%  (717/1051)
```

### Покрытие EPG

```
EPG   █████████████░░░░░░░   68.2%  (489/717)
```

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Wink` | 484 |
| `HlsWinkPlayer` | 160 |
| `TiviMate` | 30 |
| `OTT` | 29 |
| `VLC` | 9 |
| `AndroidTV` | 4 |
| `Chrome_Win` | 1 |

## 🗂 Категории

| Категория | Каналов |
|---|---:|
| 📡 Федеральные | 146 |
| 📦 Разное | 95 |
| 🎬 Кино | 91 |
| 🎭 Развлекательные | 76 |
| 🧸 Детские | 62 |
| 📰 Новостные | 44 |
| 🎵 Музыкальные | 44 |
| ⚽ Спорт | 35 |
| 🎥 Документальные | 21 |
| 📺 Сериалы | 20 |
| 🙏 Религиозные | 14 |
| 🍳 Кулинарные | 10 |
| outdoor | 9 |
| 🎭 Культура | 8 |
| 🌍 Путешествия | 8 |
| 🛒 Магазины | 8 |
| 🌍 Познавательные | 7 |
| classic | 6 |
| 🚗 Авто | 3 |
| 📰 Бизнес | 3 |
| Outdoor | 3 |
| legislative | 1 |
| relax | 1 |
| Classic | 1 |
| Legislative | 1 |

## 🎛 Управление

**Добавить источник:** `sources.txt` (`имя|url|приоритет`)

**Включить quality checks:** в `config.json` → `"check_black_screen": true`, `"check_audio": true`, `"check_static_image": true`

**Разблокировать канал:** в `problems.json` → `"blocked_until": null`

**Сменить EPG:** в `config.json` → `epg_url`, `epg_url_fallback`

**Запустить вручную:** Actions → Raw Check → Run workflow (галочка `deep` = игнор quality cache)

## ⚙️ Как это работает

- **Источники:** из `sources.txt`
- **Категории:** M3U → API iptv-org → `📦 Разное`
- **Логотипы:** M3U (HTTPS) → API iptv-org
- **EPG:** iptvx.one (+ fallback), fuzzy-матч, русские имена
- **Quality checks** (опц.): `ffmpeg` combined black + static + audio за один проход
- **Quality cache:** чистые каналы не проверяются 7 дней (в deep режиме — проверяются все)
- **Проблемные каналы:** проверяются каждый прогон, 5 фейлов в РАЗНЫХ прогонах → блок на 30 дней
- **Самообучение UA:** запоминает рабочий UA по хостам
- **Кэш:** warm 6ч, dead 30д, таймауты адаптивные
- **Защита:** публикация отменяется если живых < 15%

## ⚖️ Дисклеймер

Проект **не хранит и не транслирует** контент. Все потоки — из открытых источников (iptv-org). Права принадлежат правообладателям. Только для личного использования.

<sub>🤖 Обновлено 2026-11-03 18:16 MSK</sub>
