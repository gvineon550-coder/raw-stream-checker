#!/usr/bin/env python3
"""Raw Stream Checker v3.1 — EPG, quality (black/audio/static), production fixes."""
import asyncio, json, os, re, sys, time, subprocess, io, gzip
import urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
from urllib.parse import urlparse, urljoin
from difflib import SequenceMatcher
import xml.etree.ElementTree as ET
import concurrent.futures
import aiohttp

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)
MSK  = timezone(timedelta(hours=3))
DEEP_CHECK = os.environ.get("DEEP_CHECK") == "1"

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

def has_cyrillic(s): return bool(re.search(r'[а-яА-ЯёЁ]', s or ''))

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
        elif line.startswith("#"): continue
        elif cur is not None:
            cur["url"] = line; out.append(cur); cur = None
    return out

# ---------- МУСОР ----------
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

# ---------- ГРУППЫ ----------
GROUP_NORMALIZE = {
    "sport": "⚽ Спорт", "sports": "⚽ Спорт", "спорт": "⚽ Спорт",
    "news": "📰 Новостные", "новости": "📰 Новостные", "новостные": "📰 Новостные",
    "movie": "🎬 Кино", "movies": "🎬 Кино", "cinema": "🎬 Кино", "кино": "🎬 Кино",
    "series": "📺 Сериалы", "сериалы": "📺 Сериалы",
    "music": "🎵 Музыкальные", "музыка": "🎵 Музыкальные", "музыкальные": "🎵 Музыкальные",
    "kids": "🧸 Детские", "children": "🧸 Детские", "family": "🧸 Детские",
    "animation": "🧸 Детские", "cartoon": "🧸 Детские",
    "детские": "🧸 Детские", "детям": "🧸 Детские",
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
    if not raw: return None
    g = raw.strip().lower()
    g_clean = re.sub(r'[^\w\s]', '', g).strip()
    if g_clean in GROUP_NORMALIZE: return GROUP_NORMALIZE[g_clean]
    for key, val in GROUP_NORMALIZE.items():
        if key in g_clean: return val
    return raw.strip()

NOISE = {"тв","tv","hd","uhd","fhd","sd","4k","1080p","720p","full","канал","channel","online","live","stream"}
def norm_name(s):
    n = (s or "").lower().replace("ё","е").replace("й","и")
    n = re.sub(r'\(.*?\)|\[.*?\]', ' ', n)
    n = re.sub(r'[^a-zа-я0-9\s]', ' ', n)
    return " ".join(w for w in n.split() if w and w not in NOISE)

TRANSLIT = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya","ї":"i","є":"e","і":"i","ґ":"g"}
def translit(s): return "".join(TRANSLIT.get(c, c) for c in (s or ""))

def extract_suffix(tvg_id):
    if not tvg_id or "@" not in tvg_id: return ""
    sfx = tvg_id.split("@", 1)[1]; low = sfx.lower()
    if low == "sd": return ""
    if low.startswith("plus") and low[4:].isdigit(): return "+" + low[4:]
    if low in ("hd","fhd","uhd","4k","1080p","720p"): return sfx.upper()
    return sfx

# ---------- API ----------
def download_sync(url, timeout=180):
    if not url: return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UAS.get("Chrome_Win", "Mozilla/5.0")})
        with urllib.request.urlopen(req, timeout=timeout) as r: data = r.read()
        if data[:2] == b'\x1f\x8b':
            try: data = gzip.decompress(data)
            except: pass
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"dl {url}: {e}"); return None

def load_api_categories():
    p = DATA/"api_cats.json"; ttl = 7 * 86400
    if p.exists():
        try:
            d = json.loads(p.read_text("utf-8"))
            if time.time() - d.get("ts", 0) < ttl:
                return d.get("cats", {}), d.get("names", {})
        except: pass
    print("[*] Загрузка категорий из iptv-org API...")
    try:
        req = urllib.request.Request("https://iptv-org.github.io/api/channels.json",
            headers={"User-Agent": UAS.get("Chrome_Win", "Mozilla/5.0")})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        cats, names = {}, {}
        for ch in data:
            cid = ch.get("id")
            if not cid: continue
            for c in (ch.get("categories") or []):
                cats[cid] = c.lower(); break
            nm = ch.get("name")
            if nm: names[nm.lower()] = cid
            for alt in (ch.get("alt_names") or []):
                if alt: names[alt.lower()] = cid
        _save(p, {"ts": int(time.time()), "cats": cats, "names": names})
        print(f"[*] Загружено {len(cats)} категорий, {len(names)} имён")
        return cats, names
    except Exception as e:
        print(f"[!] API категорий: {e}"); return {}, {}

def load_api_logos():
    p = DATA/"api_logos.json"; ttl = 7 * 86400
    if p.exists():
        try:
            d = json.loads(p.read_text("utf-8"))
            if time.time() - d.get("ts", 0) < ttl:
                return d.get("logos", {})
        except: pass
    print("[*] Загрузка логотипов из iptv-org API...")
    try:
        req = urllib.request.Request("https://iptv-org.github.io/api/logos.json",
            headers={"User-Agent": UAS.get("Chrome_Win", "Mozilla/5.0")})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
        logos = {}
        for rec in data:
            cid = rec.get("channel"); url = rec.get("url")
            if not cid or not url or not url.startswith("https://"): continue
            fmt = (rec.get("format") or "").upper()
            existing = logos.get(cid)
            if not existing: logos[cid] = url
            elif ".svg" in existing.lower() and fmt == "PNG": logos[cid] = url
        _save(p, {"ts": int(time.time()), "logos": logos})
        print(f"[*] Загружено {len(logos)} логотипов")
        return logos
    except Exception as e:
        print(f"[!] API логотипов: {e}"); return {}

# ---------- EPG ----------
def build_epg(text):
    bn, bt, bp, ic, ru = {}, {}, {}, {}, {}
    prog_ids = set()
    if not text: return bn, bt, bp, ic, ru, prog_ids
    try:
        for _, el in ET.iterparse(io.BytesIO(text.encode("utf-8")), events=("end",)):
            if el.tag == "channel":
                cid = el.get("id")
                if cid:
                    icon = el.find("icon")
                    if icon is not None and icon.get("src"): ic[cid] = icon.get("src")
                    for dn in el.findall("display-name"):
                        if dn.text:
                            orig = dn.text.strip()
                            if orig and cid not in ru and has_cyrillic(orig): ru[cid] = orig
                            nn = norm_name(orig)
                            if nn and len(nn) >= 2:
                                bn.setdefault(nn, cid)
                                tr = translit(nn)
                                if tr: bt.setdefault(tr, cid)
                                if len(nn[:6]) >= 3: bp.setdefault(nn[:6], []).append((nn, cid))
                el.clear()
            elif el.tag == "programme":
                cid = el.get("channel")
                if cid: prog_ids.add(cid)
                el.clear()
    except Exception as e: print(f"epg err: {e}")
    return bn, bt, bp, ic, ru, prog_ids

def load_epg():
    p = DATA/"epg.json"; ttl = CFG.get("epg_ttl_hours", 168) * 3600
    if p.exists():
        try:
            d = json.loads(p.read_text("utf-8"))
            if time.time() - d.get("ts", 0) < ttl:
                print(f"[*] EPG из кэша: {len(d.get('bn',{}))} имён")
                return (d.get("bn",{}), d.get("bt",{}),
                        {k: [tuple(x) for x in v] for k, v in d.get("bp",{}).items()},
                        d.get("ic",{}), d.get("ru",{}), set(d.get("prog_ids",[])))
        except: pass
    urls = [u for u in (CFG.get("epg_url",""), CFG.get("epg_url_fallback","")) if u]
    for url in urls:
        print(f"[*] Загрузка EPG: {url}")
        txt = download_sync(url, timeout=180)
        if not txt: continue
        bn, bt, bp, ic, ru, prog_ids = build_epg(txt)
        if bn and prog_ids:
            _save(p, {"ts": int(time.time()), "bn": bn, "bt": bt,
                      "bp": {k: list(v) for k, v in bp.items()},
                      "ic": ic, "ru": ru, "prog_ids": list(prog_ids)})
            print(f"[*] EPG загружен: {len(bn)} имён, {len(prog_ids)} программ")
            return bn, bt, bp, ic, ru, prog_ids
    print("[!] EPG не загружен"); return {}, {}, {}, {}, {}, set()

def resolve_epg(name, bn, bt, bp):
    nn = norm_name(name)
    if not nn: return "", "no"
    if nn in bn: return bn[nn], "by_name"
    tr = translit(nn)
    if tr and tr in bt: return bt[tr], "by_tr"
    if len(nn[:6]) >= 3 and nn[:6] in bp:
        c = bp[nn[:6]]
        if len(c) <= 3: return c[0][1], "by_pfx"
    first2 = " ".join(nn.split()[:2])
    for key in (first2, nn[:4]):
        if len(key) < 3: continue
        bkt = bp.get(key, [])
        best, br = None, 0
        for nm, cid in bkt:
            r = SequenceMatcher(None, nn, nm).ratio() * 100
            if r > br: br, best = r, cid
        if best and br >= 88: return best, "by_fuzzy"
    return "", "no"

def find_ru(name, tvg_id, bn, bt, bp, ru_disp, api_names, api_ru):
    base = tvg_id.split("@")[0] if tvg_id else ""
    sfx = extract_suffix(tvg_id)
    if base and base in ru_disp:
        return ((ru_disp[base] + " " + sfx).strip() if sfx else ru_disp[base])
    cid, _ = resolve_epg(name, bn, bt, bp)
    if cid and cid in ru_disp:
        return ((ru_disp[cid] + " " + sfx).strip() if sfx else ru_disp[cid])
    api_cid = api_names.get(norm_name(name)) or base
    if api_cid and api_cid in api_ru:
        return ((api_ru[api_cid] + " " + sfx).strip() if sfx else api_ru[api_cid])
    if cid and cid in api_ru:
        return ((api_ru[cid] + " " + sfx).strip() if sfx else api_ru[cid])
    tr = translit(norm_name(name))
    if tr and tr in bt:
        c = bt[tr]
        if c in ru_disp: return ((ru_disp[c] + " " + sfx).strip() if sfx else ru_disp[c])
        if c in api_ru: return ((api_ru[c] + " " + sfx).strip() if sfx else api_ru[c])
    return None

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
                    await asyncio.sleep(5 * (attempt + 1)); continue
                if r.status != 200:
                    print(f"[src] {name}: HTTP {r.status}"); return name, None
                return name, await r.text(errors="ignore")
        except Exception as e:
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
def load_problems(): return _load(ROOT/"problems.json", {})
def save_problems(p): _save(ROOT/"problems.json", p)
def load_quality(): return _load(DATA/"quality_cache.json", {})
def save_quality(c):
    cutoff = time.time() - 30 * 86400
    _save(DATA/"quality_cache.json", {k: v for k, v in c.items() if v.get("ts", 0) > cutoff})

def pick_ua_order(host, ua_cache, ua_scores):
    saved = ua_cache.get(host); scores = ua_scores.get(host, {})
    keys = sorted(UAS.keys(), key=lambda k: (-scores.get(k, 0), -CFG.get("ua_weights", {}).get(k, 1)))
    if saved and saved in UAS:
        if saved in keys: keys.remove(saved)
        keys.insert(0, saved); return keys[:3]
    return keys[:5]

def upd_ua_score(ua_scores, host, key, ok):
    s = ua_scores.setdefault(host, {}); s[key] = s.get(key, 0) + (2 if ok else -1)

def is_dead_cached(u, dead):
    i = dead.get(u)
    if not i: return False
    if i.get("fails", 0) < CFG.get("dead_cache_min_fails", 3): return False
    if time.time() - i.get("ts", 0) > CFG.get("dead_cache_ttl_days", 30) * 86400: return False
    return True

def mark_dead(dead, u, ok):
    if ok: dead.pop(u, None)
    else:
        p = dead.get(u, {"fails":0,"ts":0})
        p["fails"] = p.get("fails",0)+1; p["ts"] = int(time.time()); dead[u] = p

def upd_host_stat(hosts, host, ok):
    e = hosts.setdefault(host, {"ok":0,"fail":0})
    e["ok" if ok else "fail"] = e.get("ok" if ok else "fail", 0) + 1

def host_blocked(host, hosts):
    e = hosts.get(host, {})
    return e.get("ok",0) == 0 and e.get("fail",0) >= CFG.get("host_block_after_fails", 10)

def get_timeout(u, tmo):
    med = tmo.get(host_of(u), {}).get("med", 0)
    return max(3, int(med/1000*2 + 2)) if med else CFG.get("ffprobe_timeout", 8)

def upd_timeout(tmo, u, ms):
    h = host_of(u); d = tmo.setdefault(h, {"v":[]})
    v = d.get("v", [])[-20:] + [int(ms)]; d["v"] = v[-20:]
    d["med"] = sorted(d["v"])[len(d["v"])//2]

# ---------- ПРОБЛЕМЫ КАЧЕСТВА ----------
def is_problem_blocked(u, problems):
    rec = problems.get(u)
    if not rec: return False
    bu = rec.get("blocked_until")
    if not bu: return False
    return time.time() < bu

def is_problematic(u, problems):
    rec = problems.get(u)
    if not rec: return False
    return (rec.get("black_fails", 0) > 0 or rec.get("silent_fails", 0) > 0
            or rec.get("static_fails", 0) > 0)

def is_quality_fresh(u, quality):
    if DEEP_CHECK: return False
    rec = quality.get(u)
    if not rec: return False
    ttl = CFG.get("quality_check_cache_days", 7) * 86400
    return time.time() - rec.get("ts", 0) < ttl

def track_problem(problems, u, name, kind, ok, run_id=None):
    """
    Счётчик растёт только если проблема зафиксирована в РАЗНЫХ прогонах.
    Внутри одного прогона (даже с 3 URL) — считается как 1 fail.
    """
    rec = problems.setdefault(u, {
        "name": name, "black_fails": 0, "silent_fails": 0, "static_fails": 0,
        "last_ts": 0, "last_ok_ts": 0, "blocked_until": None,
        "last_fail_run": {},
    })
    rec.setdefault("black_fails", 0)
    rec.setdefault("silent_fails", 0)
    rec.setdefault("static_fails", 0)
    rec.setdefault("last_fail_run", {})

    if run_id is None:
        run_id = int(time.time() // 3600)

    rec["name"] = name
    rec["last_ts"] = int(time.time())

    if ok:
        rec["last_ok_ts"] = int(time.time())
        rec["black_fails"] = 0
        rec["silent_fails"] = 0
        rec["static_fails"] = 0
        rec["blocked_until"] = None
        rec["last_fail_run"] = {}
    else:
        last_run = rec.get("last_fail_run", {})
        # Считаем только новый прогон
        if last_run.get(kind) != run_id:
            key = f"{kind}_fails"
            rec[key] = rec.get(key, 0) + 1
            rec["last_fail_run"][kind] = run_id

        thr = CFG.get("problem_threshold", 5)
        ttl = CFG.get("problem_block_ttl_days", 30)
        if (rec.get("black_fails", 0) >= thr or rec.get("silent_fails", 0) >= thr
            or rec.get("static_fails", 0) >= thr):
            rec["blocked_until"] = int(time.time() + ttl * 86400)
            print(f"  [BLOCK] {name}: блок на {ttl} дн "
                  f"(black={rec.get('black_fails',0)}, silent={rec.get('silent_fails',0)}, static={rec.get('static_fails',0)})")

# ---------- ПРОВЕРКА ПОТОКА ----------
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
           "-show_entries","stream=codec_type,codec_name,width,height",
           "-headers",hdr,
           "-probesize",str(CFG.get("ffprobe_probesize", 32768)),
           "-analyzeduration",str(CFG.get("ffprobe_analyzeduration", 1000000)),
           "-rw_timeout",str(int(tmo * 1_000_000)),
           "-i",u]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=tmo+3)
        if r.returncode != 0: return None
        streams = json.loads(r.stdout or b"{}").get("streams") or []
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        if not has_video: return None
        v = next(s for s in streams if s.get("codec_type") == "video")
        return {"codec": v.get("codec_name"), "width": v.get("width") or 0,
                "height": v.get("height") or 0, "has_audio": has_audio}
    except: return None

def ffmpeg_quality(u, ua, ref, cookie, has_audio_track):
    """Возвращает (is_black, is_static, is_silent)."""
    check_black = CFG.get("check_black_screen", False)
    check_audio = CFG.get("check_audio", False)
    check_static = CFG.get("check_static_image", False)
    if not (check_black or check_audio or check_static):
        return False, False, False

    sample = CFG.get("quality_check_sample_sec", 5)
    timeout = CFG.get("quality_check_timeout_sec", 20)
    black_dur = CFG.get("quality_black_min_duration", 2.0)
    audio_db = CFG.get("quality_audio_min_db", -70)
    static_dur = CFG.get("quality_static_min_duration", 3.0)

    filters = []
    if check_black: filters.append(f"blackdetect=d={black_dur}:pix_th=0.10")
    if check_static: filters.append(f"freezedetect=n=0.02:d={static_dur}")

    hdr = "User-Agent: " + ua + "\r\n"
    if ref: hdr += "Referer: " + ref + "\r\n"
    if cookie: hdr += "Cookie: " + cookie + "\r\n"

    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-headers", hdr,
           "-t", str(sample), "-i", u]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    if check_audio and has_audio_track:
        cmd += ["-af", "volumedetect"]
    cmd += ["-map", "0:v?"]
    if check_audio and has_audio_track:
        cmd += ["-map", "0:a?"]
    cmd += ["-f", "null", "-"]

    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
        err = r.stderr
        is_black = check_black and "black_start" in err
        is_static = check_static and "freeze_start" in err
        is_silent = False
        if check_audio:
            if not has_audio_track:
                is_silent = True
            else:
                matches = re.findall(r"mean_volume:\s*(-inf|-?\d+(?:\.\d+)?)\s*dB", err)
                if matches:
                    vals = [float(v) for v in matches if v != "-inf"]
                    if vals:
                        is_silent = max(vals) < audio_db
        return is_black, is_static, is_silent
    except:
        return False, False, False

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

async def check_one(session, ch, sem, loop, executor, ua_cache, ua_scores, warm, dead, tmo, hosts, problems, quality):
    check_black = CFG.get("check_black_screen", False)
    check_audio = CFG.get("check_audio", False)
    check_static = CFG.get("check_static_image", False)
    quality_enabled = check_black or check_audio or check_static

    async with sem:
        for u in ch["urls"]:
            if is_dead_cached(u, dead): continue
            if is_problem_blocked(u, problems): continue
            host = host_of(u)
            if host_blocked(host, hosts): continue

            use_warm = not quality_enabled or is_quality_fresh(u, quality)
            if use_warm:
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
            need_quality = quality_enabled and (
                DEEP_CHECK or is_problematic(u, problems) or not is_quality_fresh(u, quality)
            )

            for ua_key in pick_ua_order(host, ua_cache, ua_scores):
                ua = UAS[ua_key]
                try:
                    status = await http_pre(session, u, ua, ref)
                    if status in (403, 404, 410, 451):
                        mark_dead(dead, u, False); upd_host_stat(hosts, host, False); break
                    if status == 429: continue
                    if not status:
                        upd_ua_score(ua_scores, host, ua_key, False); continue

                    target = await hls_variant(session, u, ua, ref)
                    t = get_timeout(u, tmo); t0 = time.time()
                    info = await loop.run_in_executor(executor, ffprobe_check, target, ua, ref, cookie, t)
                    upd_timeout(tmo, u, (time.time()-t0)*1000)
                    if not info:
                        upd_ua_score(ua_scores, host, ua_key, False); continue

                    if need_quality:
                        is_black, is_static, is_silent = await loop.run_in_executor(
                            executor, ffmpeg_quality, target, ua, ref, cookie, info.get("has_audio", False))
                        # run_id одинаковый для всех URL одного канала в этом прогоне
                        run_id = int(time.time() // 3600)
                        if check_black: track_problem(problems, u, ch["name"], "black", ok=not is_black, run_id=run_id)
                        if check_audio: track_problem(problems, u, ch["name"], "silent", ok=not is_silent, run_id=run_id)
                        if check_static: track_problem(problems, u, ch["name"], "static", ok=not is_static, run_id=run_id)

                        if is_black or is_silent or is_static:
                            quality.pop(u, None)
                            continue
                        quality[u] = {"ts": int(time.time()), "black_ok": True,
                                      "audio_ok": True, "static_ok": True}

                    ua_cache[host] = ua_key
                    upd_ua_score(ua_scores, host, ua_key, True)
                    upd_host_stat(hosts, host, True)
                    mark_dead(dead, u, True)
                    warm[u] = {"ts": int(time.time()), "ua_key": ua_key,
                               "codec": info.get("codec",""), "height": info.get("height",0),
                               "width": info.get("width",0)}
                    ch["working_url"] = u; ch["working_ua_key"] = ua_key
                    ch["working_ua"] = ua; ch["height"] = info.get("height", 0)
                    ch["width"] = info.get("width", 0); ch["codec"] = info.get("codec", "")
                    return ch
                except Exception as e:
                    print(f"  err {ch['name']}: {e}")
                    continue
            mark_dead(dead, u, False); upd_host_stat(hosts, host, False)
        return None

# ---------- РЕЗОЛВЫ ----------
def resolve_category(ch, api_cats, api_names):
    grp = normalize_group(ch.get("group", ""))
    if grp: return grp
    tid = (ch.get("tvg_id") or "").split("@")[0]
    if tid and tid in api_cats: return normalize_group(api_cats[tid]) or "📦 Разное"
    nm = ch.get("name", "").lower().strip()
    if nm in api_names and api_names[nm] in api_cats:
        return normalize_group(api_cats[api_names[nm]]) or "📦 Разное"
    return "📦 Разное"

def resolve_logo(ch, api_logos):
    logo = (ch.get("logo") or "").strip()
    if logo and logo.startswith("https://"): return logo
    tid = (ch.get("tvg_id") or "").split("@")[0]
    if tid and tid in api_logos: return api_logos[tid]
    return ""

def resolve_epg_for_channel(ch, prog_ids, bn, bt, bp, ru_disp, api_names, api_cats):
    tid = ch.get("tvg_id", "")
    base = tid.split("@")[0] if tid else ""
    if (tid in prog_ids) or (base and base in prog_ids): return True
    ru_name = ch["name"]
    if not has_cyrillic(ch["name"]):
        new_ru = find_ru(ch["name"], tid, bn, bt, bp, ru_disp, api_names, api_cats)
        if new_ru: ru_name = new_ru
    eid, _ = resolve_epg(ru_name, bn, bt, bp)
    if eid:
        e_base = eid.split("@")[0]
        if eid in prog_ids or e_base in prog_ids:
            ch["tvg_id"] = eid; ch["name"] = ru_name; return True
    eid, _ = resolve_epg(ch["name"], bn, bt, bp)
    if eid:
        e_base = eid.split("@")[0]
        if eid in prog_ids or e_base in prog_ids:
            ch["tvg_id"] = eid
            if ru_name != ch["name"]: ch["name"] = ru_name
            return True
    return False

# ---------- ГЕНЕРАЦИЯ ----------
def write_playlist(channels):
    epg_url = CFG.get("epg_url", "")
    header = "#EXTM3U"
    if epg_url: header += f' url-tvg="{epg_url}" tvg-shift="0"'
    lines = [header]
    for c in channels:
        attrs = []
        if c.get("tvg_id"):   attrs.append('tvg-id="' + c["tvg_id"] + '"')
        if c.get("tvg_name"): attrs.append('tvg-name="' + c["tvg_name"] + '"')
        if c.get("logo"):     attrs.append('tvg-logo="' + c["logo"] + '"')
        grp = c.get("category") or "📦 Разное"
        attrs.append('group-title="' + grp + '"')
        lines.append('#EXTINF:-1 ' + " ".join(attrs) + ',' + c["name"])
        if c.get("working_ua"): lines.append('#EXTVLCOPT:http-user-agent=' + c["working_ua"])
        if c.get("extvlc",{}).get("http-referrer"):
            lines.append('#EXTVLCOPT:http-referrer=' + c["extvlc"]["http-referrer"])
        lines.append(c["working_url"])
    (ROOT / CFG.get("output_m3u", "playlist.m3u")).write_text("\n".join(lines) + "\n", "utf-8")

def write_readme(report, working, elapsed, problems):
    repo = os.environ.get("GITHUB_REPOSITORY", "user/repo")
    branch = os.environ.get("GITHUB_REF_NAME", "main") or "main"
    raw = "https://raw.githubusercontent.com/" + repo + "/" + branch
    total = report["total"]; work = report["alive"]; dead = report["dead"]
    pct = work/total*100 if total else 0
    with_epg = report.get("with_epg", 0); with_logo = report.get("with_logo", 0)
    epg_pct = with_epg/work*100 if work else 0; logo_pct = with_logo/work*100 if work else 0

    def bar(p, w=20):
        n = max(0, min(w, int(p/100*w))); return "█"*n + "░"*(w-n)

    ua_stats = Counter(c.get("working_ua_key","?") for c in working)
    grp_stats = Counter(c.get("category") or "📦 Разное" for c in working)
    date_safe = report["generated_at"][:10].replace("-", ".")
    l_a = urllib.parse.quote("живых"); l_t = urllib.parse.quote("всего")
    l_e = urllib.parse.quote("EPG"); l_l = urllib.parse.quote("с лого")
    l_u = urllib.parse.quote("обновлено")
    mode = "🔬 DEEP" if DEEP_CHECK else "⚡ normal"
    l_m = urllib.parse.quote(mode)

    L = [
        "# 🎯 Raw Stream Checker", "",
        "Автономный парсер и чекер IPTV с EPG, лого, детектом чёрного экрана, "
        "отсутствия звука и статичной картинки.", "",
        f"![живых](https://img.shields.io/badge/{l_a}-{work}-brightgreen?style=flat-square) "
        f"![всего](https://img.shields.io/badge/{l_t}-{total}-blue?style=flat-square) "
        f"![EPG](https://img.shields.io/badge/{l_e}-{with_epg}-cyan?style=flat-square) "
        f"![лого](https://img.shields.io/badge/{l_l}-{with_logo}-purple?style=flat-square) "
        f"![режим](https://img.shields.io/badge/{l_m}-{date_safe}-orange?style=flat-square)", "",
        "## 🔗 Ссылки", "", "**Плейлист:**", "```", raw + "/playlist.m3u", "```", "",
        "**Отчёт:**", "```", raw + "/report.json", "```", "",
        "## 📊 Сводка", "", "| Показатель | Значение |", "|---|---|",
        f"| Всего каналов | **{total}** |",
        f"| Живых | **{work}** ({pct:.1f}%) |",
        f"| Мёртвых | **{dead}** |",
        f"| С EPG | **{with_epg}** ({epg_pct:.1f}%) |",
        f"| С лого | **{with_logo}** ({logo_pct:.1f}%) |",
        f"| Время | **{elapsed:.1f} s** |",
        f"| Режим | **{mode}** |",
        f"| Обновлено | `{report['generated_at']}` |", "",
        "### Живучесть", "", "```",
        f"LIVE  {bar(pct)}  {pct:5.1f}%  ({work}/{total})", "```", "",
        "### Покрытие EPG", "", "```",
        f"EPG   {bar(epg_pct)}  {epg_pct:5.1f}%  ({with_epg}/{work})", "```", "",
    ]
    if ua_stats:
        L += ["## 🎭 User-Agent", "", "| UA | Каналов |", "|---|---:|"]
        for k, v in ua_stats.most_common(): L.append(f"| `{k}` | {v} |")
        L.append("")
    if grp_stats:
        L += ["## 🗂 Категории", "", "| Категория | Каналов |", "|---|---:|"]
        for k, v in grp_stats.most_common(30): L.append(f"| {k} | {v} |")
        L.append("")

    now = time.time()
    blocked = [(u, r) for u, r in problems.items() if r.get("blocked_until") and r["blocked_until"] > now]
    if blocked:
        L += [f"## ⚠️ Заблокированные ({len(blocked)})", "", "| Канал | Причина | До |", "|---|---|---|"]
        for u, r in blocked[:20]:
            reasons = []
            thr = CFG.get("problem_threshold", 5)
            if r.get("black_fails", 0) >= thr: reasons.append("чёрный")
            if r.get("silent_fails", 0) >= thr: reasons.append("без звука")
            if r.get("static_fails", 0) >= thr: reasons.append("статичная")
            until = datetime.fromtimestamp(r["blocked_until"], timezone.utc).strftime("%Y-%m-%d")
            L.append(f"| {r.get('name','?')} | {', '.join(reasons) or '?'} | {until} |")
        if len(blocked) > 20: L.append(f"| _…ещё {len(blocked)-20}_ | | |")
        L.append("")

    L += ["## 🎛 Управление", "",
          "**Добавить источник:** `sources.txt` (`имя|url|приоритет`)", "",
          "**Включить quality checks:** в `config.json` → `\"check_black_screen\": true`, `\"check_audio\": true`, `\"check_static_image\": true`", "",
          "**Разблокировать канал:** в `problems.json` → `\"blocked_until\": null`", "",
          "**Сменить EPG:** в `config.json` → `epg_url`, `epg_url_fallback`", "",
          "**Запустить вручную:** Actions → Raw Check → Run workflow (галочка `deep` = игнор quality cache)", "",
          "## ⚙️ Как это работает", "",
          "- **Источники:** из `sources.txt`",
          "- **Категории:** M3U → API iptv-org → `📦 Разное`",
          "- **Логотипы:** M3U (HTTPS) → API iptv-org",
          "- **EPG:** iptvx.one (+ fallback), fuzzy-матч, русские имена",
          "- **Quality checks** (опц.): `ffmpeg` combined black + static + audio за один проход",
          "- **Quality cache:** чистые каналы не проверяются 7 дней (в deep режиме — проверяются все)",
          "- **Проблемные каналы:** проверяются каждый прогон, 5 фейлов в РАЗНЫХ прогонах → блок на 30 дней",
          "- **Самообучение UA:** запоминает рабочий UA по хостам",
          "- **Кэш:** warm 6ч, dead 30д, таймауты адаптивные",
          "- **Защита:** публикация отменяется если живых < 15%", "",
          "## ⚖️ Дисклеймер", "",
          "Проект **не хранит и не транслирует** контент. Все потоки — из открытых источников (iptv-org). "
          "Права принадлежат правообладателям. Только для личного использования.", "",
          "<sub>🤖 Обновлено " + now_msk() + "</sub>", ""]
    (ROOT/"README.md").write_text("\n".join(L), "utf-8")

def print_progress(done, total, ok_count, fail_count):
    pct = done * 100 // total
    bar_len = 30; filled = bar_len * done // total
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"[{bar}] {pct}% ({done}/{total}) | Живых: {ok_count} | Упало: {fail_count}", flush=True)

# ---------- MAIN ----------
async def main():
    started = time.time()
    mode = "DEEP" if DEEP_CHECK else "normal"
    print(f"=== Raw Stream Checker v3.1 [{mode}] ===")
    print(f"[*] Старт: {now_msk()}")
    sources = load_sources()
    if not sources:
        print("[!] sources.txt пуст"); return

    check_black = CFG.get("check_black_screen", False)
    check_audio = CFG.get("check_audio", False)
    check_static = CFG.get("check_static_image", False)
    quality_enabled = check_black or check_audio or check_static
    if quality_enabled:
        print(f"[!] Quality: black={check_black}, audio={check_audio}, static={check_static}")
        if DEEP_CHECK: print("[!] DEEP режим: игнорируем quality cache")

    api_cats, api_names = load_api_categories()
    api_logos = load_api_logos()
    bn, bt, bp, ic, ru_disp, prog_ids = load_epg()

    ua_cache = load_ua_cache(); ua_scores = load_ua_scores()
    warm = load_warm(); dead = load_dead(); tmo = load_tmo(); hosts = load_hosts()
    problems = load_problems(); quality = load_quality()
    print(f"[*] Кэш: warm={len(warm)} dead={len(dead)} ua_hosts={len(ua_cache)} problems={len(problems)} quality={len(quality)}")

    try:
        conn = aiohttp.TCPConnector(limit=100, ssl=False, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=conn) as session:
            print("[*] Загрузка источников...")
            src_results = await asyncio.gather(*(fetch_src(session, n, u) for n, u, _ in sources))

            channels = []
            seen = set()
            for (sname, _, prio), (_, text) in zip(sources, src_results):
                if not text: print(f"[!] {sname}: пусто"); continue
                kept = 0; junk = 0
                try: parsed = parse_m3u(text)
                except Exception as e: print(f"[!] {sname}: {e}"); continue
                for ch in parsed:
                    n, u, a = ch["name"], ch["url"], ch["attrs"]
                    if is_junk(u): junk += 1; continue
                    key = (n.lower(), u)
                    if key in seen: continue
                    seen.add(key)
                    chan = {"name": n, "url": u,
                            "tvg_id": a.get("tvg-id",""), "tvg_name": a.get("tvg-name",""),
                            "logo": a.get("tvg-logo",""), "group": a.get("group-title",""),
                            "extvlc": ch["extvlc"], "urls": [u]}
                    chan["category"] = resolve_category(chan, api_cats, api_names)
                    chan["logo"] = resolve_logo(chan, api_logos)
                    chan["has_epg"] = resolve_epg_for_channel(chan, prog_ids, bn, bt, bp, ru_disp, api_names, api_cats) if prog_ids else False
                    channels.append(chan); kept += 1
                print(f"[+] {sname}: {kept} (мусор: {junk})")

            epg_pre = sum(1 for c in channels if c.get("has_epg"))
            logo_pre = sum(1 for c in channels if c.get("logo"))
            print(f"[*] Всего: {len(channels)} | с EPG: {epg_pre} | с лого: {logo_pre}")
            if not channels: return

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=CFG.get("ffprobe_threads", 50))
            loop = asyncio.get_running_loop()
            sem = asyncio.Semaphore(CFG.get("concurrency", 80))

            done = 0; ok = 0; fail = 0
            async def wrap(ch):
                nonlocal done, ok, fail
                r = await check_one(session, ch, sem, loop, executor, ua_cache, ua_scores,
                                    warm, dead, tmo, hosts, problems, quality)
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
                print(f"[!] ПРОВАЛ: живых {len(alive)} < {threshold}. Публикация отменена.")
                (ROOT/"report_failed.json").write_text(json.dumps({
                    "total": len(channels), "alive": len(alive),
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }, ensure_ascii=False, indent=2), "utf-8")
                return

            write_playlist(alive)
            report = {
                "total": len(channels), "alive": len(alive), "dead": len(channels)-len(alive),
                "with_epg": sum(1 for c in alive if c.get("has_epg")),
                "with_logo": sum(1 for c in alive if c.get("logo")),
                "mode": mode,
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "channels": [{"name": c["name"], "url": c["working_url"], "ua": c["working_ua_key"],
                              "group": c.get("category",""), "height": c.get("height",0),
                              "logo": c.get("logo",""), "epg": c.get("has_epg", False)} for c in alive],
            }
            (ROOT/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
            write_readme(report, alive, time.time()-started, problems)

            elapsed = time.time() - started
            print("=========================================")
            print(f"[+] Готово за {elapsed:.1f}s [{mode}]")
            print(f"[+] Всего: {len(channels)} | Живых: {len(alive)} | EPG: {report['with_epg']} | Лого: {report['with_logo']}")
    finally:
        print("[*] Сохранение кэша...")
        save_ua_cache(ua_cache); save_ua_scores(ua_scores)
        save_warm({k: v for k, v in warm.items() if time.time() - v.get("ts",0) < 86400 * 7})
        save_dead(dead); save_tmo(tmo); save_hosts(hosts)
        save_problems(problems); save_quality(quality)
        print("[*] Кэш сохранен.")

if __name__ == "__main__":
    asyncio.run(main())
