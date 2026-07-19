#!/usr/bin/env python3
"""Static-site generator for Arkey Lock (arkeylock.com).
Zero build deps: pure Python -> static HTML in dist/. Deploy dist/ to Cloudflare Pages.
Content lives in content/*.json; chrome + schema live here."""
import json, os, glob, html, re, shutil, urllib.parse
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
CONTENT = os.path.join(ROOT, "content")
POSTS = os.path.join(ROOT, "posts")

# Set in main() once posts are loaded: True when >=1 post is published, which
# turns on the Blog nav/footer links and the /blog hub. With zero published
# posts the site output is byte-identical to the pre-blog build.
BLOG_LIVE = False

SITE = {
    "brand": "Arkey Locksmith",  # real business name (matches GBP) — used in UI, schema, body copy
    "legalName": "Arkey Locksmith",
    "shortName": "Arkey Lock",  # short/domain form (arkeylock.com) — used only in <title> tags & schema alternateName
    "domain": "https://www.arkeylock.com",
    "phone_e164": "+15016178872",
    "phone_tel": "5016178872",
    "phone_display": "(501) 617-8872",
    "ga4Id": "G-FP3CSP0L45",    # GA4 measurement id (property "ArkeyLock.com")
    "clarityId": "xohgxd8zk6",  # Microsoft Clarity project
    # Service-area business (SAB) — no public street address. City/region only for locale signals.
    "city": "Hot Springs National Park",
    "region": "AR",
    "logo": "/assets/logo.webp",
    "tagline": "Hot Springs Locksmith — Emergency, Automotive, Residential & Commercial",
    # Towns served (dedicated pages). Order = nav order.
    "areas": ["Hot Springs", "Hot Springs Village", "Lake Hamilton", "Pearcy",
              "Magnet Cove", "Malvern", "Bismarck", "Mount Ida", "Lonsdale",
              "Benton", "Arkadelphia"],
    # smaller communities mentioned only (no page)
    "also_serve": ["Mountain Pine", "Royal", "Piney", "Jessieville",
                   "Donaldson", "Bonnerdale", "Lake Catherine", "DeGray Lake"],
    "noindex": False,  # LAUNCH: indexable. (Was staging-only while on *.pages.dev.)
    "sameAs": ["https://www.google.com/maps?cid=10533239825589396135",
               "https://www.facebook.com/profile.php?id=100090166171791"],
    "images": ["/assets/img/hero-carkey.jpg", "/assets/img/hero-emergency.jpg", "/assets/img/hero-keys.jpg",
               "/assets/img/hero-residential.jpg", "/assets/img/hero-commercial.webp", "/assets/img/hero-smartlock.webp",
               "/assets/img/hero-lake.jpg", "/assets/img/hero-rv.jpg"],
}

# Service nav (label, slug)
SERVICES = [
    ("Emergency Lockout", "emergency-locksmith"),
    ("Automotive", "automotive-locksmith"),
    ("Car Key Replacement", "car-key-replacement"),
    ("Residential", "residential-locksmith"),
    ("Commercial", "commercial-locksmith"),
    ("Smart Locks", "smart-lock-installation"),
    ("RV & Marine", "rv-marine-locksmith"),
]
LOCATIONS = [
    ("Hot Springs Village", "hot-springs-village-locksmith"),
    ("Lake Hamilton", "lake-hamilton-locksmith"),
    ("Pearcy", "pearcy-locksmith"),
    ("Magnet Cove", "magnet-cove-locksmith"),
    ("Malvern", "malvern-locksmith"),
    ("Bismarck", "bismarck-locksmith"),
    ("Mount Ida", "mount-ida-locksmith"),
    ("Lonsdale", "lonsdale-locksmith"),
    ("Benton", "benton-locksmith"),
    ("Arkadelphia", "arkadelphia-locksmith"),
]
SLUG_LABEL = {s: l for l, s in SERVICES + LOCATIONS}
SLUG_LABEL[""] = "Home"
SLUG_LABEL["service-area"] = "Service Area"

# Legacy arkeylock.com URLs that have no matching page here -> closest current page (301).
# Keeps the old indexed URLs from 404-ing after migration. Pages that still exist (e.g.
# /about, /contact, /customer-reviews, /malvern-locksmith, /mount-ida-locksmith) are served
# directly and must NOT appear here, or the redirect would shadow the real page.
REDIRECTS = [
    ("/locksmith-services", "/"),
    ("/service", "/service-area"),
    ("/articles", "/"),
    ("/gurdon-locksmith", "/"),  # ~40 mi out, outside our 35-mi radius — no dedicated page
    # legacy blog posts (unindexed, no blog on the new site) -> homepage
    ("/fast-response-emergency-locksmith-in-hot-springs-village-available-24-7", "/"),
    ("/locked-out-here-s-what-not-to-do", "/"),
    ("/reliable-hot-springs-locksmith-services-for-every-need", "/"),
    ("/protecting-your-property-is-our-priority", "/"),
    ("/not-all-locks-are-created-equal", "/"),
    ("/not%20all-locks-are-created-equal", "/"),  # same post; a space-for-hyphen variant got indexed
]

CSS = """
:root{--navy:#1e3a8a;--navy-d:#162e6e;--orange:#ff6b35;--orange-d:#e85520;--ink:#0f172a;--muted:#475569;--line:#e2e8f0;--bg:#f8fafc;}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:var(--ink);line-height:1.6;background:#fff}
a{color:var(--navy);text-decoration:none}
img{max-width:100%;display:block}
.wrap{max-width:1140px;margin:0 auto;padding:0 5%}
.btn{display:inline-flex;align-items:center;gap:8px;font-weight:800;border-radius:10px;padding:.85rem 1.4rem;text-decoration:none;transition:.2s}
.btn-call{background:var(--orange);color:#0f172a;box-shadow:0 4px 14px rgba(255,107,53,.35)}
.btn-call:hover{background:var(--orange-d)}
.btn-ghost{background:transparent;color:#fff;border:2px solid rgba(255,255,255,.5)}
.btn-ghost:hover{border-color:#fff}
.btn-navy{background:var(--navy);color:#fff}.btn-navy:hover{background:var(--navy-d)}
/* header */
header.site{position:sticky;top:0;z-index:50;background:#fff;border-bottom:1px solid var(--line)}
.nav{display:flex;align-items:center;gap:1rem;justify-content:space-between;padding:.6rem 5%}
.nav .brand{display:flex;align-items:center;gap:.6rem;font-weight:900;color:var(--navy);font-size:1.15rem}
.nav .brand img{height:38px;width:auto}
.nav .links{display:flex;gap:1.1rem;align-items:center;flex-wrap:wrap}
.nav .links a{color:var(--ink);font-weight:600;font-size:.95rem}
.nav .links a:hover{color:var(--orange)}
.nav .callbtn{white-space:nowrap}
.navtoggle{display:none;flex-direction:column;justify-content:center;gap:5px;width:44px;height:40px;background:transparent;border:0;cursor:pointer;padding:8px;margin-left:auto}
.navtoggle span{display:block;height:3px;width:100%;background:var(--navy);border-radius:2px;transition:.2s}
.floatcall{display:none}
/* hero */
.hero{background:linear-gradient(135deg,var(--navy),var(--navy-d));color:#fff;padding:4.5rem 0}
.hero h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.1;font-weight:900;letter-spacing:-.02em}
.hero p.sub{font-size:clamp(1.05rem,2vw,1.3rem);margin:1rem 0 1.6rem;color:#dbe4f5;max-width:640px}
.hero .cta{display:flex;gap:.8rem;flex-wrap:wrap}
.hero .trust{display:flex;gap:1.2rem;flex-wrap:wrap;margin-top:1.6rem;color:#cdd8ef;font-size:.92rem;font-weight:600}
.hero .trust span{display:inline-flex;align-items:center;gap:6px}
/* sections */
section.block{padding:3.5rem 0}
section.block.alt{background:var(--bg)}
h2{font-size:clamp(1.5rem,3.5vw,2.1rem);font-weight:800;color:var(--ink);margin-bottom:.6rem;letter-spacing:-.01em}
section.block h2{margin-bottom:1.2rem}
h3{font-size:1.15rem;font-weight:800;margin:.2rem 0 .4rem}
p{margin:.6rem 0;color:var(--muted)}
.lead{font-size:1.08rem;color:var(--ink)}
.grid{display:grid;gap:1.2rem}
.grid.c3{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.grid.c2{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:1.5rem}
.card.lift{transition:.2s}.card.lift:hover{box-shadow:0 8px 26px rgba(0,0,0,.08);border-color:var(--orange);transform:translateY(-2px)}
.card a.more{color:var(--orange);font-weight:700;font-size:.9rem}
.pill{display:inline-block;background:rgba(30,58,138,.08);color:var(--navy);font-weight:700;font-size:.72rem;letter-spacing:.5px;text-transform:uppercase;padding:.3rem .7rem;border-radius:50px;margin-bottom:.6rem}
ul.ticks{list-style:none;margin:.6rem 0}
ul.ticks li{padding-left:1.6rem;position:relative;margin:.4rem 0;color:var(--muted)}
ul.ticks li:before{content:"\\2714";position:absolute;left:0;color:var(--orange);font-weight:900}
/* FAQ */
.faq details{border:1px solid var(--line);border-radius:10px;margin:.6rem 0;background:#fff}
.faq summary{cursor:pointer;font-weight:700;padding:1rem 1.2rem;list-style:none}
.faq summary::-webkit-details-marker{display:none}
.faq summary:after{content:"+";float:right;color:var(--orange);font-weight:900}
.faq details[open] summary:after{content:"\\2013"}
.faq .ans{padding:0 1.2rem 1.1rem;color:var(--muted)}
/* final cta */
.finalcta{background:var(--navy);color:#fff;text-align:center;padding:3.5rem 0}
.finalcta h2{color:#fff}
.finalcta p{color:#dbe4f5}
/* promise / value bar */
.promise{background:#0f2350;color:#dbe4f5;padding:1rem 0;font-weight:600;font-size:.95rem}
.promise ul{list-style:none;display:flex;flex-wrap:wrap;gap:.5rem 1.7rem;justify-content:center;align-items:center}
.promise li{display:inline-flex;align-items:center;gap:.5rem}
.promise li:before{content:"\\2714";color:var(--orange);font-weight:900}
/* testimonials */
.tcards{display:grid;gap:1.2rem;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
.tcard{background:#fff;border:1px solid var(--line);border-radius:14px;padding:1.4rem;display:flex;flex-direction:column}
.tcard .stars{color:#f5a623;letter-spacing:2px;font-size:1.05rem}
.tcard p{color:var(--ink);font-style:italic;margin:.5rem 0 .9rem}
.tcard .who{font-weight:800;color:var(--navy);margin-top:auto}
/* footer */
footer.site{background:#0b1220;color:#cbd5e1;padding:3rem 0 1.4rem;font-size:.92rem}
footer.site h3{color:#fff;font-size:.95rem;margin-bottom:.7rem;text-transform:uppercase;letter-spacing:.5px}
footer.site p{color:#cbd5e1}
footer.site a{color:#cbd5e1}footer.site a:hover{color:var(--orange)}
.fgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.6rem}
.fgrid ul{list-style:none}.fgrid li{margin:.3rem 0}
.fbtm{border-top:1px solid #1e293b;margin-top:1.8rem;padding-top:1rem;color:#94a3b8;font-size:.85rem;display:flex;justify-content:space-between;flex-wrap:wrap;gap:.5rem}
.fbtm a{text-decoration:underline}
.bc{font-size:.85rem;color:var(--muted);padding:.8rem 0}
.bc a{color:var(--navy)}
.mapwrap{border-radius:14px;overflow:hidden;box-shadow:0 8px 25px rgba(0,0,0,.08);border:1px solid var(--line)}
.mapwrap iframe{width:100%;height:380px;border:0;display:block}
.areamap{height:440px;width:100%;border-radius:14px;overflow:hidden;box-shadow:0 8px 25px rgba(0,0,0,.08);border:1px solid var(--line);position:relative;z-index:0}
@media(max-width:600px){.areamap{height:340px}}
.formwrap{max-width:640px;margin:0 auto;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}
/* blog */
.post-head{max-width:760px;margin:0 auto}
.post-head h1{font-size:clamp(1.7rem,4.5vw,2.5rem);font-weight:900;line-height:1.15;letter-spacing:-.01em}
.post-byline{color:var(--muted);font-size:.92rem;margin:.5rem 0 1.5rem}
.post-hero{width:100%;max-width:860px;margin:0 auto 2rem;border-radius:14px;box-shadow:0 8px 25px rgba(0,0,0,.08);aspect-ratio:16/9;object-fit:cover}
.post-body{max-width:760px;margin:0 auto;font-size:1.04rem}
.post-body h2{margin:2.1rem 0 .6rem}
.post-body h3{margin:1.5rem 0 .4rem}
.post-body a{text-decoration:underline;text-underline-offset:2px}
.post-body ul,.post-body ol{margin:.6rem 0 1rem 1.5rem;color:var(--muted)}
.post-body li{margin:.35rem 0}
.post-body blockquote{border-left:4px solid var(--orange);padding:.2rem 0 .2rem 1rem;margin:1.1rem 0;color:var(--ink)}
.bloggrid{display:grid;gap:1.2rem;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}
.bcard{padding:0;overflow:hidden;display:flex;flex-direction:column}
.bcard img{width:100%;aspect-ratio:16/9;object-fit:cover}
.bcard .bbody{padding:1.3rem 1.4rem 1.5rem;display:flex;flex-direction:column;flex:1}
.bcard h3{margin:0 0 .3rem}
.bcard .bdate{color:var(--muted);font-size:.85rem;margin:0 0 .5rem}
.bcard p.bdesc{flex:1}
.ghl-facade{text-align:center;color:var(--muted);padding:1.5rem}
@media(max-width:820px){
.nav{position:relative}
.navtoggle{display:flex}
.nav .callbtn{display:none}
.nav .links{display:none;position:absolute;top:100%;left:0;right:0;flex-direction:column;align-items:stretch;background:#fff;border-bottom:1px solid var(--line);box-shadow:0 10px 24px rgba(0,0,0,.10);padding:.4rem 5% 1rem;gap:0}
.nav .links.show{display:flex}
.nav .links a{padding:.85rem .2rem;border-bottom:1px solid var(--line);font-size:1.05rem}
.nav .links a:last-child{border-bottom:0}
.floatcall{display:flex;justify-content:center;position:fixed;left:50%;transform:translateX(-50%);bottom:14px;z-index:60;width:calc(100% - 28px);max-width:460px;font-size:1.05rem;padding:.95rem 1.4rem;box-shadow:0 8px 22px rgba(255,107,53,.5)}
body{padding-bottom:78px}
}
"""

def esc(s): return html.escape(html.unescape(s), quote=True)  # unescape first to avoid double-encoding entities in content

_TEL_ANCHOR_RE = re.compile(r'<a\b[^>]*href="tel:[^"]*"[^>]*>.*?</a>', re.S | re.I)

def linkify_phone(s):
    """Wrap the visible phone number in a clickable tel: link, skipping any number already linked.
    Apply only to visible body HTML — never to <title>, meta tags, or JSON-LD."""
    if not s or SITE["phone_display"] not in s:
        return s
    stash = []
    def _hold(m):
        stash.append(m.group(0)); return f"\x00{len(stash)-1}\x00"
    s = _TEL_ANCHOR_RE.sub(_hold, s)  # protect already-linked numbers
    s = s.replace(SITE["phone_display"], f'<a href="tel:{SITE["phone_tel"]}">{SITE["phone_display"]}</a>')
    for i, original in enumerate(stash):
        s = s.replace(f"\x00{i}\x00", original)
    return s

# Sitewide analytics — GA4 + tel_click conversion + Microsoft Clarity. Lazy-
# loaded on first interaction / browser idle so they never compete with LCP, and
# hostname-guarded so nothing fires on the *.pages.dev preview or localhost.
# Built as a plain string (not an f-string) so the JS braces stay literal; the
# two ids are substituted via .replace().
ANALYTICS = ("""<script>(function(){
if(!location.hostname.endsWith('arkeylock.com'))return;
window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}window.gtag=gtag;
var loaded=false;function boot(){if(loaded)return;loaded=true;
var s=document.createElement('script');s.async=true;s.src='https://www.googletagmanager.com/gtag/js?id=__GA__';document.head.appendChild(s);
gtag('js',new Date());gtag('config','__GA__');
(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};t=l.createElement(r);t.async=1;t.src='https://www.clarity.ms/tag/'+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y)})(window,document,'clarity','script','__CLARITY__');}
['scroll','pointerdown','keydown','touchstart'].forEach(function(e){window.addEventListener(e,boot,{once:true,passive:true})});
if('requestIdleCallback' in window)requestIdleCallback(boot,{timeout:5000});else window.addEventListener('load',function(){setTimeout(boot,3000)});
document.addEventListener('click',function(e){var a=e.target&&e.target.closest&&e.target.closest('a[href^="tel:"]');if(!a)return;boot();window.gtag&&window.gtag('event','tel_click',{link_text:(a.textContent||'').trim().slice(0,60),page_path:location.pathname})});
})();</script>""".replace("__GA__", SITE["ga4Id"]).replace("__CLARITY__", SITE["clarityId"]))


def head(page):
    slug = page["slug"]; url = SITE["domain"] + ("/" if not slug else f"/{slug}")
    title = page["title"]; desc = page["metaDesc"]
    ogimg = page.get("heroImage") or SITE["logo"]
    robots_meta = '\n<meta name="robots" content="noindex, nofollow">' if SITE.get("noindex") else ''
    kw = page.get("keywords")
    keywords_meta = f'\n<meta name="keywords" content="{esc(kw)}">' if kw else ''
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{robots_meta}
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">{keywords_meta}
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#1e3a8a">
<link rel="icon" type="image/png" href="/assets/img/favicon-key.png">
<link rel="apple-touch-icon" href="/assets/img/favicon-key.png">
<meta property="og:type" content="{page.get('ogType', 'website')}"><meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE['domain']}{ogimg}">
<link rel="stylesheet" href="/assets/styles.css">
<script type="application/ld+json">{json.dumps(build_schema(page), ensure_ascii=False)}</script>
{ANALYTICS}
</head><body>"""

def header_html():
    links = "".join(f'<a href="/{s}">{esc(l)}</a>' for l, s in SERVICES[:5])
    return f"""<header class="site"><nav class="nav">
<a class="brand" href="/"><img src="{SITE['logo']}" alt="{esc(SITE['brand'])} logo"> {esc(SITE['brand'])}</a>
<div class="links" id="navlinks">{links}<a href="/service-area">Service Area</a><a href="/about">About</a>{'<a href="/blog">Blog</a>' if BLOG_LIVE else ''}<a href="/contact">Contact</a></div>
<a class="btn btn-call callbtn" href="tel:{SITE['phone_tel']}">Call {SITE['phone_display']}</a>
<button class="navtoggle" type="button" aria-label="Toggle menu" aria-expanded="false" aria-controls="navlinks"><span></span><span></span><span></span></button>
</nav></header>
<a class="btn btn-call floatcall" href="tel:{SITE['phone_tel']}">&#9742;&nbsp; Call {SITE['phone_display']}</a>
<script>(function(){{var b=document.querySelector('.navtoggle'),m=document.getElementById('navlinks');if(!b||!m)return;b.addEventListener('click',function(){{var o=m.classList.toggle('show');b.setAttribute('aria-expanded',o?'true':'false');}});m.addEventListener('click',function(e){{if(e.target.tagName==='A'){{m.classList.remove('show');b.setAttribute('aria-expanded','false');}}}});}})();</script>
<main id="main">"""

def breadcrumb_html(page):
    if not page["slug"]: return ""
    if page.get("type") == "post":
        return (f'<div class="wrap bc"><a href="/">Home</a> &rsaquo; <a href="/blog">Blog</a> &rsaquo; '
                f'{esc(page["h1"])}</div>')
    if page.get("type") == "bloghub":
        return '<div class="wrap bc"><a href="/">Home</a> &rsaquo; Blog</div>'
    return f'<div class="wrap bc"><a href="/">Home</a> &rsaquo; {esc(SLUG_LABEL.get(page["slug"], page.get("h1","")))}</div>'

def section_html(sec):
    return f'<section class="block{" alt" if sec.get("alt") else ""}"><div class="wrap">{linkify_phone(sec["html"])}</div></section>'

def faq_html(faqs):
    if not faqs: return ""
    items = "".join(f'<details><summary>{esc(f["q"])}</summary><div class="ans">{linkify_phone(f["a"])}</div></details>' for f in faqs)
    return f'<section class="block alt"><div class="wrap faq"><h2>Frequently Asked Questions</h2>{items}</div></section>'

def related_html(page):
    rel = page.get("related") or []
    if not rel: return ""
    cards = ""
    for s in rel:
        cards += f'<a class="card lift" href="/{s}"><h3>{esc(SLUG_LABEL.get(s,s))}</h3><span class="more">Learn more &rarr;</span></a>'
    return f'<section class="block"><div class="wrap"><h2>Related Services &amp; Areas</h2><div class="grid c3">{cards}</div></div></section>'

# Coverage drawn as a 35-mile radius circle centered on Hot Springs (reaches Mount Ida at the far border).
SERVICE_AREA_CENTER = [34.5037, -93.0552]
SERVICE_AREA_RADIUS_M = round(35 * 1609.344)  # 35 miles in meters
# [label, lat, lng, isBase]
SERVICE_AREA_TOWNS = [
    ["Hot Springs (base)", 34.5037, -93.0552, True],
    ["Hot Springs Village", 34.6717, -92.9938, False],
    ["Lake Hamilton", 34.4204, -93.0916, False],
    ["Pearcy", 34.4537, -93.1949, False],
    ["Magnet Cove", 34.4390, -92.8516, False],
    ["Malvern", 34.3623, -92.8127, False],
    ["Bismarck / DeGray Lake", 34.3137, -93.1671, False],
    ["Mount Ida / Lake Ouachita", 34.5537, -93.6324, False],
    ["Lonsdale", 34.5704, -92.8155, False],
    ["Benton", 34.5645, -92.5868, False],
    ["Arkadelphia", 34.1209, -93.0538, False],
]

def service_area_map_html(page):
    if not page.get("serviceAreaMap"):
        return ""
    center = json.dumps(SERVICE_AREA_CENTER)
    towns = json.dumps(SERVICE_AREA_TOWNS)
    return ('<section class="block"><div class="wrap">'
            '<h2>Our Hot Springs Service Area</h2>'
            '<p>The shaded circle is our roughly 35-mile mobile coverage around Hot Springs. Just outside it? '
            'Call us anyway &mdash; we regularly travel farther for car keys and emergencies.</p>'
            '<div id="servicemap" class="areamap" role="img" '
            'aria-label="Map showing the Arkey Locksmith service area around Hot Springs, Arkansas"></div>'
            '</div>'
            '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">'
            '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
            '<script>(function(){function init(){if(!window.L)return;'
            'var center=' + center + ';var radius=' + str(SERVICE_AREA_RADIUS_M) + ';var towns=' + towns + ';'
            "var map=L.map('servicemap',{scrollWheelZoom:false}).setView(center,9);"
            "L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',"
            "{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);"
            "var poly=L.circle(center,{radius:radius,color:'#ff6b35',weight:2,fillColor:'#ff6b35',fillOpacity:0.12}).addTo(map);"
            "towns.forEach(function(t){var b=t[3];"
            "L.circleMarker([t[1],t[2]],{radius:b?8:6,color:b?'#e85520':'#1e3a8a',weight:2,"
            "fillColor:b?'#ff6b35':'#ffffff',fillOpacity:1}).addTo(map)"
            ".bindTooltip(t[0],{direction:'top'});});"
            "map.fitBounds(poly.getBounds(),{padding:[24,24]});"
            "map.on('focus',function(){map.scrollWheelZoom.enable();});"
            "map.on('blur',function(){map.scrollWheelZoom.disable();});}"
            "if(document.readyState!=='loading'){init();}else{document.addEventListener('DOMContentLoaded',init);}})();"
            '</script></section>')

def area_hub_html(page):
    """Card grid linking every town page + the also-served list. Gated by page flag 'areaHub'."""
    if not page.get("areaHub"):
        return ""
    cards = f'<a class="card lift" href="/"><h3>Hot Springs</h3><p>Our home base &mdash; full mobile locksmith service across Hot Springs.</p><span class="more">View Hot Springs &rarr;</span></a>'
    for label, slug in LOCATIONS:
        cards += (f'<a class="card lift" href="/{slug}"><h3>{esc(label)}</h3>'
                  f'<p>Mobile locksmith service in {esc(label)} &amp; the surrounding area.</p>'
                  f'<span class="more">View {esc(label)} &rarr;</span></a>')
    also = ", ".join(SITE["also_serve"])
    return (f'<section class="block"><div class="wrap"><h2>Towns We Serve</h2>'
            f'<div class="grid c3">{cards}</div>'
            f'<p style="margin-top:1.4rem">We also serve {esc(also)} &mdash; and the greater Hot Springs area, 24/7. '
            f'Not sure if you&rsquo;re in range? <a href="/contact">Get in touch</a> or call '
            f'<a href="tel:{SITE["phone_tel"]}">{SITE["phone_display"]}</a> &mdash; we travel.</p></div></section>')

def map_html(page):
    q = page.get("mapQuery")
    if not q: return ""
    enc = urllib.parse.quote(q)
    return (f'<section class="block"><div class="wrap"><h2>Serving {esc(q)}</h2>'
            f'<p>Mobile locksmith service across {esc(q)} and the surrounding area.</p>'
            f'<div class="mapwrap"><iframe loading="lazy" referrerpolicy="no-referrer-when-downgrade" '
            f'title="Map of {esc(q)}" src="https://maps.google.com/maps?q={enc}&amp;z=12&amp;output=embed"></iframe></div></div></section>')

GHL_SCRIPT = "https://link.msgsndr.com/js/form_embed.js"

def ghl_form_html(page):
    g = page.get("ghlForm")
    if not g:
        return ""
    src = g["src"]; fid = g["id"]; h = str(g.get("height", 500)); mode = g.get("mode", "lazy")
    title = esc(g.get("name", "Contact Form")); heading = esc(g.get("heading", "Send Us a Message"))
    if mode == "eager":
        iframe = ('<iframe src="' + src + '" id="inline-' + fid + '" title="' + title +
                  '" style="width:100%;height:' + h + 'px;border:none" data-form-id="' + fid + '"></iframe>')
        return ('<section class="block alt"><div class="wrap"><h2>' + heading + '</h2>'
                '<div class="formwrap">' + iframe + '</div></div>'
                '<script src="' + GHL_SCRIPT + '"></script></section>')
    tmpl = ('<section class="block alt"><div class="wrap"><h2>__HEADING__</h2>'
            '<div id="ghlholder" class="formwrap" data-src="__SRC__" data-fid="__FID__" data-h="__H__" style="min-height:__H__px">'
            '<div class="ghl-facade"><p>Loading the quick request form&hellip;</p>'
            '<a class="btn btn-call" href="tel:__TEL__">Or tap to call __PHONE__</a></div></div></div>'
            "<script>(function(){var el=document.getElementById('ghlholder');if(!el)return;var done=false;"
            "function load(){if(done)return;done=true;var f=document.createElement('iframe');"
            "f.src=el.getAttribute('data-src');f.id='inline-'+el.getAttribute('data-fid');f.title='__TITLE__';"
            "f.style.cssText='width:100%;height:'+el.getAttribute('data-h')+'px;border:none';"
            "f.setAttribute('data-form-id',el.getAttribute('data-fid'));el.innerHTML='';el.appendChild(f);"
            "var s=document.createElement('script');s.src='__SCRIPT__';document.body.appendChild(s);}"
            "if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach("
            "function(e){if(e.isIntersecting){load();io.disconnect();}});},{rootMargin:'400px'});io.observe(el);}"
            "else{load();}})();</script></section>")
    return (tmpl.replace("__HEADING__", heading).replace("__SRC__", src).replace("__FID__", fid)
            .replace("__H__", h).replace("__TITLE__", title).replace("__TEL__", SITE["phone_tel"])
            .replace("__PHONE__", SITE["phone_display"]).replace("__SCRIPT__", GHL_SCRIPT))

def finalcta_html(page):
    return f"""<section class="finalcta"><div class="wrap">
<h2>{esc(page.get('ctaHeading','Locked Out? Need a Key? Call Arkey Locksmith.'))}</h2>
<p>{linkify_phone(esc(page.get('ctaSub','Fast, friendly, licensed local locksmiths — serving Hot Springs and the surrounding area.')))}</p>
<div style="margin-top:1.2rem;display:flex;gap:.8rem;justify-content:center;flex-wrap:wrap">
<a class="btn btn-call" href="tel:{SITE['phone_tel']}">Call {SITE['phone_display']}</a>
<a class="btn btn-ghost" href="/contact">Request Service</a></div></div></section>"""

# Real customer reviews (verbatim, from the prior arkeylock.com homepage). Owner name: William.
TESTIMONIALS = [
    {"name": "Devon York", "text": "Best service in Hot Springs — they were the only ones who would help me on a weekend."},
    {"name": "Bob Grant", "text": "This gentleman is a professional and a real gentleman. As soon as he knew my wife was stuck with the kids, he jumped in his car and beelined to them. I am truly thankful and I highly recommend him."},
    {"name": "Brandi Proetz", "text": "These guys were great. They showed up within about 45 minutes and had the door open in no time! The price was reasonable considering it was a holiday weekend. I would highly recommend these guys!"},
    {"name": "Janice R.", "text": "William was on time, very personable and professional and the work was done in no time. We felt the price we paid was well worth it. I would recommend Arkey Locksmith to anyone who wants a trustworthy company."},
    {"name": "Sandra Saunders", "text": "William was very professional, efficient and fast! They were also extremely reasonably priced! Hopefully we won't need a locksmith again — but if we do, we will be calling Arkey Locksmith for sure!"},
    {"name": "John Criss", "text": "I own Real Property Management Hometown and use Arkey every time we need keys done for our properties. Friendly, fast, and reliable — I've never had any issues. I would recommend them to anyone."},
]

PROMISE_ITEMS = ["Free estimates", "No after-hours surcharge",
                 "Parts &amp; workmanship guaranteed", "A+ BBB rated", "Licensed &amp; insured"]

def testimonials_html(page):
    if not page.get("showTestimonials"):
        return ""
    cards = ""
    for t in TESTIMONIALS:
        cards += (f'<div class="tcard"><div class="stars" aria-label="5 out of 5 stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>'
                  f'<p>&ldquo;{esc(t["text"])}&rdquo;</p><div class="who">&mdash; {esc(t["name"])}</div></div>')
    return (f'<section class="block alt"><div class="wrap"><h2>What Hot Springs Says About Us</h2>'
            f'<div class="tcards">{cards}</div>'
            f'<p style="text-align:center;margin-top:1.5rem"><a class="btn btn-navy" '
            f'href="{SITE["sameAs"][0]}" target="_blank" rel="noopener">Read more reviews on Google</a></p>'
            f'</div></section>')

def promise_bar_html():
    items = "".join(f"<li>{i}</li>" for i in PROMISE_ITEMS)
    return f'<section class="promise"><div class="wrap"><ul>{items}</ul></div></section>'

def footer_html():
    svc = "".join(f'<li><a href="/{s}">{esc(l)}</a></li>' for l, s in SERVICES)
    loc = "".join(f'<li><a href="/{s}">{esc(l)}</a></li>' for l, s in LOCATIONS)
    also = ", ".join(SITE["also_serve"])
    return f"""</main><footer class="site"><div class="wrap">
<div class="fgrid">
<div><h3>{esc(SITE['brand'])}</h3><p style="color:#cbd5e1">24/7 mobile locksmith serving Hot Springs &amp; the surrounding Arkansas area. Licensed &amp; insured.</p>
<p><a href="tel:{SITE['phone_tel']}"><strong>{SITE['phone_display']}</strong></a><br>Mobile locksmith &mdash; Hot Springs, {SITE['region']} &amp; the surrounding area</p></div>
<div><h3>Services</h3><ul>{svc}{'<li><a href="/blog">Locksmith Tips &amp; Guides</a></li>' if BLOG_LIVE else ''}</ul></div>
<div><h3>Service Areas</h3><ul>{loc}<li><a href="/service-area"><strong>All service areas &rarr;</strong></a></li></ul></div>
<div><h3>Also Serving</h3><p style="color:#cbd5e1">{esc(also)} — and the greater Hot Springs area, 24/7.</p>
<p><img src="/assets/img/bbb-rating-locksmith.webp" alt="A+ BBB rated locksmith" width="170" height="77" loading="lazy" style="margin-top:.4rem;border-radius:6px"></p></div>
</div>
<div class="fbtm"><span>&copy; 2026 {esc(SITE['legalName'])}. All rights reserved.</span><span>Hot Springs, Arkansas locksmith</span><span>Smart Site by <a href="https://impact360media.com" target="_blank" rel="noopener">Impact 360</a></span></div>
</div></footer></body></html>"""

def org_node():
    return {
        "@type": "Locksmith", "@id": SITE["domain"] + "/#organization",
        "name": SITE["brand"], "alternateName": SITE["shortName"], "url": SITE["domain"] + "/",
        "telephone": SITE["phone_e164"],
        "image": [SITE["domain"] + SITE["logo"]] + [SITE["domain"] + i for i in SITE["images"]],
        "logo": SITE["domain"] + SITE["logo"],
        "priceRange": "$$",
        # SAB: city-level address only (no street/postal), no geo point — customers are served at their location.
        "address": {"@type": "PostalAddress", "addressLocality": SITE["city"],
                    "addressRegion": SITE["region"], "addressCountry": "US"},
        "areaServed": [{"@type": "City", "name": a} for a in SITE["areas"]],
        "openingHoursSpecification": {"@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "opens": "00:00", "closes": "23:59"},
        "sameAs": SITE["sameAs"],
        "description": "24/7 mobile locksmith in Hot Springs, Arkansas: emergency lockouts, automotive key and fob programming, residential rekeys and lock installation, commercial access control and master key systems, smart locks, and RV & marine locksmith service.",
    }

def build_schema(page):
    slug = page["slug"]; url = SITE["domain"] + ("/" if not slug else f"/{slug}")
    g = []
    g.append({"@type": "WebSite", "@id": SITE["domain"] + "/#website", "url": SITE["domain"] + "/",
              "name": SITE["brand"], "publisher": {"@id": SITE["domain"] + "/#organization"}, "inLanguage": "en-US"})
    g.append(org_node())
    g.append({"@type": "WebPage", "@id": url + "#webpage", "url": url, "name": page["title"],
              "description": page["metaDesc"], "isPartOf": {"@id": SITE["domain"] + "/#website"},
              "about": {"@id": SITE["domain"] + "/#organization"},
              "primaryImageOfPage": {"@id": SITE["domain"] + "/#logo"}, "inLanguage": "en-US"})
    if page.get("type") == "service":
        svc = {"@type": "Service", "@id": url + "#service",
               "serviceType": page.get("serviceType", page["h1"]), "name": page.get("serviceType", page["h1"]),
               "url": url, "provider": {"@id": SITE["domain"] + "/#organization"},
               "areaServed": [{"@type": "City", "name": a} for a in SITE["areas"]],
               "description": page["metaDesc"]}
        if page.get("offers"):
            svc["hasOfferCatalog"] = {"@type": "OfferCatalog", "name": page.get("serviceType", page["h1"]) + " Services",
                "itemListElement": [{"@type": "Offer", "itemOffered": {"@type": "Service", "name": o}} for o in page["offers"]]}
        g.append(svc)
    if page.get("type") == "post":
        p = page["_post"]
        author = p["author"]
        author_node = ({"@id": SITE["domain"] + "/#organization"} if author == SITE["brand"]
                       else {"@type": "Person", "name": author})
        g.append({"@type": "BlogPosting", "@id": url + "#blogposting", "headline": p["postTitle"],
                  "description": p["desc"], "datePublished": p["pubDate"].isoformat(),
                  "dateModified": p["pubDate"].isoformat(),
                  "image": SITE["domain"] + p["heroImage"], "author": author_node,
                  "publisher": {"@id": SITE["domain"] + "/#organization"},
                  "mainEntityOfPage": {"@id": url + "#webpage"},
                  "isPartOf": {"@id": SITE["domain"] + "/#website"}, "url": url})
    if page.get("type") == "bloghub" and page.get("_posts"):
        g.append({"@type": "Blog", "@id": url + "#blog", "name": page["title"],
                  "description": page["metaDesc"], "publisher": {"@id": SITE["domain"] + "/#organization"},
                  "blogPost": [{"@type": "BlogPosting", "@id": f'{SITE["domain"]}/{p["slug"]}#blogposting',
                                "headline": p["postTitle"], "description": p["desc"],
                                "datePublished": p["pubDate"].isoformat(),
                                "url": f'{SITE["domain"]}/{p["slug"]}'} for p in page["_posts"]]})
    if slug and page.get("type") == "post":
        g.append({"@type": "BreadcrumbList", "@id": url + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE["domain"] + "/"},
            {"@type": "ListItem", "position": 2, "name": "Blog", "item": SITE["domain"] + "/blog"},
            {"@type": "ListItem", "position": 3, "name": page.get("h1", ""), "item": url}]})
    elif slug:
        g.append({"@type": "BreadcrumbList", "@id": url + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE["domain"] + "/"},
            {"@type": "ListItem", "position": 2, "name": SLUG_LABEL.get(slug, page.get("h1", "")), "item": url}]})
    if page.get("faqs"):
        g.append({"@type": "FAQPage", "@id": url + "#faq", "isPartOf": {"@id": url + "#webpage"},
                  "mainEntity": [{"@type": "Question", "name": f["q"],
                                  "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", f["a"]).strip()}}
                                 for f in page["faqs"]]})
    return {"@context": "https://schema.org", "@graph": g}

def hero_html(page):
    sub = page.get("heroSub", "")
    trust = page.get("trust", ["24/7 Emergency Service", "Licensed &amp; Insured", "15+ Years Experience", "Fast Mobile Response"])
    tspan = "".join(f'<span>&#10003; {t}</span>' for t in trust)
    img = page.get("heroImage")
    cls = "hero has-img" if img else "hero"
    style = (f" style=\"background-image:linear-gradient(rgba(15,32,80,.84),rgba(15,32,80,.9)),url('{img}');"
             f"background-size:cover;background-position:center\"") if img else ""
    return f"""<section class="{cls}"{style}><div class="wrap">
<h1>{esc(page['h1'])}</h1><p class="sub">{linkify_phone(esc(sub))}</p>
<div class="cta"><a class="btn btn-call" href="tel:{SITE['phone_tel']}">Call {SITE['phone_display']}</a>
<a class="btn btn-ghost" href="/contact">Request Service</a></div>
<div class="trust">{tspan}</div></div></section>"""

def render(page):
    parts = [head(page), header_html(), breadcrumb_html(page), hero_html(page)]
    for sec in page.get("sections", []):
        parts.append(section_html(sec))
    parts.append(service_area_map_html(page))
    parts.append(area_hub_html(page))
    parts.append(testimonials_html(page))
    parts.append(ghl_form_html(page))
    parts.append(map_html(page))
    parts.append(faq_html(page.get("faqs")))
    parts.append(related_html(page))
    parts.append(finalcta_html(page))
    parts.append(promise_bar_html())
    parts.append(footer_html())
    return "".join(p for p in parts if p)

def write_page(page, html_out=None):
    slug = page["slug"]
    # Flat files (slug.html) rather than slug/index.html: this makes Cloudflare Pages serve
    # the extensionless URL with NO trailing slash (and 308 the slash variant to it), matching
    # <link rel=canonical> and the existing live arkeylock.com sitemap. (index.html dirs do the opposite.)
    outpath = os.path.join(DIST, "index.html") if not slug else os.path.join(DIST, f"{slug}.html")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(html_out if html_out is not None else render(page))
    return (SITE["domain"] + ("/" if not slug else f"/{slug}"))

# ---------------------------------------------------------------------------
# Blog: markdown posts with scheduled publishing.
#
# Posts live in posts/*.md (filename = URL slug, root-level like every other
# page). Frontmatter between '---' fences:
#   title, description, pubDate (YYYY-MM-DD), heroImage, heroAlt   [required]
#   seoTitle (short <title> override), author, draft: true          [optional]
#
# A post is INVISIBLE until pubDate <= today (UTC): no page, no /blog card, no
# sitemap/llms entry, no nav link — and any <a> in OTHER pages pointing at it
# is unwrapped to plain text (restored automatically once it publishes). The
# daily rebuild (GitHub Actions, 11:00 UTC) flips each post live on its date.
# ---------------------------------------------------------------------------
SLUG_LABEL["blog"] = "Blog"

def parse_frontmatter(raw, name):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.S)
    if not m:
        raise SystemExit(f"posts/{name}: missing --- frontmatter block")
    meta = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        meta[k.strip()] = v
    return meta, m.group(2)

_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")

def md_inline(s):
    s = esc(s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = _MD_LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    return s

def md_blocks(md):
    """Minimal markdown -> HTML: h2/h3, paragraphs, ul/ol, blockquote, bold/em/links.
    Deliberately small (zero deps) — matches the subset our post copy uses."""
    out, para = [], []
    lines = md.split("\n")
    i = 0
    def flush():
        if para:
            out.append("<p>" + md_inline(" ".join(para)) + "</p>")
            para.clear()
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            flush(); i += 1; continue
        if s.startswith("### "):
            flush(); out.append("<h3>" + md_inline(s[4:]) + "</h3>"); i += 1; continue
        if s.startswith("## "):
            flush(); out.append("<h2>" + md_inline(s[3:]) + "</h2>"); i += 1; continue
        if re.match(r"^[-*] ", s):
            flush(); items = []
            while i < len(lines) and re.match(r"^[-*] ", lines[i].strip()):
                items.append("<li>" + md_inline(lines[i].strip()[2:]) + "</li>"); i += 1
            out.append("<ul>" + "".join(items) + "</ul>"); continue
        if re.match(r"^\d+\. ", s):
            flush(); items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i].strip()):
                items.append("<li>" + md_inline(re.sub(r"^\d+\. ", "", lines[i].strip())) + "</li>"); i += 1
            out.append("<ol>" + "".join(items) + "</ol>"); continue
        if s.startswith(">"):
            flush(); quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip("> ").strip()); i += 1
            out.append("<blockquote><p>" + md_inline(" ".join(q for q in quote if q)) + "</p></blockquote>"); continue
        para.append(s); i += 1
    flush()
    return "\n".join(out)

def load_posts():
    posts = []
    today = datetime.now(timezone.utc).date()
    for fp in sorted(glob.glob(os.path.join(POSTS, "*.md"))):
        name = os.path.basename(fp)
        if name.lower() == "readme.md" or name.startswith("_"):
            continue  # docs/scratch files, not posts
        meta, body = parse_frontmatter(open(fp, encoding="utf-8").read(), name)
        for req in ("title", "description", "pubDate", "heroImage", "heroAlt"):
            if not meta.get(req):
                raise SystemExit(f"posts/{name}: missing required frontmatter field '{req}'")
        pub = date.fromisoformat(meta["pubDate"])
        img = os.path.join(ROOT, meta["heroImage"].lstrip("/"))
        if not os.path.exists(img):
            raise SystemExit(f"posts/{name}: heroImage {meta['heroImage']} not found under {ROOT}")
        posts.append({
            "slug": name[:-3], "postTitle": meta["title"], "seoTitle": meta.get("seoTitle"),
            "desc": meta["description"], "pubDate": pub,
            "heroImage": meta["heroImage"], "heroAlt": meta["heroAlt"],
            "author": meta.get("author", SITE["brand"]),
            "live": meta.get("draft", "").lower() != "true" and pub <= today,
            "body_md": body,
        })
    posts.sort(key=lambda p: p["pubDate"], reverse=True)
    return posts

_GATE_A = re.compile(r'<a\s+href="(/[^"]*)"[^>]*>(.*?)</a>', re.S)

def gate_unpublished_links(html_s, unpublished):
    """Unwrap anchors that point at not-yet-published posts so nothing links to a
    404. The daily rebuild restores each link once its target goes live."""
    def _sub(m):
        slug = m.group(1).lstrip("/").split("?")[0].split("#")[0]
        return m.group(2) if slug in unpublished else m.group(0)
    return _GATE_A.sub(_sub, html_s)

def _date_disp(d):
    return f"{d.strftime('%B')} {d.day}, {d.year}"

def render_post(post, unpublished):
    page = {"slug": post["slug"], "title": post["seoTitle"] or post["postTitle"],
            "metaDesc": post["desc"], "h1": post["postTitle"], "type": "post",
            "ogType": "article", "heroImage": post["heroImage"], "_post": post}
    body = linkify_phone(gate_unpublished_links(md_blocks(post["body_md"]), unpublished))
    article = (
        '<section class="block"><div class="wrap">'
        f'<header class="post-head"><h1>{esc(post["postTitle"])}</h1>'
        f'<p class="post-byline">By {esc(post["author"])} &middot; '
        f'<time datetime="{post["pubDate"].isoformat()}">{_date_disp(post["pubDate"])}</time></p></header>'
        f'<img class="post-hero" src="{post["heroImage"]}" alt="{esc(post["heroAlt"])}" '
        'width="1200" height="675" loading="eager" decoding="async">'
        f'<div class="post-body">{body}</div>'
        '</div></section>')
    parts = [head(page), header_html(), breadcrumb_html(page), article,
             finalcta_html({}), promise_bar_html(), footer_html()]
    return page, "".join(parts)

def render_bloghub(published):
    page = {"slug": "blog", "title": f"Locksmith Tips & Guides | {SITE['shortName']} Blog",
            "metaDesc": "Practical locksmith advice for Hot Springs & central Arkansas — lockouts, car keys, rekeying after a move, smart locks, and how to avoid locksmith scams.",
            "h1": "Locksmith Tips & Guides", "type": "bloghub", "_posts": published}
    cards = ""
    for p in published:
        cards += (f'<a class="card lift bcard" href="/{p["slug"]}">'
                  f'<img src="{p["heroImage"]}" alt="{esc(p["heroAlt"])}" width="640" height="360" loading="lazy" decoding="async">'
                  f'<div class="bbody"><h3>{esc(p["postTitle"])}</h3>'
                  f'<p class="bdate"><time datetime="{p["pubDate"].isoformat()}">{_date_disp(p["pubDate"])}</time></p>'
                  f'<p class="bdesc">{esc(p["desc"])}</p>'
                  f'<span class="more">Read more &rarr;</span></div></a>')
    body = (
        '<section class="block"><div class="wrap">'
        '<h1 style="font-size:clamp(1.7rem,4.5vw,2.5rem);font-weight:900;letter-spacing:-.01em">Locksmith Tips &amp; Guides</h1>'
        '<p class="lead" style="max-width:680px;margin:.5rem 0 1.8rem">Straight answers from a working Hot Springs '
        'locksmith &mdash; what to do in a lockout, what car keys really involve, when to rekey, and how to avoid '
        'getting burned by scam locksmiths.</p>'
        f'<div class="bloggrid">{cards}</div>'
        '</div></section>')
    parts = [head(page), header_html(), breadcrumb_html(page), body,
             finalcta_html({}), promise_bar_html(), footer_html()]
    return page, "".join(parts)

def main():
    global BLOG_LIVE
    # Copy static assets first so a from-scratch build (CI) produces a complete dist/.
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(DIST, "assets"), dirs_exist_ok=True)
    with open(os.path.join(DIST, "assets", "styles.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    pages = []
    for fp in sorted(glob.glob(os.path.join(CONTENT, "*.json"))):
        pages.append(json.load(open(fp, encoding="utf-8")))
    posts = load_posts()
    published = [p for p in posts if p["live"]]
    unpublished = {p["slug"] for p in posts if not p["live"]}
    BLOG_LIVE = bool(published)
    taken = {p["slug"] for p in pages}
    for p in posts:
        if p["slug"] in taken or p["slug"] == "blog":
            raise SystemExit(f"posts/{p['slug']}.md: slug collides with an existing page")
    urls = []
    for p in pages:
        # Gate applies sitewide: JSON content may cross-link a post that isn't out yet.
        urls.append(write_page(p, gate_unpublished_links(render(p), unpublished)))
    if BLOG_LIVE:
        hub_page, hub_html = render_bloghub(published)
        urls.append(write_page(hub_page, hub_html))
        for p in published:
            post_page, post_html = render_post(p, unpublished)
            urls.append(write_page(post_page, post_html))
        print(f"Blog: {len(published)} published, {len(posts) - len(published)} scheduled (hidden until pubDate)")
    elif posts:
        print(f"Blog: 0 published, {len(posts)} scheduled — hub and nav link suppressed until the first pubDate passes")
    # Remove stale HTML from prior local builds (renamed pages, unpublished/deleted posts) so
    # nothing outside the current page set can ride along in a deploy. CI builds start clean.
    keep = {"404.html"} | {("index.html" if u.endswith("/") else u.rsplit("/", 1)[-1] + ".html") for u in urls}
    for f in glob.glob(os.path.join(DIST, "*.html")):
        if os.path.basename(f) not in keep:
            os.remove(f)
            print(f"  removed stale {os.path.basename(f)}")
    # sitemap
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"<url><loc>{u}</loc></url>")
    sm.append("</urlset>")
    open(os.path.join(DIST, "sitemap.xml"), "w").write("\n".join(sm))
    # legacy URL redirects (Cloudflare Pages _redirects format) — regenerated every build.
    # A redirect is dropped automatically if a real page now exists at its source (lets a
    # new post reclaim a legacy blog slug); /articles points at the hub once the blog is live.
    built_slugs = {u.rsplit("/", 1)[-1] for u in urls}
    redirects = []
    for src, dst in REDIRECTS:
        if src.lstrip("/") in built_slugs:
            print(f"  redirect {src} dropped — page now exists")
            continue
        if src == "/articles" and BLOG_LIVE:
            dst = "/blog"
        redirects.append((src, dst))
    # Emit each rule twice: bare and trailing-slash. Cloudflare Pages matches
    # _redirects sources exactly, so /foo and /foo/ are distinct paths. The old
    # Duda URLs used trailing slashes, so without the /foo/ variant they 404
    # instead of redirecting (real pages get trailing-slash normalization for
    # free; _redirects rules do not).
    redirect_lines = []
    for src, dst in redirects:
        redirect_lines.append(f"{src}  {dst}  301")
        if not src.endswith("/"):
            redirect_lines.append(f"{src}/  {dst}  301")
    open(os.path.join(DIST, "_redirects"), "w").write(
        "# Legacy arkeylock.com URLs -> current pages (301). Generated by build.py.\n" +
        "\n".join(redirect_lines) + "\n")
    if SITE.get("noindex"):
        open(os.path.join(DIST, "robots.txt"), "w").write("User-agent: *\nDisallow: /\n")
        open(os.path.join(DIST, "_headers"), "w").write("/*\n  X-Robots-Tag: noindex, nofollow\n")
    else:
        open(os.path.join(DIST, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE['domain']}/sitemap.xml\n")
        # Live mode still noindexes the always-on pages.dev alias + per-deploy hash
        # previews. Host-scoped rules — they can never match arkeylock.com.
        open(os.path.join(DIST, "_headers"), "w").write(
            "https://:project.pages.dev/*\n  X-Robots-Tag: noindex\n"
            "https://:version.:project.pages.dev/*\n  X-Robots-Tag: noindex\n")
    open(os.path.join(DIST, "llms.txt"), "w").write(
        f"# {SITE['brand']}\n> 24/7 mobile locksmith in Hot Springs, Arkansas. Emergency lockouts, automotive key & fob programming, residential, commercial access control, smart locks, RV & marine.\n\n"
        f"Phone: {SITE['phone_display']}\nService area: {SITE['city']}, {SITE['region']} and the surrounding area (mobile service-area business — no walk-in location)\nHours: 24/7\n\n## Pages\n" +
        "\n".join(f"- {u}" for u in urls) + "\n")
    # 404 page — Cloudflare Pages serves /404.html with a 404 status for unmatched paths
    p404 = {"slug": "404", "title": "Page Not Found | " + SITE["brand"], "metaDesc": "Page not found.",
            "h1": "Page Not Found", "type": "info"}
    body404 = (head(p404) + header_html() +
               '<section class="block"><div class="wrap" style="text-align:center;min-height:42vh">'
               '<h1>Page Not Found</h1><p>Sorry &mdash; that page does not exist or has moved.</p>'
               '<p style="margin-top:1.3rem"><a class="btn btn-navy" href="/">Back to Home</a> '
               '<a class="btn btn-call" href="tel:' + SITE["phone_tel"] + '">Call ' + SITE["phone_display"] + '</a></p>'
               '</div></section>' + promise_bar_html() + footer_html())
    open(os.path.join(DIST, "404.html"), "w", encoding="utf-8").write(body404)
    print(f"Built {len(pages)} pages -> {DIST}")
    for u in urls: print("  ", u)

if __name__ == "__main__":
    main()
