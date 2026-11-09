"""Selection rules: which new Brazilian companies count as "creative tech".

CNAE codes are matched on their 4-digit class (the first 4 digits of the
7-digit subclass published by the Receita Federal, e.g. 6203100 -> 6203).
After each monthly run the pipeline writes data/cnae_rules.md with the
official description of every subclass matched, so the lists can be reviewed.
"""
import re
import unicodedata

# --- Technology activities -------------------------------------------------
TECH_CLASSES = {
    "6201": "Custom software development",
    "6202": "Customisable software development & licensing",
    "6203": "Non-customisable software (apps, SaaS)",
    "6204": "IT consulting",
    "6209": "IT support & other IT services",
    "6311": "Data processing, application & hosting services",
    "6319": "Internet portals & content providers",
}

# --- Creative activities, grouped into the sectors shown on the site --------
CREATIVE_CLASSES = {
    # Fashion: clothing, accessories, bags, footwear (manufacturing and retail)
    "1411": "Fashion", "1412": "Fashion", "1414": "Fashion",
    "1521": "Fashion", "1531": "Fashion", "1532": "Fashion",
    "1533": "Fashion", "1539": "Fashion",
    "4781": "Fashion", "4782": "Fashion",
    # Beauty: cosmetics & perfume (manufacturing and retail)
    "2063": "Beauty", "4772": "Beauty",
    # Jewellery: gem cutting, jewellery, costume jewellery (manufacturing and retail)
    "3211": "Jewellery", "3212": "Jewellery", "4783": "Jewellery",
    # Design & living: design services and furniture making
    "7410": "Design & living", "3101": "Design & living",
    "3102": "Design & living", "3103": "Design & living",
    # Film & photo
    "5911": "Film & photo", "5912": "Film & photo", "5913": "Film & photo",
    "7420": "Film & photo",
    # Music & audio
    "5920": "Music & audio",
    # Arts & culture
    "9001": "Arts & culture", "9002": "Arts & culture",
    # Publishing
    "5811": "Publishing", "5813": "Publishing", "5821": "Publishing",
}

# Subclasses excluded even though their class is listed above
EXCLUDED_SUBCLASSES = {
    "3211603",  # coin and medal minting
}

SECTORS = ["Fashion", "Beauty", "Jewellery", "Design & living", "Film & photo",
           "Music & audio", "Arts & culture", "Publishing", "Other startups"]

# --- Name keywords (matched on whole words, accents removed) ---------------
CREATIVE_KEYWORDS = {
    "Fashion": ["MODA", "FASHION", "VESTUARIO", "ROUPAS?", "STREETWEAR", "WEAR",
                "APPAREL", "ATELIE", "ATELIER", "SNEAKERS?"],
    "Beauty": ["BELEZA", "BEAUTY", "COSMETICOS?", "COSMETICS?", "MAKEUP", "MAKE",
               "SKINCARE", "SKIN", "PERFUMARIA", "PERFUMES?"],
    "Jewellery": ["JOIAS?", "JOALHERIA", "JEWELRY", "JEWELLERY", "JEWELS?", "BIJU",
                  "BIJUTERIAS?", "SEMIJOIAS?", "GEMAS?", "GEMS?"],
    "Design & living": ["DESIGN", "DECOR", "DECORACAO", "INTERIORES", "MOVEIS"],
    "Film & photo": ["FILMES?", "FILMS?", "CINEMA", "FOTOS?", "FOTOGRAFIA", "PHOTOS?",
                     "PHOTOGRAPHY", "AUDIOVISUAL", "VIDEOS?", "STUDIOS?", "ESTUDIOS?"],
    "Music & audio": ["MUSICA", "MUSICAS", "MUSIC", "AUDIO", "SOUND", "PODCASTS?",
                      "RECORDS"],
    "Arts & culture": ["ARTE", "ARTES", "ART", "ARTS", "GALERIA", "GALLERY", "CULTURA",
                       "CULTURAL", "CRIATIVA", "CRIATIVO", "CRIATIVOS", "CREATIVE",
                       "ARTESANATO", "CRAFTS?"],
    "Publishing": ["EDITORA", "LIVROS", "BOOKS", "PUBLISHING"],
}

TECH_KEYWORDS = ["TECNOLOGIA", "TECNOLOGIAS", "DIGITAL", "DIGITAIS", "APP", "APPS",
                 "PLATAFORMA", "PLATFORM", "SOFTWARE", "LAB", "LABS", "DATA", "ONLINE",
                 "WEB", "CLOUD", "SAAS", "STARTUP", "AI", "IA", "INOVA", "INOVACAO",
                 "INOVACOES", "MARKETPLACE", "ECOMMERCE", "METAVERSO", "NFT", "GAMES?",
                 "STREAMING", "ROBOTICA", "3D", "VIRTUAL", "PHYGITAL"]
# "TECH" also counts when glued to another word (FASHIONTECH, BEAUTYTECH...)
TECH_SUBSTRINGS = ["TECH"]

# --- Legal forms ------------------------------------------------------------
# Only business entities (codes 2xxx) are kept, minus the ones below.
EXCLUDED_LEGAL_NATURES = {
    "2135",  # Empresário individual (includes micro-entrepreneurs)
    "2143",  # Cooperativa
    "2011",  # Empresa pública
    "2038",  # Sociedade de economia mista
}
CORPORATION_NATURES = {"2046", "2054"}  # Sociedade anônima (aberta / fechada)

# --- Email domains that never identify a company's own website -------------
FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.com.br", "outlook.com",
    "outlook.com.br", "live.com", "msn.com", "yahoo.com", "yahoo.com.br", "ymail.com",
    "icloud.com", "me.com", "mac.com", "bol.com.br", "uol.com.br", "terra.com.br",
    "ig.com.br", "globo.com", "globomail.com", "r7.com", "zipmail.com.br",
    "oi.com.br", "protonmail.com", "proton.me", "aol.com", "gmx.com", "zoho.com",
    "yandex.com", "mail.com", "email.com", "hotmail.es", "outlook.es", "gmail.com.br",
    "hotmal.com", "hotmai.com", "gmial.com", "gmai.com", "gamil.com",
}
# Domains that look like accounting or paperwork firms (they register companies
# for clients and leave their own email in the registry).
SERVICE_DOMAIN_HINTS = ["contab", "contador", "contadores", "contabil", "escritorio",
                        "assessoria", "legaliza", "abertura", "despachante", "fiscal",
                        "tributar", "auditoria"]


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


def _compile(words):
    return re.compile(r"\b(?:" + "|".join(words) + r")\b")


_CREATIVE_RE = {sector: _compile(words) for sector, words in CREATIVE_KEYWORDS.items()}
_TECH_RE = _compile(TECH_KEYWORDS)


_GLUED = {sector: [w[:-2] if w.endswith("S?") else w.rstrip("?") for w in words]
          for sector, words in CREATIVE_KEYWORDS.items()}


def creative_sectors_from_name(name_norm):
    found = [s for s, rx in _CREATIVE_RE.items() if rx.search(name_norm)]
    glued = name_norm.replace(" ", "")
    for sector, words in _GLUED.items():
        # FASHIONTECH, BEAUTYTECH, MODATECH, ARTTECH...
        if sector not in found and any(len(w) >= 3 and w + "TECH" in glued for w in words):
            found.append(sector)
    return found


def has_tech_name(name_norm):
    if _TECH_RE.search(name_norm):
        return True
    return any(sub in name_norm for sub in TECH_SUBSTRINGS)


def classify_cnaes(codes):
    """Return (tech_any, creative_sectors) for a list of 7-digit CNAE codes."""
    tech = False
    sectors = []
    for code in codes:
        code = code.strip()
        if len(code) < 4 or code in EXCLUDED_SUBCLASSES:
            continue
        cls = code[:4]
        if cls in TECH_CLASSES:
            tech = True
        sector = CREATIVE_CLASSES.get(cls)
        if sector and sector not in sectors:
            sectors.append(sector)
    return tech, sectors


def is_relevant_cnae(code):
    code = code.strip()
    if code in EXCLUDED_SUBCLASSES:
        return False
    return code[:4] in TECH_CLASSES or code[:4] in CREATIVE_CLASSES
