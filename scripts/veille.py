#!/usr/bin/env python3
"""Veille créative quotidienne : lead magnets, hooks, angles, créas, tendances marketing et visuelles.

Sources :
  1. Soumissions (Google Forms publié en CSV)
  2. Recherche web Tavily, avec des requêtes qui tournent chaque jour :
     - format × sujet sur les plateformes à lead magnets (Notion, Gumroad, Figma…)
     - posts LinkedIn « commente et je t'envoie… » indexés par le moteur
     - web ouvert : rapports de tendances, benchmarks, nouveaux formats (30 derniers jours)
     - exploration des sites des créateurs repérés ou suivis
  3. Flux RSS (médias pub & design, newsletters, Google Alerts), pré-filtrés par mots-clés
  4. Effet boule de neige : liens vers d'autres ressources trouvés dans les pages retenues

Priorité au français : la majorité des requêtes, des flux et des créateurs suivis sont
francophones, les candidats français passent en premier, et un contenu en anglais doit
obtenir une meilleure note pour être retenu.

Chaque candidat est enrichi (texte de la page, API publique Notion), puis trié par
Gemini (gratuit) si GEMINI_API_KEY est défini, sinon par score de mots-clés.

Aucune dépendance externe : bibliothèque standard Python uniquement.
Usage : python scripts/veille.py [--dry-run]
"""
import csv
import hashlib
import html
import io
import json
import math
import os
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlparse, urlunparse

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
DATA_FILE = ROOT / "data" / "ressources.json"
SEEN_FILE = ROOT / "data" / "vus.json"
CREATORS_FILE = ROOT / "data" / "createurs.json"

TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"

DRY_RUN = "--dry-run" in sys.argv
NOW = datetime.now(timezone.utc)
TODAY = NOW.strftime("%Y-%m-%d")
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " \
             "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# Plateformes génériques : on ne les « explore » pas comme des sites de créateurs.
PLATFORMS = ("linkedin.com", "notion.com", "notion.so", "google.com", "gumroad.com",
             "substack.com", "beehiiv.com", "canva.com", "medium.com", "github.com",
             "figma.com", "gamma.app", "framer.com")
CREATOR_SUBDOMAINS = ("notion.site", "gumroad.com", "substack.com", "beehiiv.com",
                      "framer.website", "framer.app")
ARCHIVE_URL = re.compile(r"/(tag|tags|category|categorie|author|auteur|page/\d+|search|login|signup)(/|$)", re.I)
RESOURCE_HINT = re.compile(r"guide|template|ressource|resource|kit|swipe|checklist|playbook|"
                           r"ebook|e-book|livre-blanc|toolkit|prompts|hook|trend|tendance|"
                           r"report|rapport|benchmark|notion\.site|gumroad", re.I)


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- HTTP / JSON

def http(url, data=None, headers=None, timeout=30, max_bytes=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET")
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept-Language", "fr-FR,fr;q=0.9,en;q=0.8")
    if body:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(max_bytes) if max_bytes else resp.read()


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- URLs / texte

TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_src|s$|source$|trk|rcm)")


def clean_url(url):
    """URL affichée sur le site : sans paramètres de tracking, mais avec son hôte d'origine."""
    p = urlparse(url.strip())
    # Liens de redirection Google (Google Alerts) : on garde la vraie destination
    if p.netloc.endswith("google.com") and p.path == "/url":
        real = parse_qs(p.query).get("url") or parse_qs(p.query).get("q")
        if real:
            return clean_url(real[0])
    query = [(k, v) for k, v in parse_qsl(p.query) if not TRACKING.match(k)]
    return urlunparse((p.scheme or "https", p.netloc.lower(), p.path or "/", "", urlencode(query), ""))


def url_key(url):
    """Clé de dédoublonnage : sans www, sans / final, sans variante de pays LinkedIn."""
    p = urlparse(clean_url(url))
    host = re.sub(r"^[a-z]{2}\.linkedin\.com$", "linkedin.com", host_of(url))
    query = f"?{p.query}" if p.query else ""
    return f"{host}{p.path.rstrip('/')}{query}"


def host_of(url):
    host = urlparse(url if "//" in url else f"https://{url}").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def url_id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def clean_text(s, limit=600):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = unicodedata.normalize("NFKC", s)  # 𝗵𝗼𝗼𝗸 (gras LinkedIn) → hook
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def excluded(url):
    # Correspondance exacte : exclure tiktok.com n'exclut pas ads.tiktok.com (rapports TikTok)
    return host_of(url) in set(CONFIG.get("domaines_exclus", []))


def is_creator_host(host, rss_hosts):
    """Site propre à un créateur (ex. agence.notion.site, agence.fr), pas une plateforme ni un média suivi en RSS."""
    if host in rss_hosts:
        return False
    if host.endswith(CREATOR_SUBDOMAINS):
        return host.count(".") >= 2
    return not any(host == p or host.endswith("." + p) for p in PLATFORMS)


def fill(query):
    """Remplace {annee} et {annee_tendances} (l'année suivante à partir de septembre,
    quand sortent les rapports de tendances)."""
    trend_year = NOW.year + 1 if NOW.month >= 9 else NOW.year
    return query.replace("{annee}", str(NOW.year)).replace("{annee_tendances}", str(trend_year))


def rotation(items, per_day, salt=0):
    """Sélectionne `per_day` éléments différents chaque jour ; parcourt toute la liste en boucle."""
    if not items or per_day <= 0:
        return []
    items = list(items)
    random.Random(salt).shuffle(items)  # ordre mélangé mais stable d'un jour à l'autre
    start = (NOW.toordinal() * per_day) % len(items)
    return [items[(start + i) % len(items)] for i in range(min(per_day, len(items)))]


def interleave(*groups):
    """Alterne les sources pour qu'aucune ne monopolise le budget quotidien."""
    out = []
    for i in range(max((len(g) for g in groups), default=0)):
        out += [g[i] for g in groups if i < len(g)]
    return out


def split_fr_en(n):
    """Répartit n requêtes : la part française d'abord (arrondie au-dessus), le reste en anglais."""
    n_fr = min(n, math.ceil(n * CONFIG.get("priorite_francais", 0.75)))
    return n_fr, n - n_fr


FR_HINT = re.compile(r"\b(le|la|les|des|du|une|pour|avec|vos|votre|nos|dans|sur|est|sont|comment|"
                     r"gratuit|guide|tendances|créas?)\b|[éèêàùçœ]", re.I)
EN_HINT = re.compile(r"\b(the|and|for|with|your|how|free|what|best|to|of|is|are|you)\b", re.I)


def guess_lang(text):
    return "fr" if len(FR_HINT.findall(text)) >= len(EN_HINT.findall(text)) else "en"


def is_fr_host(host):
    fr_hosts = {host_of(h) for h in (CONFIG.get("createurs_a_suivre") or {}).get("fr", [])}
    return host in fr_hosts or host.endswith(".fr")


# ---------------------------------------------------------------- Collecte : Tavily

def tavily(query, domains=None, time_range=None, max_results=10, country=None):
    payload = {"query": query, "max_results": max_results, "search_depth": "basic"}
    if domains:
        payload["include_domains"] = domains
    if time_range:
        payload["time_range"] = time_range
    if country:
        payload["country"] = country  # favorise les résultats du pays (ex. france)
    try:
        res = json.loads(http("https://api.tavily.com/search", payload,
                              {"Authorization": f"Bearer {TAVILY_KEY}"}))
    except urllib.error.HTTPError as e:
        if country and e.code in (400, 422):  # paramètre refusé : on relance sans le pays
            return tavily(query, domains, time_range, max_results)
        log(f"  ! Tavily « {query} » : HTTP {e.code}")
        return []
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        log(f"  ! Tavily « {query} » : {e}")
        return []
    finally:
        time.sleep(1)
    return [{"url": r.get("url", ""), "titre": r.get("title", ""),
             "extrait": clean_text(r.get("content"), 800)} for r in res.get("results", [])]


def collect_tavily(creators):
    groups = {f"{g}_{lang}": [] for lang in ("fr", "en")
              for g in ("recherche", "linkedin", "web", "exploration")}
    if not TAVILY_KEY:
        log("· Tavily : pas de clé TAVILY_API_KEY, recherche web ignorée")
        return groups
    country = CONFIG.get("pays_recherche_fr") or None

    def search(group, lang, query, **kw):
        found = tavily(fill(query), country=country if lang == "fr" else None, **kw)
        for c in found:
            c["source"], c["langue_source"] = group, lang
        groups[f"{group}_{lang}"] += found

    # Recherche tournante « format × sujet » sur les plateformes à lead magnets
    rech = CONFIG["recherche"]
    for lang, n, salt in zip(("fr", "en"), split_fr_en(rech["requetes_par_jour"]), (1, 11)):
        cfg = rech.get(lang, {})
        combos = [f"{f} {s}" for s in cfg.get("sujets", []) for f in cfg.get("formats", [])]
        for q in rotation(combos, n, salt):
            search("recherche", lang, q, domains=rech["domaines_cibles"])

    # Posts LinkedIn « commente et je t'envoie… »
    li = CONFIG.get("linkedin", {})
    for lang, n, salt in zip(("fr", "en"), split_fr_en(li.get("requetes_par_jour", 0)), (2, 12)):
        cfg = li.get(lang, {})
        combos = [f"{a} {s}" for s in cfg.get("sujets", []) for a in cfg.get("accroches", [])]
        for q in rotation(combos, n, salt):
            search("linkedin", lang, q, domains=["linkedin.com"], time_range="month")

    # Web ouvert : tendances, benchmarks, nouveaux formats
    web = CONFIG.get("web_ouvert", {})
    for lang, n, salt in zip(("fr", "en"), split_fr_en(web.get("requetes_par_jour", 0)), (3, 13)):
        for q in rotation(web.get(lang, []), n, salt):
            search("web", lang, q, time_range=web.get("periode") or None)

    # Exploration des sites de créateurs (jamais explorés, ou pas depuis 30 jours), français d'abord
    limit = (NOW - timedelta(days=30)).strftime("%Y-%m-%d")
    due = sorted((h for h, d in creators.items() if not d or d < limit),
                 key=lambda h: (creators[h], 0 if is_fr_host(h) else 1))
    for host in due[: CONFIG.get("exploration_createurs_par_jour", 0)]:
        lang = "fr" if is_fr_host(host) else "en"
        query = ("guide gratuit template hooks angles tendances ressources" if lang == "fr"
                 else "free guide template swipe file hooks trends report")
        search("exploration", lang, query, domains=[host], max_results=20)
        creators[host] = TODAY

    log("· Tavily : " + ", ".join(f"{len(v)} {k}" for k, v in groups.items() if v)
        if any(groups.values()) else "· Tavily : aucun résultat")
    return groups


# ---------------------------------------------------------------- Collecte : RSS & soumissions

def _parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def rss_feeds():
    """Flux RSS par langue : {"fr": [...], "en": [...]} (une simple liste compte comme du français)."""
    feeds = CONFIG.get("flux_rss") or {}
    return {"fr": feeds, "en": []} if isinstance(feeds, list) else feeds


def collect_rss():
    limit = NOW - timedelta(days=CONFIG.get("age_max_rss_jours", 3))
    keep = re.compile(CONFIG.get("filtre_rss") or ".", re.I)
    atom = "{http://www.w3.org/2005/Atom}"
    out, skipped = {"fr": [], "en": []}, 0
    for lang, feed in [(lang, f) for lang, feeds in rss_feeds().items() for f in feeds]:
        try:
            root = ET.fromstring(http(feed))
        except (urllib.error.URLError, ET.ParseError, TimeoutError) as e:
            log(f"  ! RSS {feed} : {e}")
            continue
        entries = root.findall(".//item") or root.findall(f".//{atom}entry")
        for e in entries:
            link = e.findtext("link") or ""
            if not link.strip():
                el = e.find(f"{atom}link")
                link = el.get("href", "") if el is not None else ""
            date = _parse_date(e.findtext("pubDate") or e.findtext(f"{atom}updated")
                               or e.findtext(f"{atom}published"))
            if date and date < limit:
                continue
            c = {
                "url": link.strip(),
                "titre": clean_text(e.findtext("title") or e.findtext(f"{atom}title"), 200),
                "extrait": clean_text(e.findtext("description") or e.findtext(f"{atom}summary")
                                      or e.findtext(f"{atom}content")),
                "source": "rss",
                "langue_source": lang,
            }
            if keep.search(f"{c['titre']} {c['extrait'][:200]}"):
                out.setdefault(lang, []).append(c)
            else:
                skipped += 1
    log(f"· RSS : {len(out['fr'])} éléments français et {len(out['en'])} anglais retenus "
        f"({skipped} hors sujet écartés)")
    return out


def collect_submissions():
    csv_url = CONFIG.get("url_csv_soumissions", "").strip()
    if not csv_url:
        return []
    try:
        rows = list(csv.DictReader(io.StringIO(http(csv_url).decode("utf-8"))))
    except (urllib.error.URLError, UnicodeDecodeError, TimeoutError) as e:
        log(f"  ! Soumissions : {e}")
        return []
    out = []
    for row in rows:
        link = next((v for k, v in row.items() if k and re.search(r"url|lien|link", k, re.I)), "")
        if link.strip().startswith("http"):
            out.append({"url": link.strip(), "titre": "", "extrait": "", "source": "soumission"})
    log(f"· Soumissions : {len(out)} liens")
    return out


# ---------------------------------------------------------------- Enrichissement

def _notion_text(segments):
    text, links = "", []
    for seg in segments or []:
        text += seg[0] if seg and isinstance(seg[0], str) else ""
        for ann in (seg[1] if len(seg) > 1 else []):
            if ann and ann[0] == "a" and len(ann) > 1:
                links.append(ann[1])
    return text, links


def enrich_notion(c):
    """Lit une page Notion publique via l'API interne utilisée par notion.site (non officielle)."""
    p = urlparse(c["url"])
    m = re.search(r"([0-9a-f]{32})$", p.path.split("/")[-1].replace("-", ""))
    if not m:
        return
    h = m.group(1)
    page_id = f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"
    payload = {"pageId": page_id, "limit": 60, "cursor": {"stack": []},
               "chunkNumber": 0, "verticalColumns": False}
    host = "www.notion.so" if p.netloc == "notion.so" else p.netloc
    data = json.loads(http(f"https://{host}/api/v3/loadPageChunk", payload, timeout=15))
    blocks = {k: (v["value"].get("value") or v["value"])
              for k, v in data.get("recordMap", {}).get("block", {}).items() if "value" in v}
    page = blocks.get(page_id)
    if not page:
        return
    title, _ = _notion_text(page.get("properties", {}).get("title"))
    parts, links = [], []
    for block in blocks.values():
        links += _notion_text(block.get("properties", {}).get("title"))[1]
    for bid in page.get("content", []):
        t, _ = _notion_text(blocks.get(bid, {}).get("properties", {}).get("title"))
        if t:
            parts.append(t)
    c["titre"] = title or c["titre"]
    c["extrait"] = clean_text(" · ".join(parts), 1500) or c["extrait"]
    c["liens"] = links


META = r'<meta[^>]+(?:property|name)=["\']{}["\'][^>]+content=["\']([^"\']*)["\']'


def enrich_html(c):
    if urlparse(c["url"]).path.lower().endswith(".pdf"):
        return  # PDF : on garde le titre et l'extrait du moteur de recherche
    raw = http(c["url"], timeout=12, max_bytes=800_000).decode("utf-8", "ignore")
    grab = lambda pat: (re.search(pat, raw, re.I | re.S) or [None, ""])[1]
    title = grab(META.format("og:title")) or grab(r"<title[^>]*>(.*?)</title>")
    desc = grab(META.format("og:description")) or grab(META.format("description"))
    body = re.sub(r"<(script|style|noscript|svg|nav|footer)[^>]*>.*?</\1>", " ", raw, flags=re.I | re.S)
    c["titre"] = clean_text(title, 200) or c["titre"]
    c["extrait"] = clean_text(f"{desc} — {clean_text(body, 1500)}", 1500)
    c["liens"] = [urljoin(c["url"], h) for h in re.findall(r'href=["\']([^"\'#]+)', raw)[:400]]


def enrich(c):
    host = host_of(c["url"])
    try:
        if host.endswith("linkedin.com"):
            return  # page derrière connexion : on garde l'extrait du moteur de recherche
        if host.endswith("notion.site") or host.endswith("notion.so"):
            enrich_notion(c)
        else:
            enrich_html(c)
    except Exception as e:  # une page qui ne répond pas ne doit pas bloquer la veille
        c["erreur"] = str(e)[:120]


# ---------------------------------------------------------------- Tri

GEMINI_PROMPT = """Tu fais la veille d'un·e creative strategist. Son périmètre : {secteur}.

Pour chaque candidat, décide s'il mérite d'apparaître dans sa veille.

On RETIENT :
- les ressources gratuites et actionnables : lead magnets (guide, template, swipe file, banque de
  hooks ou de concepts, checklist, framework, prompts, mini-formation, outil gratuit), en accès libre,
  contre un email, ou proposées dans un post LinkedIn « commente X et je t'envoie… » ;
- les contenus de fond directement utilisables : listes de hooks ou d'angles, décryptages de créas,
  méthodes de brief, de recherche client ou de creative testing ;
- les rapports et analyses de tendances : marketing, social media, consommateurs, tendances visuelles
  et design (couleurs, typographies, esthétiques, DA), benchmarks de performance créative ;
- les nouveautés des plateformes publicitaires qui changent la façon de concevoir les créas
  (nouveaux formats, fonctionnalités créatives, outils de création) ;
- les campagnes et pubs remarquables, surtout sur les réseaux sociaux, quand l'idée créative est expliquée.

On ÉCARTE : actus business (levées de fonds, rachats, nominations, résultats financiers), actus
générales ou politiques, tests de matériel, comparatifs d'outils sans lien avec la création
publicitaire, pages d'accueil, pages de services ou de tarifs, offres payantes, templates de
productivité génériques, pages de connexion ou d'erreur, contenus trop pauvres pour être utiles.

LANGUE : la veille est francophone. Les contenus en français sont prioritaires : à qualité égale,
donne 1 point de pertinence de plus à un contenu en français. Un contenu en anglais ne vaut la peine
que s'il apporte quelque chose de vraiment utile ou introuvable en français.

Réponds UNIQUEMENT par un tableau JSON, un objet par candidat :
[{{"index": 0, "retenu": true, "pertinence": 0-10,
   "langue": "fr" | "en" | "autre",
   "titre": "titre clair en français (garde le nom officiel d'un rapport s'il en a un)",
   "resume": "2 phrases max, en français : ce qu'on y trouve et comment s'en servir pour ses créas",
   "categorie": "une valeur parmi {categories}",
   "tags": ["3 à 5 mots-clés en français"],
   "auteur": "agence / marque / média / créateur, ou \\"\\"",
   "acces": "libre" | "email" | "commentaire" | "inconnu"}}]

"langue" = la langue du contenu lui-même (pas celle de ton résumé).
Barème : 9-10 = ressource riche ou tendance majeure à ne pas rater ; 7-8 = utile ; 6 = intéressant ;
5 ou moins = hors sujet, trop générique ou trop pauvre.

Candidats :
{candidats}"""


def classify_gemini(batch):
    lines = [f"[{i}] URL: {c['url']}\n    Source: {c['source']}\n    Titre: {c['titre']}\n"
             f"    Contenu: {c['extrait'][:1200]}" for i, c in enumerate(batch)]
    prompt = GEMINI_PROMPT.format(secteur=CONFIG["secteur"],
                                  categories=json.dumps(CONFIG["categories"], ensure_ascii=False),
                                  candidats="\n".join(lines))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}}
    for attempt in range(3):
        try:
            res = json.loads(http(url, payload, {"x-goog-api-key": GEMINI_KEY}, timeout=120))
            text = res["candidates"][0]["content"]["parts"][0]["text"]
            return {int(r["index"]): r for r in json.loads(text) if "index" in r}
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and attempt < 2:  # quota/minute ou surcharge : on réessaie
                time.sleep(30)
                continue
            log(f"  ! Gemini HTTP {e.code} : {e.read()[:200]!r}")
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError, TypeError) as e:
            log(f"  ! Gemini : {e}")
        break
    return None


RESOURCE_WORDS = r"template|modèle|guide|checklist|swipe|toolkit|kit|playbook|ressource|gratuit|" \
                 r"free|copier-coller|prompts?|bibliothèque|library|e-?book|livre blanc|framework|" \
                 r"exemples|rapport|report|tendances|trends|benchmark|hooks?|angles?|commente|" \
                 r"je t'envoie|je vous envoie"
SECTOR_WORDS = r"pub|ads?\b|créa|creative|marketing|marque|brand|copywriting|contenu|content|" \
               r"linkedin|tiktok|instagram|meta|ugc|social|design|visuel|visual|vidéo|video|" \
               r"campagne|campaign"


KEYWORD_CATEGORIES = [
    (r"hook|accroche", "Hooks & accroches"),
    (r"\bangles?\b|concept", "Angles & concepts"),
    (r"(trend|tendance).*(design|visuel|visual|couleur|colou?r|typo|graphi)|"
     r"(design|visuel|visual|couleur|colou?r|typo|graphi).*(trend|tendance)", "Tendances visuelles"),
    (r"trend|tendance|benchmark|rapport|report", "Tendances marketing & social"),
    (r"\bugc\b|vidéo|video|reels|shorts", "UGC & vidéo"),
    (r"brief|creative strateg|stratégie créative|testing|persona|insight", "Stratégie créative & briefs"),
    (r"copywriting|headline|titre|slogan", "Copywriting"),
    (r"campagne|campaign", "Inspiration & campagnes"),
    (r"nouveau format|new feature|launch|lance|nouveauté", "Nouveautés plateformes"),
    (r"\bia\b|\bai\b|chatgpt|prompt|outil|tool", "IA & outils"),
    (r"static|statique|créa|creative|\bads?\b|swipe|format", "Créas & formats pub"),
]


def guess_category(text):
    for pattern, cat in KEYWORD_CATEGORIES:
        if cat in CONFIG["categories"] and re.search(pattern, text):
            return cat
    return "Autre"


def classify_keywords(c):
    text = f"{c['titre']} {c['extrait'][:300]} {c['url']}".lower()
    res = len(re.findall(RESOURCE_WORDS, text))
    sector = len(re.findall(SECTOR_WORDS, text))
    on_target = any(host_of(c["url"]).endswith(d) for d in CONFIG["recherche"]["domaines_cibles"])
    ok = res >= 1 and sector >= 1 and (on_target or res >= 2)
    acces = "commentaire" if re.search(r"commente", text) else "inconnu"
    lang = guess_lang(f"{c['titre']} {c['extrait'][:600]}")
    return {"retenu": ok, "pertinence": min(10, res + sector + (3 if on_target else 0) + (lang == "fr")),
            "langue": lang, "titre": c["titre"], "resume": c["extrait"][:220],
            "categorie": guess_category(text), "tags": [], "auteur": "", "acces": acces}


def classify(candidates, seen):
    """Trie les candidats ; renvoie les éléments retenus avec les liens trouvés dans leur page."""
    accepted = []
    min_fr = CONFIG.get("pertinence_min", 6)
    min_other = CONFIG.get("pertinence_min_autres_langues", min_fr + 1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(enrich, candidates))
    for start in range(0, len(candidates), 10):
        batch = candidates[start:start + 10]
        verdicts = classify_gemini(batch) if GEMINI_KEY else None
        if verdicts is None and GEMINI_KEY:
            continue  # erreur IA : ces URLs seront retentées demain
        for i, c in enumerate(batch):
            v = verdicts.get(i) if verdicts else classify_keywords(c)
            if not v:
                continue
            seen.add(c["cle"])
            lang = v.get("langue") if v.get("langue") in ("fr", "en") else (
                "autre" if v.get("langue") else c.get("langue_source") or guess_lang(c["titre"]))
            # Priorité au français : l'anglais (ou autre) doit être mieux noté pour être retenu
            ok = v.get("retenu") and int(v.get("pertinence") or 0) >= (min_fr if lang == "fr" else min_other)
            if c["source"] == "soumission" and v.get("retenu"):
                ok = True
            if not ok:
                continue
            cat = v.get("categorie") if v.get("categorie") in CONFIG["categories"] else "Autre"
            acces = v.get("acces") if v.get("acces") in ("libre", "email", "commentaire") else "inconnu"
            accepted.append(({
                "id": url_id(c["cle"]),
                "url": c["url"],
                "titre": clean_text(v.get("titre") or c["titre"], 200) or c["url"],
                "resume": clean_text(v.get("resume") or c["extrait"], 400),
                "categorie": cat,
                "tags": [clean_text(t, 40) for t in (v.get("tags") or [])][:5],
                "auteur": clean_text(v.get("auteur"), 80),
                "domaine": host_of(c["url"]),
                "langue": lang,
                "acces": acces,
                "pertinence": int(v.get("pertinence") or 0),
                "source": c["source"],
                "ajoute_le": TODAY,
            }, c.get("liens", [])))
        if GEMINI_KEY and start + 10 < len(candidates):
            time.sleep(7)  # reste sous la limite de requêtes/minute du palier gratuit
    return accepted


# ---------------------------------------------------------------- Main

def dedupe(raw, known, limit):
    out, urls = [], set()
    for c in raw:
        if not c.get("url", "").startswith("http"):
            continue
        c["url"] = clean_url(c["url"])
        c["cle"] = url_key(c["url"])
        if c["cle"] in known or c["cle"] in urls or excluded(c["url"]):
            continue
        urls.add(c["cle"])
        out.append(c)
    return out[:limit]


def main():
    db = load_json(DATA_FILE, {"items": []})
    seen = set(load_json(SEEN_FILE, []))
    creators = load_json(CREATORS_FILE, {})
    follow = CONFIG.get("createurs_a_suivre") or {}
    for host in (follow if isinstance(follow, list) else follow.get("fr", []) + follow.get("en", [])):
        creators.setdefault(host_of(host), "")
    rss_hosts = {host_of(f) for feeds in rss_feeds().values() for f in feeds}
    known = {url_key(i["url"]) for i in db["items"]} | seen
    budget = CONFIG.get("max_candidats_par_jour", 150)

    tav = collect_tavily(creators)
    rss = collect_rss()
    # Les candidats français passent en premier dans le budget quotidien ; l'anglais complète sans
    # dépasser sa part : avec priorite_francais = 0.75, au plus 1 candidat anglais pour 3 français
    fr = interleave(tav["linkedin_fr"], rss["fr"], tav["recherche_fr"], tav["web_fr"], tav["exploration_fr"])
    en = interleave(tav["linkedin_en"], rss["en"], tav["recherche_en"], tav["web_en"], tav["exploration_en"])
    candidates = dedupe(collect_submissions() + fr, known, budget)
    p = min(max(CONFIG.get("priorite_francais", 0.75), 0.01), 0.99)
    en_budget = min(budget - len(candidates), max(3, math.ceil(len(candidates) * (1 - p) / p)))
    candidates += dedupe(en, known | {c["cle"] for c in candidates}, en_budget)
    log(f"· {len(candidates)} nouveaux candidats à trier "
        f"({'Gemini ' + GEMINI_MODEL if GEMINI_KEY else 'mots-clés'})")
    results = classify(candidates, seen)

    # Boule de neige : les pages retenues renvoient souvent vers d'autres ressources du même auteur
    known |= {c["cle"] for c in candidates}
    links = []
    for _, liens in results:
        found = [l for l in dict.fromkeys(liens)
                 if l.startswith("http") and RESOURCE_HINT.search(l) and not ARCHIVE_URL.search(l)]
        links += [{"url": l, "titre": "", "extrait": "", "source": "boule de neige"} for l in found[:5]]
    extra = dedupe(links, known, max(0, budget - len(candidates)))
    if extra:
        log(f"· Boule de neige : {len(extra)} liens trouvés dans les éléments retenus")
        results += classify(extra, seen)

    added = sorted((item for item, _ in results),
                   key=lambda i: (i["langue"] != "fr", -i["pertinence"]))
    for item in added:
        if is_creator_host(item["domaine"], rss_hosts):
            creators.setdefault(item["domaine"], "")
        log(f"  + [{item['langue'].upper()}] [{item['categorie']}] ({item['pertinence']}/10) "
            f"{item['titre']} — {item['url']}")
    n_fr = sum(i["langue"] == "fr" for i in added)
    log(f"✓ {len(added)} élément(s) ajouté(s) aujourd'hui, dont {n_fr} en français")

    if DRY_RUN:
        log("(dry-run : rien n'est enregistré)")
        return
    db["items"] = added + db["items"]
    db["mis_a_jour_le"] = NOW.isoformat(timespec="seconds")
    db["site"] = CONFIG["site"]
    db["categories"] = CONFIG["categories"]
    save_json(DATA_FILE, db)
    save_json(SEEN_FILE, sorted(seen))
    save_json(CREATORS_FILE, dict(sorted(creators.items())))


if __name__ == "__main__":
    main()
