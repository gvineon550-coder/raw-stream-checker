#!/usr/bin/env python3
"""Raw Stream Checker v2 — self-learning, fault-tolerant, production-ready."""
import asyncio, json, os, re, sys, time, subprocess, urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
from urllib.parse import urlparse, urljoin
import concurrent.futures
import aiohttp

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)
MSK  = timezone(timedelta(hours=3))

def _load(p, d=None):
    try: return json.loads(Path(p).read_text("utf-8"))
    except: return d if d is not None else {}

def _save(p, o):
    try: Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=1), "utf-8")
    except Exception as e: print(f"save {p}: {e}")

def now_msk(): return datetime.now(MSK).strftime("%Y-%m-%d %H:%M MSK")
def host_of(u):
    try: return urlparse(u).netloc.lower().split(":")[0]
    except: return "unknown"

CFG = _load(ROOT/"config.json", {})
UAS = _load(ROOT/"useragents.json", {})
BLK = _load(ROOT/"blocklist.json", {})

# ---------- ПАРСИНГ ----------
ATTR_RE = re.compile(r'([A-Za-z0-9_\-]+)="([^"]*)"')
def split_extinf(line):
    in_q = False
    for i, ch in enumerate(line):
        if ch == '"': in_q = not in_q
        elif ch == ',' and not in_q: return line[:i], line[i+1:].strip()
    return line, ""

def parse_m3u(text):
    out, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if line.startswith("#EXTINF"):
            m = re.match(r'#EXTINF:-?\d+\s*(.*)$', line)
            if not m: continue
            attrs_str, name = split_extinf(m.group(1))
            attrs = dict(ATTR_RE.findall(attrs_str))
            cur = {"name": name, "attrs": attrs, "extvlc": {}, "url": None}
        elif cur is not None and line.startswith("#EXTVLCOPT:"):
            kv = line[len("#EXTVLCOPT:"):].strip()
            if "=" in kv:
                k, v = kv.split("=", 1); cur["extvlc"][k.strip().lower()] = v.strip()
        elif line.startswith("#"):
            continue
        elif cur is not None:
            cur["url"] = line; out.append(cur); cur = None
    return out

# ---------- ФИЛЬТР МУСОРА ----------
PRIV_RE = re.compile(r'^https?://(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)')
_BAD_EXT   = tuple(BLK.get("bad_extensions", []))
_BAD_PORTS = tuple(BLK.get("bad_ports", []))
_BAD_DOMS  = tuple(BLK.get("bad_domains_suffix", []))
_BAD_PFX   = tuple(BLK.get("blocked_url_prefixes", []))
_BAD_CNT   = tuple(BLK.get("blocked_url_contains", []))

def is_junk(u):
    if not u or not re.match(r'^https?://', u): return True
    if u.startswith(_BAD_PFX): return True
    if any(x in u for x in _BAD_CNT): return True
    if PRIV_RE.search(u): return True
    if u.lower().split("?")[0].endswith(_BAD_EXT): return True
    for bp in _BAD_PORTS:
        if bp in u: return True
    h = host_of(u)
    for bd in _BAD_DOMS:
        if h == bd or h.endswith("." + bd): return True
    return False

# ---------- НОРМАЛИЗАЦИЯ ГРУПП ----------
GROUP_NORMALIZE = {
    "sport": "⚽ Спорт", "sports": "⚽ Спорт", "спорт": "⚽ Спорт",
    "news": "📰 Новостные", "новости": "📰 Новостные", "новостные": "📰 Новостные",
    "movie": "🎬 Кино", "movies": "🎬 Кино", "cinema": "🎬 Кино", "кино": "🎬 Кино",
    "series": "📺 Сериалы", "сериалы": "📺 Сериалы",
    "music": "🎵 Музыкальные", "музыка": "🎵 Музыкальные", "музыкальные": "🎵 Музыкальные",
    "kids": "🧸 Детские", "children": "🧸 Детские", "family": "🧸 Детские",
    "animation": "🧸 Детские", "cartoon": "🧸 Детские",
    "детские": "🧸 Детские", "детям": "🧸 Детские", "мультфильмы": "🧸 Детские",
    "documentary": "🎥 Документальные", "history": "🎥 Документальные",
    "документальные": "🎥 Документальные",
    "science": "🌍 Познавательные", "education": "🌍 Познавательные",
    "познавательные": "🌍 Познавательные",
    "entertainment": "🎭 Развлекательные", "comedy": "🎭 Развлекательные",
    "lifestyle": "🎭 Развлекательные", "развлекательные": "🎭 Развлекательные",
    "general": "📡 Федеральные", "федеральные": "📡 Федеральные",
    "regional": "🏙 Региональные", "региональные": "🏙 Региональные",
    "religious": "🙏 Религиозные", "religion": "🙏 Религиозные",
    "религиозные": "🙏 Религиозные",
    "auto": "🚗 Авто", "авто": "🚗 Авто",
    "cooking": "🍳 Кулинарные", "food": "🍳 Кулинарные", "кулинарные": "🍳 Кулинарные",
    "travel": "🌍 Путешествия", "путешествия": "🌍 Путешествия",
    "culture": "🎭 Культура", "культура": "🎭 Культура",
    "business": "📰 Бизнес", "бизнес": "📰 Бизнес",
    "weather": "📰 Погода", "погода": "📰 Погода",
    "shop": "🛒 Магазины", "shopping": "🛒 Магазины", "магазины": "🛒 Магазины",
    "undefined": "📦 Разное", "other": "📦 Разное", "misc": "📦 Разное",
    "разное": "📦 Разное",
}

def normalize_group(raw):
    if not raw:
        return None
    g = raw.strip().lower()
    g_clean = re.sub(r'[^\w\s]', '', g).strip()
    if g_clean in GROUP_NORMALIZE:
        return GROUP_NORMALIZE[g_clean]
    for key, val in GROUP_NORMALIZE.items():
        if key in g_clean:
            return val
    return raw.strip()

# ---------- API: КАТЕГОРИИ + ЛОГОТИПЫ ----------
def load_api_categories():
    p = DATA/"api_cats.json"
    ttl = 7 * 86400
    if p.exists():
        try:
            d = json.loads(p.read_text("utf-8"))
            if time.time() - d.get("ts", 0) < ttl:
                return d.get("cats", {}), d.get("names", {})
        except: pass
    print("[*] Загрузка категорий из iptv-org API...")
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://iptv-org.github.io/api/channels.json",
            headers={"User-Agent": UAS.get("Chrome_Win", "Mozilla/5.0")}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        cats = {}
        names = {}
        for ch in data:
            cid = ch.get("id")
            if not cid: continue
            for c in (ch.get("categories") or []):
                cats[cid] = c.lower()
                break
            nm = ch.get("name")
            if nm: names[nm.lower()] = cid
            for alt in (ch.get("alt_names") or []):
                if alt: names[alt.lower()] = cid
        _save(p, {"ts": int(time.time()), "cats": cats, "names": names})
        print(f"[*] Загружено {len(cats)} категорий, {len(names)} имён")
        return cats, names
    except Exception as e:
        print(f"[!] API категорий недоступен: {e}")
        return {}, {}

def load_api_logos():
    """Загружает logos.json из iptv-org API (кэш 7 дней). Возвращает dict: tvg-id → https url."""
    p = DATA/"api_logos.json"
    ttl = 7 * 86400
    if p.exists():
        try:
            d = json.loads(p.read_text("utf-8"))
            if time.time() - d.get("ts", 0) < ttl:
                return d.get("logos", {})
        except: pass
    print("[*] Загрузка логотипов из iptv-org API...")
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://iptv-org.github.io/api/logos.json",
            headers={"User-Agent": UAS.get("Chrome_Win", "Mozilla/5.0")}
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
        logos = {}
        for rec in data:
            cid = rec.get("channel")
            url = rec.get("url")
            if not cid or not url: continue
            if not url.startswith("https://"): continue
            # Приоритет: сначала PNG, потом SVG, потом всё остальное
            fmt = (rec.get("format") or "").upper()
            existing = logos.get(cid)
            if not existing:
                logos[cid] = url
            elif ".svg" in existing.lower() and fmt == "PNG":
                logos[cid] = url  # PNG лучше SVG
        _save(p, {"ts": int(time.time()), "logos": logos})
        print(f"[*] Загружено {len(logos)} логотипов")
        return logos
    except Exception as e:
        print(f"[!] API логотипов недоступен: {e}")
        return {}

def resolve_category(ch, api_cats, api_names):
    grp = normalize_group(ch.get("group", ""))
    if grp:
        return grp
    tid = (ch.get("tvg_id") or "").split("@")[0]
    if tid and tid in api_cats:
        return normalize_group(api_cats[tid]) or "📦 Разное"
    nm = ch.get("name", "").lower().strip()
    if nm in api_names:
        cid = api_names[nm]
        if cid in api_cats:
            return normalize_group(api_cats[cid]) or "📦 Разное"
    return "📦 Разное"

def resolve_logo(ch, api_logos):
    """Приоритет: M3U (если HTTPS) → API по tvg-id → API по имени → пусто."""
    # 1. Логотип из M3U (только если HTTPS)
    logo = (ch.get("logo") or "").strip()
    if logo and logo.startswith("https://"):
        return logo
    
    # 2. API по tvg-id
    tid = (ch.get("tvg_id") or "").split("@")[0]
    if tid and tid in api_logos:
        return api_logos[tid]
    
    # 3. API по имени канала (через поиск tvg-id)
    return ""

# ---------- ИСТОЧНИКИ ----------
def load_sources():
    p = ROOT/"sources.txt"
    if not p.exists(): return []
    out = []
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        parts = [x.strip() for x in line.split("|")]
        if len(parts) < 2: continue
        prio = int(parts[2]) if len(parts) > 2 and parts[2].lstrip("-").isdigit() else 5
        out.append((parts[0], parts[1], prio))
    return out

async def fetch_src(session, name, url, retries=2):
    for attempt in range(retries + 1):
        try:
            async with session.get(url, headers={"User-Agent": UAS.get("Chrome_Win","Mozilla/5.0")},
                                   timeout=aiohttp.ClientTimeout(total=60), ssl=False) as r:
                if r.status == 429:
                    wait = 5 * (attempt + 1)
                    print(f"[src] {name}: 429 rate limit, ждем {wait}s")
                    await asyncio.sleep(wait); continue
                if r.status != 200:
                    print(f"[src] {name}: HTTP {r.status}"); return name, None
                return name, await r.text(errors="ignore")
        except Exception as e:
            print(f"[src] {name}: {e} (attempt {attempt+1}/{retries+1})")
            if attempt < retries: await asyncio.sleep(3)
    return name, None

# ---------- КЭШИ ----------
def load_ua_cache(): return _load(DATA/"ua_cache.json", {})
def save_ua_cache(c): _save(DATA/"ua_cache.json", c)
def load_ua_scores(): return _load(DATA/"ua_scores.json", {})
def save_ua_scores(s): _save(DATA/"ua_scores.json", s)
def load_warm(): return _load(DATA/"warm.json", {})
def save_warm(c): _save(DATA/"warm.json", c)
def load_dead(): return _load(DATA/"dead.json", {})
def save_dead(c): _save(DATA/"dead.json", c)
def load_tmo(): return _load(DATA/"tmo.json", {})
def save_tmo(s): _save(DATA/"tmo.json", s)
def load_hosts(): return _load(DATA/"hosts.json", {})
def save_hosts(s): _save(DATA/"hosts.json", s)

def pick_ua_order(host, ua_cache, ua_scores):
    saved = ua_cache.get(host)
    scores = ua_scores.get(host, {})
    keys = sorted(UAS.keys(), key=lambda k: (-scores.get(k, 0), -CFG.get("ua_weights", {}).get(k, 1)))
    if saved and saved in UAS:
        if saved in keys: keys.remove(saved)
        keys.insert(0, saved)
        return keys[:3]
    return keys[:5]

def upd_ua_score(ua_scores, host, key, ok):
    s = ua_scores.setdefault(host, {})
    s[key] = s.get(key, 0) + (2 if ok else -1)

def is_dead_cached(u, dead):
    i = dead.get(u)
    if not i: return False
    if i.get("fails", 0) < 3: return False
    if time.time() - i.get("ts", 0) > 30 * 86400: return False
    return True

def mark_dead(dead, u, ok):
    if ok: dead.pop(u, None)
    else:
        p = dead.get(u, {"fails":0,"ts":0})
        p["fails"] = p.get("fails",0)+1; p["ts"] = int(time.time()); dead[u] = p

def upd_host_stat(hosts, host, ok):
    e = hosts.setdefault(host, {"ok":0,"fail":0})
    k = "ok" if ok else "fail"; e[k] = e.get(k, 0) + 1

def host_blocked(host, hosts):
    e = hosts.get(host, {})
    return e.get("ok",0) == 0 and e.get("fail",0) >= 10

def get_timeout(u, tmo):
    med = tmo.get(host_of(u), {}).get("med", 0)
    return max(3, int(med/1000*2 + 2)) if med else CFG.get("ffprobe_timeout", 8)

def upd_timeout(tmo, u, ms):
    h = host_of(u); d = tmo.setdefault(h, {"v":[]})
    v = d.get("v", [])[-20:] + [int(ms)]; d["v"] = v[-20:]
    d["med"] = sorted(d["v"])[len(d["v"])//2]

# ---------- ПРОВЕРКА ----------
def get_ref(u):
    h = host_of(u)
    if "wink.ru" in h: return "https://wink.ru/"
    if "rutube.ru" in h: return "https://rutube.ru/"
    return None

def ffprobe_check(u, ua, ref, cookie, tmo):
    hdr = "User-Agent: " + ua + "\r\n"
    if ref: hdr += "Referer: " + ref + "\r\n"
    if cookie: hdr += "Cookie: " + cookie + "\r\n"
    cmd = ["ffprobe","-hide_banner","-loglevel","error","-of","json",
           "-select_streams","v:0",
           "-show_entries","stream=codec_name,width,height",
           "-headers",hdr,
           "-probesize",str(CFG.get("ffprobe_probesize", 32768)),
           "-analyzeduration",str(CFG.get("ffprobe_analyzeduration", 1000000)),
           "-rw_timeout",str(int(tmo * 1_000_000)),
           "-i",u]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=tmo+3)
        if r.returncode != 0: return None
        streams = json.loads(r.stdout or b"{}").get("streams") or []
        if not streams: return None
        s = streams[0]
        return {"codec": s.get("codec_name"), "width": s.get("width") or 0, "height": s.get("height") or 0}
    except: return None

async def hls_variant(session, u, ua, ref):
    if not u.endswith(".m3u8"): return u
    try:
        h = {"User-Agent": ua}
        if ref: h["Referer"] = ref
        async with session.get(u, headers=h, timeout=aiohttp.ClientTimeout(total=8), ssl=False) as r:
            if r.status != 200: return u
            txt = await r.text()
            if "#EXT-X-STREAM-INF" not in txt: return u
            lines = txt.splitlines()
            for i, ln in enumerate(lines):
                if ln.startswith("#EXT-X-STREAM-INF"):
                    for j in range(i+1, len(lines)):
                        nxt = lines[j].strip()
                        if nxt and not nxt.startswith("#"): return urljoin(u, nxt)
    except: pass
    return u

async def http_pre(session, u, ua, ref):
    h = {"User-Agent": ua, "Range": "bytes=0-2048"}
    if ref: h["Referer"] = ref
    try:
        async with session.get(u, headers=h, timeout=aiohttp.ClientTimeout(total=CFG.get("http_timeout",5)),
                               allow_redirects=True, ssl=False) as r:
            return r.status
    except: return 0

async def check_one(session, ch, sem, loop, executor, ua_cache, ua_scores, warm, dead, tmo, hosts):
    async with sem:
        for u in ch["urls"]:
            if is_dead_cached(u, dead): continue
            host = host_of(u)
            if host_blocked(host, hosts): continue
            
            wc = warm.get(u)
            if wc and time.time() - wc.get("ts", 0) < CFG.get("warm_cache_ttl_hours", 6) * 3600:
                ch["working_url"] = u
                ch["working_ua_key"] = wc["ua_key"]
                ch["working_ua"] = UAS.get(wc["ua_key"], "")
                ch["height"] = wc.get("height", 0)
                ch["width"] = wc.get("width", 0)
                ch["codec"] = wc.get("codec", "")
                return ch

            ref = ch.get("extvlc", {}).get("http-referrer") or get_ref(u)
            cookie = ch.get("extvlc", {}).get("http-cookie")

            for ua_key in pick_ua_order(host, ua_cache, ua_scores):
                ua = UAS[ua_key]
                try:
                    status = await http_pre(session, u, ua, ref)
                    if status in (403, 404, 410, 451):
                        mark_dead(dead, u, False); upd_host_stat(hosts, host, False)
                        break
                    if status == 429:
                        continue
                    if not status:
                        upd_ua_score(ua_scores, host, ua_key, False); continue

                    target = await hls_variant(session, u, ua, ref)
                    t = get_timeout(u, tmo); t0 = time.time()
                    info = await loop.run_in_executor(executor, ffprobe_check, target, ua, ref, cookie, t)
                    upd_timeout(tmo, u, (time.time()-t0)*1000)

                    if info:
                        ua_cache[host] = ua_key
                        upd_ua_score(ua_scores, host, ua_key, True)
                        upd_host_stat(hosts, host, True)
                        mark_dead(dead, u, True)
                        warm[u] = {"ts": int(time.time()), "ua_key": ua_key,
                                   "codec": info.get("codec",""), "height": info.get("height",0),
                                   "width": info.get("width",0)}
                        ch["working_url"] = u
                        ch["working_ua_key"] = ua_key
                        ch["working_ua"] = ua
                        ch["height"] = info.get("height", 0)
                        ch["width"] = info.get("width", 0)
                        ch["codec"] = info.get("codec", "")
                        return ch
                    upd_ua_score(ua_scores, host, ua_key, False)
                except Exception as e:
                    print(f"  err {ch['name']}: {e}")
                    continue
            mark_dead(dead, u, False); upd_host_stat(hosts, host, False)
        return None

# ---------- ГЕНЕРАЦИЯ ----------
def write_playlist(channels):
    lines = ["#EXTM3U"]
    for c in channels:
        attrs = []
        if c.get("tvg_id"):   attrs.append('tvg-id="' + c["tvg_id"] + '"')
        if c.get("tvg_name"): attrs.append('tvg-name="' + c["tvg_name"] + '"')
        if c.get("logo"):     attrs.append('tvg-logo="' + c["logo"] + '"')
        
        grp = c.get("category") or "📦 Разное"
        attrs.append('group-title="' + grp + '"')
        
        attr_str = " ".join(attrs)
        lines.append('#EXTINF:-1 ' + attr_str + ',' + c["name"])
        if c.get("working_ua"): lines.append('#EXTVLCOPT:http-user-agent=' + c["working_ua"])
        if c.get("extvlc",{}).get("http-referrer"): lines.append('#EXTVLCOPT:http-referrer=' + c["extvlc"]["http-referrer"])
        lines.append(c["working_url"])
    (ROOT / CFG.get("output_m3u", "playlist.m3u")).write_text("\n".join(lines) + "\n", "utf-8")

def write_readme(report, working, elapsed):
    repo = os.environ.get("GITHUB_REPOSITORY", "user/repo")
    branch = os.environ.get("GITHUB_REF_NAME", "main") or "main"
    raw = "https://raw.githubusercontent.com/" + repo + "/" + branch
    total = report["total"]; work = report["alive"]; dead = report["dead"]
    pct = work/total*100 if total else 0
    def bar(p, w=20):
        n = max(0, min(w, int(p/100*w))); return "█"*n + "░"*(w-n)
    ua_stats = Counter(c.get("working_ua_key","?") for c in working)
    grp_stats = Counter(c.get("category") or "📦 Разное" for c in working)
    with_logo = sum(1 for c in working if c.get("logo"))
    date_safe = report["generated_at"][:10].replace("-", ".")
    lbl_a = urllib.parse.quote("живых")
    lbl_t = urllib.parse.quote("всего")
    lbl_l = urllib.parse.quote("с лого")
    lbl_u = urllib.parse.quote("обновлено")
    L = [
        "# 🎯 Raw Stream Checker", "",
        "Автономный самообучающийся парсер и чекер IPTV. Парсит источники «как есть», "
        "проверяет каждый поток через `ffprobe`, собирает рабочий плейлист. "
        "Умный UA-подбор, кэш живых/мёртвых, адаптивные таймауты, единые категории и логотипы из iptv-org API.", "",
        "![живых](https://img.shields.io/badge/" + lbl_a + "-" + str(work) + "-brightgreen?style=flat-square) " +
        "![всего](https://img.shields.io/badge/" + lbl_t + "-" + str(total) + "-blue?style=flat-square) " +
        "![лого](https://img.shields.io/badge/" + lbl_l + "-" + str(with_logo) + "-purple?style=flat-square) " +
        "![обновлено](https://img.shields.io/badge/" + lbl_u + "-" + date_safe + "-lightgrey?style=flat-square)", "",
        "## 🔗 Ссылки", "", "**Плейлист:**", "```", raw + "/playlist.m3u", "```", "",
        "**Отчёт:**", "```", raw + "/report.json", "```", "",
        "## 📊 Сводка", "", "| Показатель | Значение |", "|---|---|",
        "| Всего каналов | **" + str(total) + "** |",
        "| Живых | **" + str(work) + "** (" + f"{pct:.1f}" + "%) |",
        "| Мёртвых | **" + str(dead) + "** |",
        "| С логотипом | **" + str(with_logo) + "** |",
        "| Время прогона | **" + f"{elapsed:.1f}" + " s** |",
        "| Обновлено | `" + report['generated_at'] + "` |", "",
        "### Живучесть", "", "```",
        "LIVE  " + bar(pct) + "  " + f"{pct:5.1f}" + "%  (" + str(work) + "/" + str(total) + ")", "```", "",
    ]
    if ua_stats:
        L += ["## 🎭 User-Agent", "", "| UA | Каналов |", "|---|---:|"]
        for k, v in ua_stats.most_common(): L.append("| `" + k + "` | " + str(v) + " |")
        L.append("")
    if grp_stats:
        L += ["## 🗂 Категории", "", "| Категория | Каналов |", "|---|---:|"]
        for k, v in grp_stats.most_common(30): L.append("| " + k + " | " + str(v) + " |")
        L.append("")
    L += ["## ⚙️ Как это работает", "",
          "- **Источники:** из `sources.txt` (формат `имя|url|приоритет`)",
          "- **Категории:** M3U → API iptv-org по `tvg-id` → API по имени → `📦 Разное`",
          "- **Логотипы:** M3U (только HTTPS) → API iptv-org по `tvg-id`",
          "- **Нормализация:** `Sports` и `Спорт` → `⚽ Спорт`, `Movies` и `Кино` → `🎬 Кино`",
          "- **Фильтр мусора:** расширения, приватные IP, редиректы, битые протоколы",
          "- **Проверка:** HTTP pre-check + `ffprobe` + умный перебор UA по хосту",
          "- **Самообучение:** запоминает рабочий UA для каждого хоста",
          "- **Кэш:** живые 6ч, мёртвые 30 дней, таймауты адаптивные",
          "- **HLS:** master-плейлист → variant stream",
          "- **Защита:** публикация отменяется если живых < 15%", "",
          "## ⚖️ Дисклеймер", "",
          "Этот проект **не хранит и не транслирует** видеоконтент. Все потоки берутся из открытых источников "
          "(в частности, репозитория [iptv-org](https://github.com/iptv-org/iptv)). "
          "Права на каналы и передачи принадлежат их правообладателям. "
          "Проект создан для личного использования и не преследует коммерческих целей.", "",
          "<sub>🤖 Обновлено " + now_msk() + "</sub>", ""]
    (ROOT/"README.md").write_text("\n".join(L), "utf-8")

def print_progress(done, total, ok_count, fail_count):
    pct = done * 100 // total
    bar_len = 30
    filled = bar_len * done // total
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"[{bar}] {pct}% ({done}/{total}) | Живых: {ok_count} | Упало: {fail_count}", flush=True)

# ---------- MAIN ----------
async def main():
    started = time.time()
    print("=== Raw Stream Checker v2 ===")
    print(f"[*] Старт: {now_msk()}")
    sources = load_sources()
    if not sources:
        print("[!] sources.txt пуст"); return

    api_cats, api_names = load_api_categories()
    api_logos = load_api_logos()

    ua_cache = load_ua_cache()
    ua_scores = load_ua_scores()
    warm = load_warm()
    dead = load_dead()
    tmo = load_tmo()
    hosts = load_hosts()
    print(f"[*] Кэш: warm={len(warm)} dead={len(dead)} ua_hosts={len(ua_cache)} logos={len(api_logos)}")

    try:
        conn = aiohttp.TCPConnector(limit=100, ssl=False, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=conn) as session:
            print("[*] Загрузка источников...")
            src_results = await asyncio.gather(*(fetch_src(session, n, u) for n, u, _ in sources))

            channels = []
            seen = set()
            for (sname, _, prio), (_, text) in zip(sources, src_results):
                if not text:
                    print(f"[!] {sname}: пустой ответ, пропускаем")
                    continue
                kept = 0; junk = 0
                try:
                    parsed = parse_m3u(text)
                except Exception as e:
                    print(f"[!] {sname}: парсинг упал ({e})")
                    continue
                for ch in parsed:
                    n, u, a = ch["name"], ch["url"], ch["attrs"]
                    if is_junk(u): junk += 1; continue
                    key = (n.lower(), u)
                    if key in seen: continue
                    seen.add(key)
                    chan = {
                        "name": n, "url": u,
                        "tvg_id": a.get("tvg-id",""), "tvg_name": a.get("tvg-name",""),
                        "logo": a.get("tvg-logo",""), "group": a.get("group-title",""),
                        "extvlc": ch["extvlc"], "urls": [u],
                    }
                    chan["category"] = resolve_category(chan, api_cats, api_names)
                    chan["logo"] = resolve_logo(chan, api_logos)
                    channels.append(chan)
                    kept += 1
                print(f"[+] {sname}: {kept} (мусор: {junk})")

            cats_preview = Counter(c["category"] for c in channels)
            top = ", ".join(f"{k}={v}" for k, v in cats_preview.most_common(6))
            print(f"[*] Топ категорий: {top}")
            logos_preview = sum(1 for c in channels if c.get("logo"))
            print(f"[*] Всего уникальных: {len(channels)} | с лого: {logos_preview}")
            if not channels:
                print("[!] Нет каналов для проверки — выходим"); return

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=CFG.get("ffprobe_threads", 50))
            loop = asyncio.get_running_loop()
            sem = asyncio.Semaphore(CFG.get("concurrency", 80))

            done = 0; ok = 0; fail = 0
            async def wrap(ch):
                nonlocal done, ok, fail
                r = await check_one(session, ch, sem, loop, executor, ua_cache, ua_scores, warm, dead, tmo, hosts)
                done += 1
                if r: ok += 1
                else: fail += 1
                step = max(1, len(channels)//20)
                if done % step == 0 or done == len(channels) or done == 1:
                    print_progress(done, len(channels), ok, fail)
                return r

            print(f"[*] Проверка ({len(channels)} шт.)...")
            rs = await asyncio.gather(*[wrap(c) for c in channels], return_exceptions=True)
            executor.shutdown()

            alive = [r for r in rs if r and not isinstance(r, Exception)]

            threshold = max(10, int(len(channels) * 0.15))
            if len(alive) < threshold:
                print(f"[!] ПРОВАЛ: живых {len(alive)} < порога {threshold}. Публикация отменена.")
                (ROOT/"report_failed.json").write_text(json.dumps({
                    "total": len(channels), "alive": len(alive),
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }, ensure_ascii=False, indent=2), "utf-8")
                return

            write_playlist(alive)

            report = {
                "total": len(channels), "alive": len(alive), "dead": len(channels) - len(alive),
                "with_logo": sum(1 for c in alive if c.get("logo")),
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "channels": [{"name": c["name"], "url": c["working_url"], "ua": c["working_ua_key"],
                              "group": c.get("category",""), "height": c.get("height",0),
                              "logo": c.get("logo","")} for c in alive],
            }
            (ROOT/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
            write_readme(report, alive, time.time()-started)

            elapsed = time.time() - started
            print("=========================================")
            print(f"[+] Готово за {elapsed:.1f}s")
            print(f"[+] Всего:   {len(channels)}")
            print(f"[+] Живых:   {len(alive)}")
            print(f"[+] С лого:  {report['with_logo']}")
            print(f"[+] Мёртвых: {len(channels)-len(alive)}")

    finally:
        print("[*] Сохранение кэша...")
        save_ua_cache(ua_cache)
        save_ua_scores(ua_scores)
        save_warm({k: v for k, v in warm.items() if time.time() - v.get("ts",0) < 86400 * 7})
        save_dead(dead)
        save_tmo(tmo)
        save_hosts(hosts)
        print("[*] Кэш сохранен.")

if __name__ == "__main__":
    asyncio.run(main())
