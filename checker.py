#!/usr/bin/env python3
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

async def fetch_src(session, name, url):
    try:
        async with session.get(url, headers={"User-Agent": UAS.get("Chrome_Win","Mozilla/5.0")},
                               timeout=aiohttp.ClientTimeout(total=60), ssl=False) as r:
            if r.status != 200:
                print(f"[src] {name}: HTTP {r.status}"); return name, None
            return name, await r.text(errors="ignore")
    except Exception as e:
        print(f"[src] {name}: {e}"); return name, None

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

async def check_one(session, ch, sem, loop, executor):
    async with sem:
        for u in ch["urls"]:
            ref = ch.get("extvlc", {}).get("http-referrer") or get_ref(u)
            cookie = ch.get("extvlc", {}).get("http-cookie")
            for ua_key, ua in UAS.items():
                status = await http_pre(session, u, ua, ref)
                if status in (403, 404, 410, 451): break
                if not status: continue
                target = await hls_variant(session, u, ua, ref)
                info = await loop.run_in_executor(executor, ffprobe_check, target, ua, ref, cookie, CFG.get("ffprobe_timeout", 8))
                if info:
                    ch["working_url"] = u
                    ch["working_ua"] = ua
                    ch["working_ua_key"] = ua_key
                    ch["height"] = info.get("height", 0)
                    ch["width"] = info.get("width", 0)
                    ch["codec"] = info.get("codec", "")
                    return ch
        return None

def write_playlist(channels):
    lines = ["#EXTM3U"]
    for c in channels:
        attrs = []
        if c.get("tvg_id"):   attrs.append('tvg-id="' + c["tvg_id"] + '"')
        if c.get("tvg_name"): attrs.append('tvg-name="' + c["tvg_name"] + '"')
        if c.get("logo"):     attrs.append('tvg-logo="' + c["logo"] + '"')
        if c.get("group"):    attrs.append('group-title="' + c["group"] + '"')
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
    grp_stats = Counter(c.get("group") or "Без группы" for c in working)
    date_safe = report["generated_at"][:10].replace("-", ".")
    lbl_a = urllib.parse.quote("живых")
    lbl_t = urllib.parse.quote("всего")
    lbl_u = urllib.parse.quote("обновлено")
    L = [
        "# 🎯 Raw Stream Checker", "",
        "Автономный парсер и чекер IPTV-плейлистов. Парсит источники «как есть», проверяет каждый поток через ffprobe, собирает рабочий плейлист.", "",
        "![живых](https://img.shields.io/badge/" + lbl_a + "-" + str(work) + "-brightgreen?style=flat-square) " +
        "![всего](https://img.shields.io/badge/" + lbl_t + "-" + str(total) + "-blue?style=flat-square) " +
        "![обновлено](https://img.shields.io/badge/" + lbl_u + "-" + date_safe + "-lightgrey?style=flat-square)", "",
        "## 🔗 Ссылки", "", "**Плейлист:**", "```", raw + "/playlist.m3u", "```", "",
        "**Отчёт:**", "```", raw + "/report.json", "```", "",
        "## 📊 Сводка", "", "| Показатель | Значение |", "|---|---|",
        "| Всего каналов | **" + str(total) + "** |",
        "| Живых | **" + str(work) + "** (" + f"{pct:.1f}" + "%) |",
        "| Мёртвых | **" + str(dead) + "** |",
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
        L += ["## 🗂 Группы", "", "| Группа | Каналов |", "|---|---:|"]
        for k, v in grp_stats.most_common(30): L.append("| " + k + " | " + str(v) + " |")
        L.append("")
    L += ["## ⚙️ Как это работает", "",
          "- **Источники:** из `sources.txt` (формат `имя|url|приоритет`)",
          "- **Парсинг:** `#EXTINF`, `#EXTVLCOPT`",
          "- **Фильтр мусора:** расширения, приватные IP, редиректы, битые протоколы",
          "- **Проверка:** HTTP pre-check + `ffprobe` + перебор 15 ходовых UA",
          "- **HLS:** master-плейлист → variant stream",
          "- **Итог:** `playlist.m3u` с рабочими ссылками и нужным User-Agent", "",
          "<sub>🤖 Обновлено " + now_msk() + "</sub>", ""]
    (ROOT/"README.md").write_text("\n".join(L), "utf-8")

def print_progress(done, total, ok_count, fail_count):
    pct = done * 100 // total
    bar_len = 30
    filled = bar_len * done // total
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"[{bar}] {pct}% ({done}/{total}) | Живых: {ok_count} | Упало: {fail_count}", flush=True)

async def main():
    started = time.time()
    print("=== Raw Stream Checker ===")
    print(f"[*] Старт: {now_msk()}")
    sources = load_sources()
    if not sources:
        print("[!] sources.txt пуст"); return

    conn = aiohttp.TCPConnector(limit=100, ssl=False, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=conn) as session:
        print("[*] Загрузка источников...")
        src_results = await asyncio.gather(*(fetch_src(session, n, u) for n, u, _ in sources))

        channels = []
        seen = set()
        for (sname, _, prio), (_, text) in zip(sources, src_results):
            if not text: continue
            kept = 0; junk = 0
            for ch in parse_m3u(text):
                n, u, a = ch["name"], ch["url"], ch["attrs"]
                if is_junk(u): junk += 1; continue
                key = (n.lower(), u)
                if key in seen: continue
                seen.add(key)
                channels.append({
                    "name": n, "url": u,
                    "tvg_id": a.get("tvg-id",""), "tvg_name": a.get("tvg-name",""),
                    "logo": a.get("tvg-logo",""), "group": a.get("group-title",""),
                    "extvlc": ch["extvlc"], "urls": [u],
                })
                kept += 1
            print(f"[+] {sname}: {kept} (мусор: {junk})")

        print(f"[*] Всего уникальных: {len(channels)}")

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=CFG.get("ffprobe_threads", 50))
        loop = asyncio.get_running_loop()
        sem = asyncio.Semaphore(CFG.get("concurrency", 80))

        done = 0; ok = 0; fail = 0
        async def wrap(ch):
            nonlocal done, ok, fail
            r = await check_one(session, ch, sem, loop, executor)
            done += 1
            if r: ok += 1
            else: fail += 1
            step = max(1, len(channels)//20)
            if done % step == 0 or done == len(channels) or done == 1:
                print_progress(done, len(channels), ok, fail)
            return r

        print(f"[*] Проверка ({len(channels)} шт.)...")
        rs = await asyncio.gather(*[wrap(c) for c in channels])
        executor.shutdown()

        alive = [r for r in rs if r]
        write_playlist(alive)

        report = {
            "total": len(channels), "alive": len(alive), "dead": len(channels) - len(alive),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "channels": [{"name": c["name"], "url": c["working_url"], "ua": c["working_ua_key"],
                          "group": c.get("group",""), "height": c.get("height",0)} for c in alive],
        }
        (ROOT/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
        write_readme(report, alive, time.time()-started)

        elapsed = time.time() - started
        print("=========================================")
        print(f"[+] Готово за {elapsed:.1f}s")
        print(f"[+] Всего:   {len(channels)}")
        print(f"[+] Живых:   {len(alive)}")
        print(f"[+] Мёртвых: {len(channels)-len(alive)}")

if __name__ == "__main__":
    asyncio.run(main())
