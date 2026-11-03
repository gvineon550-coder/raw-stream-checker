# 🎯 Raw Stream Checker

Автономный парсер и чекер IPTV-плейлистов. Парсит источники «как есть», проверяет каждый поток через ffprobe, собирает рабочий плейлист.

![живых](https://img.shields.io/badge/%D0%B6%D0%B8%D0%B2%D1%8B%D1%85-753-brightgreen?style=flat-square) ![всего](https://img.shields.io/badge/%D0%B2%D1%81%D0%B5%D0%B3%D0%BE-1051-blue?style=flat-square) ![обновлено](https://img.shields.io/badge/%D0%BE%D0%B1%D0%BD%D0%BE%D0%B2%D0%BB%D0%B5%D0%BD%D0%BE-2026.11.03-lightgrey?style=flat-square)

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
| Живых | **753** (71.6%) |
| Мёртвых | **298** |
| Время прогона | **353.2 s** |
| Обновлено | `2026-11-03T12:02:32Z` |

### Живучесть

```
LIVE  ██████████████░░░░░░   71.6%  (753/1051)
```

## 🎭 User-Agent

| UA | Каналов |
|---|---:|
| `Wink` | 713 |
| `HlsWinkPlayer` | 21 |
| `AndroidTV` | 11 |
| `VLC` | 5 |
| `TiviMate` | 3 |

## 🗂 Группы

| Группа | Каналов |
|---|---:|
| Без группы | 524 |
| General | 70 |
| Undefined | 32 |
| News | 19 |
| Movies | 17 |
| Entertainment | 15 |
| Music | 11 |
| Religious | 10 |
| Sports | 10 |
| Kids | 8 |
| Lifestyle | 5 |
| Documentary | 3 |
| Culture | 3 |
| Series | 3 |
| Outdoor | 3 |
| Cooking | 2 |
| Comedy | 2 |
| Shop | 2 |
| Auto | 1 |
| Documentary;Series | 1 |
| General;Religious | 1 |
| Education | 1 |
| Music;Religious | 1 |
| Science | 1 |
| Classic | 1 |
| Culture;News | 1 |
| Legislative | 1 |
| Family | 1 |
| General;News | 1 |
| Travel | 1 |

## ⚙️ Как это работает

- **Источники:** из `sources.txt` (формат `имя|url|приоритет`)
- **Парсинг:** `#EXTINF`, `#EXTVLCOPT`
- **Фильтр мусора:** расширения, приватные IP, редиректы, битые протоколы
- **Проверка:** HTTP pre-check + `ffprobe` + перебор 15 ходовых UA
- **HLS:** master-плейлист → variant stream
- **Итог:** `playlist.m3u` с рабочими ссылками и нужным User-Agent

<sub>🤖 Обновлено 2026-11-03 15:02 MSK</sub>
