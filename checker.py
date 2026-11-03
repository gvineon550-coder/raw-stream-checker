#!/usr/bin/env python3
"""Raw Stream Checker v5.0 — stealth + smart dedup + bitrate + HEAD fallback + rotation."""
import asyncio, json, os, re, sys, time, subprocess, io, gzip, random
import urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict
from urllib.parse import urlparse, urljoin
from difflib import SequenceMatcher
import xml.etree.ElementTree as ET
import concurrent.futures
import aiohttp
from rapidfuzz import fuzz, process

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

# ---------- ПАРСИНГ (с #EXTHTTP и #KODIPROP) ----------
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
            cur = {"name": name, "attrs": attrs, "extvlc": {}, "kodiprop": {},
                   "exthttp": {}, "url": None}
        elif cur is not None and line.startswith("#EXTVLCOPT:"):
            kv = line[len("#EXTVLCOPT:"):].strip()
            if "=" in kv:
                k, v = kv.split("=", 1); cur["extvlc"][k.strip().lower()] = v.strip()
        elif cur is not None and line.startswith("#KODIPROP:"):
            kv = line[len("#KODIPROP:"):].strip()
            if "=" in kv:
                k, v = kv.split("=", 1); cur["kodiprop"][k.strip()] = v.strip()
        elif cur is not None and line.startswith("#EXTHTTP:"):
            js = line[len("#EXTHTTP:"):].strip()
            try:
                parsed = json.loads(js)
                if isinstance(parsed, dict):
                    cur["exthttp"] = {str(k): str(v) for k, v in parsed.items()}
            except: pass
        elif line.startswith("#"): continue
        elif cur is not None:
            cur["url"] = line; out.append(cur); cur = None
    return out

# ---------- URL-ФИЛЬТР ----------
PRIV_RE = re.compile(r'^https?://(localhost|127\.|0\.0\.0\.0|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)')
_BAD_EXT   = tuple(BLK.get("bad_extensions", []))
_BAD_PORTS = tuple(BLK.get("bad_ports", []))
_BAD_DOMS  = tuple(BLK.get("bad_domains_suffix", []))
_BAD_HOSTS = tuple(BLK.get("blocked_url_hosts", []))
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
    for bh in _BAD_HOSTS:
        if h == bh or h.endswith("." + bh): return True
    return False

# ---------- КОНТЕНТ-ФИЛЬТР ----------
BAD_GROUPS = ["kids","детск","children","cartoon","мульт","шопинг","shop","магазин","ювелир","adult","18+","regional","региональн"]
BAD_TLD = [".ua",".lv",".lt",".ee",".kz",".uz",".by",".az",".am",".ge",".md",".kg",".tj",".tm",".pt",".pl",".cz",".sk",".hu",".ro",".bg",".rs",".hr",".de",".fr",".it",".es",".gb",".uk",".us",".ca"]
BAD_WORDS = [
    "детск","kids","child","cartoon","мульт","карусель","carousel","в гостях у сказки",
    "капитан фантастика","мама тв","супергерои","тооку","тижи","tiji","gulli","baby",
    "disney","nick jr","nicktoons","jimjam","мультиландия","радость моя","рыжий","ниндзя",
    "черепашки","смешарик","фиксики",
    "украин","ukrain","україн","новий канал","новий","ictv","1+1","2+2","стб","тет",
    "плюс плюс","plusplus","нло","прямий","еспресо","рада","freeдом","майдан","громад",
    "галичина","нтн","мега","к1","к2","zoom украина","интер","inter","iнтер",
    "112 украина","112.ua","newsone","ziq","ukraine","ukrainian",
    "беларус","belarus","беларусь 1","беларусь 2","беларусь 3","беларусь 4","беларусь 5",
    "беларусь 24","витебск","гомель",
    "казах","kazakh","qazaq","jibek","joly","mtrk","silk way","ulytau","хабар","khabar",
    "ktk","31 канал","qazsport","kazsport","астана","astana tv","первый канал евразия",
    "uzbek","uzreport","dasturxon","киргиз","kyrgyz","таджик","tajik","туркмен","turkmen",
    "армени","armenia","h1 армения","kentron","shant","imedi","rustavi","gpbc",
    "азерб","azerbaijan","aztv","itv azerbaijan",
    "латви","latvia","ltv","эстон","estonia","err","литв","lithuania","lrt","otv латвия",
    "tbn baltia","молдов","moldova","trm","prime tv moldova",
    "rtvi","russian america","rt balkan","rt en espanol","rt español","europe","europa",
    "european","international","cis","asia","america","israel","channel 9 israel",
    "областное","краевое","городской","городская","области","республики","края",
    "leomax","magnat","top shop","нтв витрина","teleshop",
    "city eden","сити эдем","svoboda","свобода","univer","vitrina","zoopark","зоопарк",
    "doctor","home 4k","moy mir","test","demo","promo","sample",
]
FORBIDDEN_TVG_IDS = {"o.ru@sd","o.ru@international","mult","carousel.ru@plus4"}

def is_forbidden(name, tid, tvg_name, grp):
    parts = [name or "", tid or "", tvg_name or "", grp or ""]
    text = " ".join(parts).lower()
    t_low = (tid or "").lower().strip()
    for tld in BAD_TLD:
        if tld in t_low: return f"tld:{tld}"
    for bg in BAD_GROUPS:
        if bg in (grp or "").lower(): return f"group:{bg}"
    t_base = t_low.split("@")[0]
    if t_low in FORBIDDEN_TVG_IDS or t_base in FORBIDDEN_TVG_IDS: return f"tvid:{t_low}"
    for bw in BAD_WORDS:
        if bw in text: return f"word:{bw}"
    return None

# ---------- КАТЕГОРИИ ----------
CATEGORY_MAP = {
    "sports": "⚽ Спорт","sport": "⚽ Спорт","news": "📰 Новостные",
    "movies": "🎬 Кино","movie": "🎬 Кино","cinema": "🎬 Кино",
    "series": "📺 Сериалы","music": "🎵 Музыкальные",
    "kids": "🧸 Детские","children": "🧸 Детские","family": "🧸 Детские",
    "animation": "🧸 Детские","cartoon": "🧸 Детские",
    "documentary": "🎥 Документальные","history": "🎥 Документальные",
    "science": "🌍 Познавательные","education": "🌍 Познавательные",
    "entertainment": "🎭 Развлекательные","comedy": "🎭 Развлекательные",
    "lifestyle": "🎭 Развлекательные","general": "📡 Федеральные",
    "regional": "🏙 Региональные","religious": "🙏 Религиозные","religion": "🙏 Религиозные",
    "auto": "🚗 Авто","cooking": "🍳 Кулинарные","food": "🍳 Кулинарные",
    "travel": "🌍 Путешествия","culture": "🎭 Культура","business": "📰 Бизнес",
    "weather": "📰 Погода","shop": "🛒 Магазины","shopping": "🛒 Магазины",
    "outdoor": "🌍 Природа","classic": "🎭 Классика",
    "undefined": "📦 Разное","other": "📦 Разное","misc": "📦 Разное","разное": "📦 Разное",
}
KEYWORD_RULES = {
    "⚽ Спорт": ["спорт","sport","футбол","football","матч","match","хокке","hockey","теннис","бокс","ufc","mma","арена","arena","биатлон"],
    "📰 Новостные": ["новост","news","известия","рбк","вести","360","дождь","тасс","lenta","информ","24"],
    "🎬 Кино": ["кино","cinema","movie","фильм","film","боевик","комедия","ужас","детектив","премьера","tv1000","кинопоказ","иллюзион","победа"],
    "📺 Сериалы": ["сериал","series","serial","дорам","драма","мелодрам"],
    "🎵 Музыкальные": ["music","музык","муз","mtv","vh1","ru.tv","шансон","europa plus","bridge","top hit"],
    "🎭 Развлекательные": ["развлек","юмор","comedy","шоу","тнт","пятница","суббота","перец"],
    "🌍 Познавательные": ["science","наука","discovery","nat geo","history","истор","viasat","nano","животн","природа","охота","рыбалк","путешеств","365"],
    "🎥 Документальные": ["документ","documental","tlc","dmax","военн","биограф","катастроф"],
    "🧸 Детские": ["детск","child","kids","cartoon","мульт","nickelodeon","карусель","disney","boomerang","смешарик","малыш","tiji","аниме","anime","junior"],
    "🙏 Религиозные": ["религ","церков","православ","ислам","спас","soyuz","царь","3abn","троиц"],
    "🚗 Авто": ["авто","auto","drive","драйв"],
    "🍳 Кулинарные": ["кухня","еда","food","cooking","кулинар"],
    "🎭 Культура": ["культур","culture","искусств","театр"],
    "📰 Бизнес": ["бизнес","business","деньги"],
    "📰 Погода": ["погода","weather"],
}

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

def normalize_api_category(raw):
    if not raw: return None
    g = raw.strip().lower()
    if ";" in g: g = g.split(";")[0].strip()
    return CATEGORY_MAP.get(g)

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
            if d.get("v") == 3 and time.time() - d.get("ts", 0) < ttl:
                return d.get("cats", {}), d.get("names", {}), d.get("ru", {})
        except: pass
    print("[*] Загрузка категорий из iptv-org API...")
    try:
        req = urllib.request.Request("https://iptv-org.github.io/api/channels.json",
            headers={"User-Agent": UAS.get("Chrome_Win", "Mozilla/5.0")})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        cats, names, ru = {}, {}, {}
        for ch in data:
            cid = ch.get("id")
            if not cid: continue
            for c in (ch.get("categories") or []):
                cats[cid] = c.lower(); break
            nm = ch.get("name")
            if nm: names[nm.lower()] = cid
            for alt in (ch.get("alt_names") or []):
                if alt: names[alt.lower()] = cid
            for n in ([nm] if nm else []) + list(ch.get("alt_names") or []):
                if n and has_cyrillic(n): ru[cid] = n.strip(); break
        _save(p, {"v": 3, "ts": int(time.time()), "cats": cats, "names": names, "ru": ru})
        print(f"[*] Загружено {len(cats)} категорий, {len(names)} имён, {len(ru)} русских")
        return cats, names, ru
    except Exception as e:
        print(f"[!] API категорий: {e}"); return {}, {}, {}

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

# ---------- АВТО-ОБУЧЕНИЕ ----------
LEARNED_FILE = DATA/"learned_categories.json"
def load_learned():
    d = _load(LEARNED_FILE, {})
    cutoff = time.time() - 60 * 86400
    return {k: v for k, v in d.items() if v.get("ts", 0) > cutoff}

def save_learned(learned):
    _save(LEARNED_FILE, learned)

def learn_category(learned, norm_nm, category, method, confidence):
    if confidence < 0.8: return
    if not norm_nm or len(norm_nm) < 2: return
    learned[norm_nm] = {"cat": category, "method": method,
                        "conf": confidence, "ts": int(time.time())}

# ---------- КАСКАДНАЯ КЛАССИФИКАЦИЯ ----------
def classify_channel(ch, api_cats, api_names, learned):
    name = ch.get("name", "").strip()
    tvg_id = (ch.get("tvg_id") or "").split("@")[0].strip().lower()
    tvg_name = ch.get("tvg_name", "").strip()
    group = ch.get("group", "").strip()
    nn = norm_name(name)

    if nn and nn in learned:
        rec = learned[nn]
        return rec["cat"], min(rec.get("conf", 0.95), 0.95), "learned"

    if tvg_id and tvg_id in api_cats:
        norm = normalize_api_category(api_cats[tvg_id])
        if norm: return norm, 1.0, "api_id"

    if nn in api_names:
        cid = api_names[nn]
        if cid in api_cats:
            norm = normalize_api_category(api_cats[cid])
            if norm: return norm, 0.95, "api_name"

    if api_names and name:
        try:
            best = process.extractOne(name.lower(), list(api_names.keys()),
                                       scorer=fuzz.ratio, score_cutoff=88)
        except Exception:
            best = None
        if best:
            matched_name, score, _ = best
            cid = api_names.get(matched_name)
            if cid and cid in api_cats:
                norm = normalize_api_category(api_cats[cid])
                if norm: return norm, 0.8, "fuzzy"

    if group:
        g_clean = re.sub(r'[^\w\s]', '', group.strip().lower()).strip()
        for key, val in CATEGORY_MAP.items():
            if g_clean == key or g_clean.startswith(key):
                return val, 0.7, "group"

    text = f"{name} {tvg_name} {group}".lower()
    for cat, kws in KEYWORD_RULES.items():
        for kw in kws:
            if kw in text: return cat, 0.6, "keyword"

    return "📦 Разное", 0.0, "none"

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
    if base and base in ru_disp: return ((ru_disp[base] + " " + sfx).strip() if sfx else ru_disp[base])
    cid, _ = resolve_epg(name, bn, bt, bp)
    if cid and cid in ru_disp: return ((ru_disp[cid] + " " + sfx).strip() if sfx else ru_disp[cid])
    api_cid = api_names.get(norm_name(name)) or base
    if api_cid and api_cid in api_ru: return ((api_ru[api_cid] + " " + sfx).strip() if sfx else api_ru[api_cid])
    if cid and cid in api_ru: return ((api_ru[cid] + " " + sfx).strip() if sfx else api_ru[cid])
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
    """Первый — learned UA хоста (если есть). Остальные — случайно перемешаны (ротация)."""
    saved = ua_cache.get(host)
    scores = ua_scores.get(host, {})
    keys = sorted(UAS.keys(), key=lambda k: (-scores.get(k, 0), -CFG.get("ua_weights", {}).get(k, 1)))
    if saved and saved in UAS:
        if saved in keys: keys.remove(saved)
        rest = keys[:4]
        random.shuffle(rest)
        return [saved] + rest
    top = keys[:5]
    random.shuffle(top)
    return top

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
    rec = problems.setdefault(u, {
        "name": name, "black_fails": 0, "silent_fails": 0, "static_fails": 0,
        "last_ts": 0, "last_ok_ts": 0, "blocked_until": None, "last_fail_run": {},
    })
    rec.setdefault("black_fails", 0); rec.setdefault("silent_fails", 0); rec.setdefault("static_fails", 0)
    rec.setdefault("last_fail_run", {})
    if run_id is None: run_id = int(time.time() // 3600)
    rec["name"] = name; rec["last_ts"] = int(time.time())
    if ok:
        rec["last_ok_ts"] = int(time.time())
        rec["black_fails"] = 0; rec["silent_fails"] = 0; rec["static_fails"] = 0
        rec["blocked_until"] = None; rec["last_fail_run"] = {}
    else:
        last_run = rec.get("last_fail_run", {})
        if last_run.get(kind) != run_id:
            key = f"{kind}_fails"
            rec[key] = rec.get(key, 0) + 1
            rec["last_fail_run"][kind] = run_id
        thr = CFG.get("problem_threshold", 5); ttl = CFG.get("problem_block_ttl_days", 30)
        if (rec.get("black_fails", 0) >= thr or rec.get("silent_fails", 0) >= thr
            or rec.get("static_fails", 0) >= thr):
            rec["blocked_until"] = int(time.time() + ttl * 86400)
            print(f"  [BLOCK] {name}: {ttl} дн "
                  f"(black={rec.get('black_fails',0)}, silent={rec.get('silent_fails',0)}, static={rec.get('static_fails',0)})")

# ---------- СТЕЛС: ЗАГОЛОВКИ ----------
def build_http_headers(ua, ref, cookie, exthttp=None):
    headers = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }
    if ref:
        headers["Referer"] = ref
        if "wink.ru" in ref:
            headers["Origin"] = "https://wink.ru"
        elif "rutube.ru" in ref:
            headers["Origin"] = "https://rutube.ru"
    if cookie:
        headers["Cookie"] = cookie
    if exthttp and isinstance(exthttp, dict):
        for k, v in exthttp.items():
            if k.lower() not in ("host", "content-length"):
                headers[k] = v
    return headers

def get_ref(u):
    h = host_of(u)
    if "wink.ru" in h: return "https://wink.ru/"
    if "rutube.ru" in h: return "https://rutube.ru/"
    return None

# ---------- HTTP PRE (HEAD → GET fallback) ----------
async def http_pre(session, u, ua, ref, exthttp=None):
    h = build_http_headers(ua, ref, None, exthttp)
    # Пробуем HEAD (быстрее, меньше трафика)
    try:
        async with session.head(u, headers=h, timeout=aiohttp.ClientTimeout(total=CFG.get("http_timeout",5)),
                                 allow_redirects=True, ssl=False) as r:
            if r.status in (200, 206): return r.status
            if r.status in (403, 404, 410, 451): return r.status
            # 405 (Method Not Allowed) или другой → пробуем GET
    except: pass
    # Fallback: GET с Range
    h["Range"] = "bytes=0-2048"
    try:
        async with session.get(u, headers=h, timeout=aiohttp.ClientTimeout(total=CFG.get("http_timeout",5)),
                               allow_redirects=True, ssl=False) as r:
            return r.status
    except: return 0

# ---------- FFPROBE (с bitrate) ----------
def ffprobe_check(u, ua, ref, cookie, tmo, exthttp=None):
    h = build_http_headers(ua, ref, cookie, exthttp)
    hdr_str = "".join(f"{k}: {v}\r\n" for k, v in h.items())
    cmd = ["ffprobe","-hide_banner","-loglevel","error","-of","json",
           "-show_entries","stream=codec_type,codec_name,width,height:format=bit_rate",
           "-headers", hdr_str,
           "-probesize", str(CFG.get("ffprobe_probesize", 32768)),
           "-analyzeduration", str(CFG.get("ffprobe_analyzeduration", 1000000)),
           "-rw_timeout", str(int(tmo * 1_000_000)),
           "-i", u]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=tmo+3)
        if r.returncode != 0: return None
        data = json.loads(r.stdout or b"{}")
        streams = data.get("streams") or []
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        if not has_video: return None
        v = next(s for s in streams if s.get("codec_type") == "video")
        fmt = data.get("format") or {}
        try: bitrate = int(fmt.get("bit_rate", 0) or 0)
        except: bitrate = 0
        return {"codec": v.get("codec_name"), "width": v.get("width") or 0,
                "height": v.get("height") or 0, "has_audio": has_audio,
                "bitrate": bitrate}
    except: return None

def ffmpeg_quality(u, ua, ref, cookie, has_audio_track, exthttp=None):
    check_black = CFG.get("check_black_screen", False)
    check_audio = CFG.get("check_audio", False)
    check_static = CFG.get("check_static_image", False)
    if not (check_black or check_audio or check_static):
        return False, False, False
    sample = CFG.get("quality_check_sample_sec", 10)
    timeout = CFG.get("quality_check_timeout_sec", 25)
    black_dur = CFG.get("quality_black_min_duration", 3.0)
    audio_db = CFG.get("quality_audio_min_db", -70)
    static_dur = CFG.get("quality_static_min_duration", 5.0)
    filters = []
    if check_black:
        filters.append(f"blackdetect=d={black_dur}:pix_th=0.05")
        filters.append("signalstats")
    if check_static:
        filters.append(f"freezedetect=n=0.02:d={static_dur}")
    h = build_http_headers(ua, ref, cookie, exthttp)
    hdr_str = "".join(f"{k}: {v}\r\n" for k, v in h.items())
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "info", "-headers", hdr_str,
           "-t", str(sample), "-i", u]
    if filters: cmd += ["-vf", ",".join(filters)]
    if check_audio and has_audio_track: cmd += ["-af", "volumedetect"]
    cmd += ["-map", "0:v?"]
    if check_audio and has_audio_track: cmd += ["-map", "0:a?"]
    cmd += ["-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, text=True)
        err = r.stderr
        is_black_detected = check_black and "black_start" in err
        is_black_signal = False
        if check_black:
            yavg_vals = [float(x) for x in re.findall(r'YAVG:([\d\.]+)', err)]
            if yavg_vals:
                median_yavg = sorted(yavg_vals)[len(yavg_vals)//2]
                is_black_signal = median_yavg < 16
        is_black = is_black_detected or is_black_signal
        is_static = check_static and "freeze_start" in err
        is_silent = False
        if check_audio:
            if not has_audio_track: is_silent = True
            else:
                matches = re.findall(r"mean_volume:\s*(-inf|-?\d+(?:\.\d+)?)\s*dB", err)
                if matches:
                    vals = [float(v) for v in matches if v != "-inf"]
                    if vals: is_silent = max(vals) < audio_db
        return is_black, is_static, is_silent
    except: return False, False, False

async def hls_variant(session, u, ua, ref, exthttp=None):
    if not u.endswith(".m3u8"): return u
    try:
        h = build_http_headers(ua, ref, None, exthttp)
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
                    ch["bitrate"] = wc.get("bitrate", 0)
                    return ch
            ref = ch.get("extvlc", {}).get("http-referrer") or get_ref(u)
            cookie = ch.get("extvlc", {}).get("http-cookie")
            exthttp = ch.get("exthttp") or None
            need_quality = quality_enabled and (
                DEEP_CHECK or is_problematic(u, problems) or not is_quality_fresh(u, quality))
            for ua_key in pick_ua_order(host, ua_cache, ua_scores):
                ua = UAS[ua_key]
                try:
                    status = await http_pre(session, u, ua, ref, exthttp)
                    if status in (403, 404, 410, 451):
                        mark_dead(dead, u, False); upd_host_stat(hosts, host, False); break
                    if status == 429: continue
                    if not status:
                        upd_ua_score(ua_scores, host, ua_key, False); continue
                    target = await hls_variant(session, u, ua, ref, exthttp)
                    t = get_timeout(u, tmo); t0 = time.time()
                    info = await loop.run_in_executor(executor, ffprobe_check, target, ua, ref, cookie, t, exthttp)
                    upd_timeout(tmo, u, (time.time()-t0)*1000)
                    if not info:
                        upd_ua_score(ua_scores, host, ua_key, False); continue
                    if need_quality:
                        is_black, is_static, is_silent = await loop.run_in_executor(
                            executor, ffmpeg_quality, target, ua, ref, cookie, info.get("has_audio", False), exthttp)
                        run_id = int(time.time() // 3600)
                        if check_black: track_problem(problems, u, ch["name"], "black", ok=not is_black, run_id=run_id)
                        if check_audio: track_problem(problems, u, ch["name"], "silent", ok=not is_silent, run_id=run_id)
                        if check_static: track_problem(problems, u, ch["name"], "static", ok=not is_static, run_id=run_id)
                        if is_black or is_silent or is_static:
                            quality.pop(u, None); continue
                        quality[u] = {"ts": int(time.time()), "black_ok": True,
                                      "audio_ok": True, "static_ok": True}
                    ua_cache[host] = ua_key
                    upd_ua_score(ua_scores, host, ua_key, True)
                    upd_host_stat(hosts, host, True)
                    mark_dead(dead, u, True)
                    warm[u] = {"ts": int(time.time()), "ua_key": ua_key,
                               "codec": info.get("codec",""), "height": info.get("height",0),
                               "width": info.get("width",0), "bitrate": info.get("bitrate",0)}
                    ch["working_url"] = u; ch["working_ua_key"] = ua_key
                    ch["working_ua"] = ua; ch["height"] = info.get("height", 0)
                    ch["width"] = info.get("width", 0); ch["codec"] = info.get("codec", "")
                    ch["bitrate"] = info.get("bitrate", 0)
                    return ch
                except Exception as e:
                    print(f"  err {ch['name']}: {e}")
                    continue
            mark_dead(dead, u, False); upd_host_stat(hosts, host, False)
        return None

# ---------- РЕЗОЛВ EPG/ЛОГО ----------
def resolve_logo(ch, api_logos):
    logo = (ch.get("logo") or "").strip()
    if logo and logo.startswith("https://"): return logo
    tid = (ch.get("tvg_id") or "").split("@")[0]
    if tid and tid in api_logos: return api_logos[tid]
    return ""

def resolve_epg_for_channel(ch, prog_ids, bn, bt, bp, ru_disp, api_names, api_ru):
    tid = ch.get("tvg_id", "")
    base = tid.split("@")[0] if tid else ""
    if (tid in prog_ids) or (base and base in prog_ids): return True
    ru_name = ch["name"]
    if not has_cyrillic(ch["name"]):
        new_ru = find_ru(ch["name"], tid, bn, bt, bp, ru_disp, api_names, api_ru)
        if new_ru and has_cyrillic(new_ru): ru_name = new_ru
    eid, _ = resolve_epg(ru_name, bn, bt, bp)
    if eid:
        e_base = eid.split("@")[0]
        if eid in prog_ids or e_base in prog_ids:
            ch["tvg_id"] = eid
            if ru_name != ch["name"] and has_cyrillic(ru_name): ch["name"] = ru_name
            return True
    eid, _ = resolve_epg(ch["name"], bn, bt, bp)
    if eid:
        e_base = eid.split("@")[0]
        if eid in prog_ids or e_base in prog_ids:
            ch["tvg_id"] = eid
            if ru_name != ch["name"] and has_cyrillic(ru_name): ch["name"] = ru_name
            return True
    return False

# ---------- УМНАЯ ДЕДУПЛИКАЦИЯ ПО КАЧЕСТВУ ----------
def dedup_by_quality(alive):
    """
    Группирует по norm_name, в каждой группе сортирует по height desc,
    берёт лучший как основной, остальные URLs — fallback.
    """
    groups = defaultdict(list)
    for c in alive:
        key = norm_name(c["name"]) or c["name"].lower()
        groups[key].append(c)
    result = []
    for key, grp in groups.items():
        # Сортируем: высокое разрешение → выше битрейт → есть EPG
        grp.sort(key=lambda x: (
            -(x.get("height") or 0),
            -(x.get("bitrate") or 0),
            0 if x.get("has_epg") else 1,
        ))
        main = dict(grp[0])
        urls = []
        for c in grp:
            if c["working_url"] not in urls:
                urls.append(c["working_url"])
        main["urls"] = urls
        result.append(main)
    return result

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
        if c.get("extvlc",{}).get("http-cookie"):
            lines.append('#EXTVLCOPT:http-cookie=' + c["extvlc"]["http-cookie"])
        urls = [c["working_url"]] + [u for u in c.get("urls", []) if u != c["working_url"]]
        for u in urls: lines.append(u)
    (ROOT / CFG.get("output_m3u", "playlist.m3u")).write_text("\n".join(lines) + "\n", "utf-8")

def write_readme(report, working, elapsed, problems, filtered_stats, top_filtered, low_conf_count):
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
    method_stats = Counter(c.get("method","?") for c in working)
    # Топ источников по качеству (1080p+)
    hd_count = sum(1 for c in working if (c.get("height") or 0) >= 1000)
    date_safe = report["generated_at"][:10].replace("-", ".")
    l_a = urllib.parse.quote("живых"); l_t = urllib.parse.quote("всего")
    l_e = urllib.parse.quote("EPG"); l_l = urllib.parse.quote("с лого")
    l_h = urllib.parse.quote("HD+"); l_u = urllib.parse.quote("обновлено")
    mode = "🔬 DEEP" if DEEP_CHECK else "⚡ normal"
    l_m = urllib.parse.quote(mode)
    L = [
        "# 🎯 Raw Stream Checker v5.0", "",
        "Stealth-заголовки (Accept, Origin, Language), умная дедупликация по качеству, "
        "проверка битрейта, HEAD→GET fallback, ротация UA, авто-обучение категорий, "
        "детект чёрного экрана (signalstats), EPG, лого.", "",
        f"![живых](https://img.shields.io/badge/{l_a}-{work}-brightgreen?style=flat-square) "
        f"![всего](https://img.shields.io/badge/{l_t}-{total}-blue?style=flat-square) "
        f"![EPG](https://img.shields.io/badge/{l_e}-{with_epg}-cyan?style=flat-square) "
        f"![лого](https://img.shields.io/badge/{l_l}-{with_logo}-purple?style=flat-square) "
        f"![HD+](https://img.shields.io/badge/{l_h}-{hd_count}-success?style=flat-square) "
        f"![режим](https://img.shields.io/badge/{l_m}-{date_safe}-orange?style=flat-square)", "",
        "## 🔗 Ссылки", "", "**Плейлист:**", "```", raw + "/playlist.m3u", "```", "",
        "**Отчёт:**", "```", raw + "/report.json", "```", "",
        "## 📊 Сводка", "", "| Показатель | Значение |", "|---|---|",
        f"| Всего каналов | **{total}** |",
        f"| Живых | **{work}** ({pct:.1f}%) |",
        f"| Мёртвых | **{dead}** |",
        f"| С EPG | **{with_epg}** ({epg_pct:.1f}%) |",
        f"| С лого | **{with_logo}** ({logo_pct:.1f}%) |",
        f"| **HD+ (720p+)** | **{hd_count}** ({hd_count/work*100 if work else 0:.1f}%) |",
        f"| Время | **{elapsed:.1f} s** |",
        f"| Режим | **{mode}** |",
        f"| Low-conf | **{low_conf_count}** |",
        f"| Обновлено | `{report['generated_at']}` |", "",
        "### Живучесть", "", "```",
        f"LIVE  {bar(pct)}  {pct:5.1f}%  ({work}/{total})", "```", "",
    ]
    if method_stats:
        L += ["## 🎯 Методы классификации", "", "| Метод | Confidence | Каналов |", "|---|---|---|"]
        mc = {"api_id":1.0,"api_name":0.95,"learned":0.95,"fuzzy":0.8,"group":0.7,"keyword":0.6,"none":0.0,"?":0.0}
        for k, v in method_stats.most_common():
            L.append(f"| `{k}` | {mc.get(k,0):.2f} | {v} |")
        L.append("")
    if top_filtered:
        L += ["## 🚫 Топ причин фильтрации", "", "| Причина | Каналов | Пример |", "|---|---:|---|"]
        for reason, cnt, example in top_filtered[:10]:
            L.append(f"| `{reason}` | {cnt} | _{example}_ |")
        L.append("")
    if grp_stats:
        L += ["## 🗂 Категории", "", "| Категория | Каналов |", "|---|---:|"]
        for k, v in grp_stats.most_common(30): L.append(f"| {k} | {v} |")
        L.append("")
    if ua_stats:
        L += ["## 🎭 User-Agent", "", "| UA | Каналов |", "|---|---:|"]
        for k, v in ua_stats.most_common(): L.append(f"| `{k}` | {v} |")
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
    L += ["## ⚙️ Как это работает", "",
          "**Стелс:** Accept, Accept-Language, Accept-Encoding, Connection, Origin для Wink/Rutube. "
          "HEAD pre-check → GET fallback. Ротация UA (learned первый, остальные — random).", "",
          "**Дедупликация:** каналы с одинаковым именем группируются, выбирается лучшее разрешение. "
          "Остальные URLs — как fallback для плеера.", "",
          "**Битрейт:** ffprobe извлекает `format=bit_rate`. В report.json у каждого канала есть `bitrate`.", "",
          "**Каскад:** `api_id` (1.0) → `api_name` (0.95) → `learned` (0.95) → `fuzzy` (0.8) → `group` (0.7) → `keyword` (0.6) → `none`", "",
          "**Авто-обучение:** fuzzy ≥88% → `data/learned_categories.json` (60 дней). "
          "Следующий прогон — `learned` метод (мгновенно).", "",
          "**`#EXTHTTP` и `#KODIPROP`:** парсятся и передаются в заголовки ffprobe/ffmpeg.", "",
          "**Quality:** `ffmpeg` black + signalstats + static + audio. 5 фейлов в РАЗНЫХ прогонах → блок 30 дней.", "",
          "## ⚖️ Дисклеймер", "",
          "Проект **не хранит и не транслирует** контент. Потоки — из открытых источников (iptv-org). "
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
    print(f"=== Raw Stream Checker v5.0 [{mode}] ===")
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
        if DEEP_CHECK: print("[!] DEEP: игнорируем quality cache")
    api_cats, api_names, api_ru = load_api_categories()
    api_logos = load_api_logos()
    bn, bt, bp, ic, ru_disp, prog_ids = load_epg()
    ua_cache = load_ua_cache(); ua_scores = load_ua_scores()
    warm = load_warm(); dead = load_dead(); tmo = load_tmo(); hosts = load_hosts()
    problems = load_problems(); quality = load_quality()
    learned = load_learned()
    print(f"[*] Кэш: warm={len(warm)} dead={len(dead)} ua_hosts={len(ua_cache)} problems={len(problems)} quality={len(quality)} learned={len(learned)}")
    filtered_stats = Counter()
    filtered_examples = {}
    low_conf_count = 0
    conf_threshold = CFG.get("confidence_threshold", 0.7)
    try:
        conn = aiohttp.TCPConnector(limit=100, ssl=False, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=conn) as session:
            print("[*] Загрузка источников...")
            src_results = await asyncio.gather(*(fetch_src(session, n, u) for n, u, _ in sources))
            channels = []
            seen = set()
            for (sname, _, prio), (_, text) in zip(sources, src_results):
                if not text: print(f"[!] {sname}: пусто"); continue
                kept = 0; junk = 0; filtered = 0
                try: parsed = parse_m3u(text)
                except Exception as e: print(f"[!] {sname}: {e}"); continue
                for ch in parsed:
                    n, u, a = ch["name"], ch["url"], ch["attrs"]
                    if is_junk(u): junk += 1; continue
                    tid = a.get("tvg-id","")
                    tvg_name = a.get("tvg-name","")
                    grp = a.get("group-title","")
                    reason = is_forbidden(n, tid, tvg_name, grp)
                    if reason:
                        filtered += 1
                        key = reason.split(":")[0]
                        filtered_stats[key] += 1
                        if key not in filtered_examples: filtered_examples[key] = reason.split(":",1)[-1][:30]
                        continue
                    key = (n.lower(), u)
                    if key in seen: continue
                    seen.add(key)
                    chan = {"name": n, "url": u, "tvg_id": tid, "tvg_name": tvg_name,
                            "logo": a.get("tvg-logo",""), "group": grp,
                            "extvlc": ch["extvlc"], "kodiprop": ch.get("kodiprop",{}),
                            "exthttp": ch.get("exthttp",{}), "urls": [u]}
                    cat, conf, method = classify_channel(chan, api_cats, api_names, learned)
                    chan["category"] = cat
                    chan["confidence"] = conf
                    chan["method"] = method
                    if conf < conf_threshold: low_conf_count += 1
                    if method == "fuzzy" and conf >= 0.8:
                        learn_category(learned, norm_name(n), cat, method, conf)
                    chan["logo"] = resolve_logo(chan, api_logos)
                    chan["has_epg"] = resolve_epg_for_channel(chan, prog_ids, bn, bt, bp, ru_disp, api_names, api_ru) if prog_ids else False
                    channels.append(chan); kept += 1
                print(f"[+] {sname}: {kept} (мусор: {junk}, фильтр: {filtered})")
            if filtered_stats:
                print(f"[*] Отфильтровано: " + ", ".join(f"{k}={v}" for k, v in filtered_stats.most_common()))
            epg_pre = sum(1 for c in channels if c.get("has_epg"))
            logo_pre = sum(1 for c in channels if c.get("logo"))
            print(f"[*] Всего: {len(channels)} | с EPG: {epg_pre} | с лого: {logo_pre} | low-conf: {low_conf_count}")
            print(f"[*] Learned: {len(learned)}")
            if not channels: return
            # Перемешиваем для распределения нагрузки по CDN
            random.shuffle(channels)
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
            # Умная дедупликация по качеству
            before_dedup = len(alive)
            alive = dedup_by_quality(alive)
            print(f"[*] Дедупликация: {before_dedup} → {len(alive)} (склеено {before_dedup - len(alive)})")
            write_playlist(alive)
            # Статистика битрейта
            low_bitrate = sum(1 for c in alive if 0 < (c.get("bitrate") or 0) < 200000)
            report = {
                "total": len(channels), "alive": len(alive), "dead": len(channels)-len(alive),
                "with_epg": sum(1 for c in alive if c.get("has_epg")),
                "with_logo": sum(1 for c in alive if c.get("logo")),
                "hd_plus": sum(1 for c in alive if (c.get("height") or 0) >= 1000),
                "low_bitrate": low_bitrate,
                "filtered": dict(filtered_stats),
                "mode": mode,
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "channels": [{"name": c["name"], "url": c["working_url"], "ua": c["working_ua_key"],
                              "group": c.get("category",""), "height": c.get("height",0),
                              "bitrate": c.get("bitrate",0),
                              "logo": c.get("logo",""), "epg": c.get("has_epg", False),
                              "method": c.get("method",""), "confidence": c.get("confidence",0),
                              "fallbacks": len(c.get("urls", []))-1} for c in alive],
            }
            (ROOT/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
            top_filtered = [(k, v, filtered_examples.get(k,"")) for k, v in filtered_stats.most_common()]
            write_readme(report, alive, time.time()-started, problems, filtered_stats, top_filtered, low_conf_count)
            elapsed = time.time() - started
            print("=========================================")
            print(f"[+] Готово за {elapsed:.1f}s [{mode}]")
            print(f"[+] Всего: {len(channels)} | Живых: {len(alive)} | EPG: {report['with_epg']} | Лого: {report['with_logo']}")
            print(f"[+] HD+: {report['hd_plus']} | Low-bitrate: {low_bitrate} | Learned: {len(learned)}")
    finally:
        print("[*] Сохранение кэша...")
        save_ua_cache(ua_cache); save_ua_scores(ua_scores)
        save_warm({k: v for k, v in warm.items() if time.time() - v.get("ts",0) < 86400 * 7})
        save_dead(dead); save_tmo(tmo); save_hosts(hosts)
        save_problems(problems); save_quality(quality); save_learned(learned)
        print("[*] Кэш сохранен.")
if __name__ == "__main__":
    asyncio.run(main())
