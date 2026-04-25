from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, unquote, quote
import re

PRICE_PUBLIC = "Public price extracted"
PRICE_SNIPPET = "Search-snippet price only"
PRICE_LOGIN = "Login/account price required"
PRICE_QUOTE = "Quote required"
PRICE_HIDDEN = "No public price detected by current parser"
PRICE_FAILED = "Extraction failed"
PRICE_RE = re.compile(r"(?:US\$|\$)\s?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)|\b([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s?(?:USD)\b", re.I)
QUOTE_RE = re.compile(r"(?i)(request\s+a?\s*quote|ask\s+for\s+quotation|quote\s+only|bulk\s+inquiry|pricing\s+on\s+request|price\s+on\s+request|please\s+inquire|inquiry\s+price|inquire)")
LOGIN_RE = re.compile(r"(?i)(sign\s*in\s*(?:or\s*register)?\s*to\s*(?:check|view|see)\s*(?:your\s*)?price|login\s*to\s*view\s*price|log\s*in\s*to\s*view\s*price|account\s*specific\s*price|your\s*price)")
CATALOG_PATTERNS = [
    re.compile(r"\b(?:catalog|cat\.?|sku|item|part|product(?:\s*id)?)\s*(?:no\.?|number|#)?\s*[:#-]\s*([A-Z0-9][A-Z0-9._/-]{3,35})\b", re.I),
    re.compile(r"\b(?:catalog|cat\.?|sku|item|part|product(?:\s*id)?)\s*(?:no\.?|number|#)?\s+([A-Z0-9][A-Z0-9._/-]{3,35})\b", re.I),
]
BAD_CATALOG_TOKENS = {
    "library", "introduction", "analysis", "alysis", "search", "result", "results",
    "product", "products", "compound", "compounds", "catalog", "category", "price", "stock",
    "availability", "phillyrin", "forsythin", "standard", "details", "chemical", "cas",
    "home", "html", "login", "register", "contact", "cart", "checkout", "shipping",
}
LANG_PREFIXES = {"us", "en", "jp", "kr", "de", "fr", "sp", "es", "cn", "uk", "eu", "ca", "au"}
SEARCH_QUERY_KEYS = {"keyword", "search", "q", "text", "term", "query", "searchdto.searchparam", "utm_source", "utm_medium", "utm_campaign", "srsltid"}

@dataclass(frozen=True)
class SupplierAdapter:
    name: str
    domains: tuple[str, ...]
    search_url_templates: tuple[str, ...]
    notes: str
    public_price_likelihood: str = "mixed"
    search_priority: int = 50
    source_tier: str = "standard"
    expected_behavior: str = "mixed_public_or_quote"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return any(host == d or host.endswith("." + d) or d in host for d in self.domains)

# v16 registry: source-of-truth supplier map.
# We walk suppliers directly with supplier-specific search/product URL strategies first,
# then use optional broad search as a supplement. Keep search templates ordered from
# most reliable to least reliable for each supplier.
ADAPTERS: tuple[SupplierAdapter, ...] = (
    SupplierAdapter("TargetMol", ("targetmol.com",), ("https://www.targetmol.com/search?keyword={cas}",), "Often exposes Pack Size / Price / USA Stock / Global Stock tables.", "high", 140, "price_first", "public_price_common"),
    SupplierAdapter("MedChemExpress", ("medchemexpress.com",), ("https://www.medchemexpress.com/cas/{cas}.html", "https://www.medchemexpress.com/search.html?q={cas}", "https://www.medchemexpress.com/search.html?keyword={cas}"), "CAS pages frequently link to the real compound page, where size/price/stock rows live.", "high", 138, "price_first", "public_price_common"),
    SupplierAdapter("SelleckChem", ("selleckchem.com",), ("https://www.selleckchem.com/search.html?searchDTO.searchParam={cas}", "https://www.selleckchem.com/search?keyword={cas}"), "Bioactive catalog with frequent public size/price/stock rows.", "high", 136, "price_first", "public_price_common"),
    SupplierAdapter("Cayman Chemical", ("caymanchem.com",), ("https://www.caymanchem.com/search?q={cas}",), "Often exposes pack sizes, pricing, availability on product/item pages.", "high", 134, "price_first", "public_price_common"),
    SupplierAdapter("MolPort", ("molport.com",), ("https://www.molport.com/shop/find-chemicals-by-cas-number/{cas}", "https://www.molport.com/shop/search?query={cas}"), "Marketplace with pack/price potential; may require JS/API for full data.", "high", 132, "marketplace", "marketplace_public_mixed"),
    SupplierAdapter("Adooq", ("adooq.com",), ("https://www.adooq.com/search?q={cas}", "https://www.adooq.com/catalogsearch/result/?q={cas}"), "Magento-style catalog; product pages often expose Grouped product items Size / Price / Stock.", "high", 130, "price_first", "public_price_common"),
    SupplierAdapter("ApexBio", ("apexbt.com",), ("https://www.apexbt.com/search?q={cas}", "https://www.apexbt.com/catalogsearch/result/?q={cas}"), "Public size/price/stock rows on many compound pages.", "high", 128, "price_first", "public_price_common"),
    SupplierAdapter("GLP Bio", ("glpbio.com",), ("https://www.glpbio.com/search?q={cas}", "https://www.glpbio.com/catalogsearch/result/?q={cas}"), "Public size/price/stock common; multilingual mirrors must be deduped.", "high", 126, "price_first", "public_price_common"),
    SupplierAdapter("AbMole", ("abmole.com",), ("https://www.abmole.com/search?q={cas}",), "Public product pages commonly sit under /products/<slug>.html; search endpoint is preferred over older catalogsearch path.", "high", 124, "price_first", "public_price_common"),
    SupplierAdapter("ChemFaces", ("chemfaces.com",), ("https://www.chemfaces.com/search/?q={cas}", "https://www.chemfaces.com/search?q={cas}"), "Natural-products/reference supplier with many public prices.", "high", 122, "price_first", "public_price_common"),
    SupplierAdapter("BioCrick", ("biocrick.com",), ("https://www.biocrick.com/search?keyword={cas}",), "Natural products catalog; public price rows appear on many pages.", "medium", 120, "price_first", "public_price_mixed"),
    SupplierAdapter("CSNpharm", ("csnpharm.com",), ("https://csnpharm.com/search?q={cas}",), "Often has size/price/stock tables; some values encoded or login-dependent.", "medium", 118, "price_first", "public_price_mixed"),
    SupplierAdapter("InvivoChem", ("invivochem.com",), ("https://www.invivochem.com/search?q={cas}", "https://www.invivochem.com/search.html?q={cas}"), "May not carry every CAS; older catalogsearch URLs can 404, so v16 tries /search first.", "medium", 116, "price_first", "public_price_mixed"),
    SupplierAdapter("AdooQ Bioscience", ("adooqbioscience.com",), ("https://www.adooqbioscience.com/catalogsearch/result/?q={cas}", "https://www.adooqbioscience.com/search?q={cas}"), "Alternate AdooQ domain seen in some search results.", "medium", 114, "price_first", "public_price_mixed"),
    SupplierAdapter("Biorbyt", ("biorbyt.com",), ("https://www.biorbyt.com/search?q={cas}",), "Research reagent supplier; public pricing varies by product/region.", "medium", 112, "price_first", "public_price_mixed"),
    SupplierAdapter("US Biological", ("usbiological.com",), ("https://www.usbiological.com/search?q={cas}", "https://www.usbio.net/search?q={cas}"), "Biochem/reagent catalog; public pricing varies.", "medium", 110, "price_first", "public_price_mixed"),
    SupplierAdapter("Biosynth", ("biosynth.com",), ("https://www.biosynth.com/search?query={cas}", "https://www.biosynth.com/search?q={cas}"), "Biosynth product pages can be discovered from search results; prices often load via JS and may show Loading Prices.", "medium", 108, "price_first", "js_price_loader_common"),
    SupplierAdapter("1ClickChemistry", ("1clickchemistry.com",), ("https://www.1clickchemistry.com/search?query={cas}", "https://www.1clickchemistry.com/search?q={cas}"), "Small-molecule catalog; public price visibility varies.", "medium", 106, "price_first", "public_price_mixed"),

    SupplierAdapter("TCI Chemicals", ("tcichemicals.com",), ("https://www.tcichemicals.com/US/en/search?text={cas}", "https://www.tcichemicals.com/US/en/search?text={cas}&searchtype=product"), "Reagent catalog; public pricing varies by region/session.", "medium", 98, "standard", "public_or_session_mixed"),
    SupplierAdapter("Oakwood Chemical", ("oakwoodchemical.com",), ("https://oakwoodchemical.com/Search?term={cas}", "https://www.oakwoodchemical.com/Search?term={cas}"), "Specialty chemical catalog; mixed public price/quote behavior.", "medium", 96, "standard", "public_or_quote_mixed"),
    SupplierAdapter("Chem-Impex", ("chemimpex.com",), ("https://www.chemimpex.com/search?search={cas}",), "Specialty catalog; public/quote mixed. Needs strict product identity gating.", "medium", 94, "standard", "public_or_quote_mixed"),
    SupplierAdapter("Combi-Blocks", ("combi-blocks.com",), ("https://www.combi-blocks.com/cgi-bin/find.cgi?search={cas}",), "Building-block catalog; pricing may be public, quote, or login dependent.", "medium", 92, "standard", "public_or_quote_mixed"),
    SupplierAdapter("BLD Pharm", ("bldpharm.com",), ("https://www.bldpharm.com/search?search={cas}", "https://www.bldpharm.com/search?q={cas}"), "Building-block catalog for advanced intermediates.", "medium", 90, "standard", "public_or_quote_mixed"),
    SupplierAdapter("Ambeed", ("ambeed.com",), ("https://www.ambeed.com/search?q={cas}", "https://www.ambeed.com/search.html?search={cas}"), "Building-block catalog; product pages can be hidden behind a region-selection overlay and account/login price prompts.", "medium", 88, "marketplace", "public_or_js_mixed"),
    SupplierAdapter("A2B Chem", ("a2bchem.com",), ("https://www.a2bchem.com/search.aspx?search={cas}",), "Building-block supplier; useful candidate source.", "medium", 86, "standard", "public_or_quote_mixed"),
    SupplierAdapter("Enamine", ("enaminestore.com", "enamine.net"), ("https://enaminestore.com/catalogsearch/result/?q={cas}", "https://enamine.net/compound/search?q={cas}"), "Screening/building block catalog; may need account/API for accurate price.", "medium", 84, "standard", "quote_or_account_mixed"),
    SupplierAdapter("Matrix Scientific", ("matrixscientific.com",), ("https://www.matrixscientific.com/search?query={cas}",), "Specialty chemical supplier; public price varies.", "medium", 82, "standard", "public_or_quote_mixed"),
    SupplierAdapter("Santa Cruz Biotechnology", ("scbt.com",), ("https://www.scbt.com/search?query={cas}",), "Research chemicals/biochemicals; some public prices.", "medium", 80, "standard", "public_or_quote_mixed"),
    SupplierAdapter("CymitQuimica", ("cymitquimica.com",), ("https://cymitquimica.com/products?search={cas}", "https://cymitquimica.com/search?q={cas}"), "European catalog/marketplace; public price often visible.", "medium", 78, "marketplace", "public_price_mixed"),
    SupplierAdapter("Toronto Research Chemicals", ("trc-canada.com",), ("https://www.trc-canada.com/search?search={cas}",), "Reference/specialty chemicals; public price visibility varies.", "medium", 76, "standard", "public_or_quote_mixed"),

    SupplierAdapter("Fisher Scientific", ("fishersci.com",), ("https://www.fishersci.com/us/en/catalog/search/products?keyword={cas}", "https://www.fishersci.com/us/en/browse/cas/{cas}"), "Large distributor; pricing often account/login-specific.", "low", 60, "login_gated", "login_price_common"),
    SupplierAdapter("Thermo Fisher / Alfa Aesar", ("thermofisher.com", "alfa.com"), ("https://www.thermofisher.com/search/results?keyword={cas}",), "Thermo/Alfa/Acros frequently require account/session JS pricing.", "low", 58, "login_gated", "login_price_common"),
    SupplierAdapter("Sigma-Aldrich", ("sigmaaldrich.com", "milliporesigma.com"), ("https://www.sigmaaldrich.com/US/en/search/{cas}",), "Strong catalog coverage; prices often country/account/session dependent.", "low", 56, "login_gated", "login_price_common"),
    SupplierAdapter("VWR / Avantor", ("vwr.com", "avantorsciences.com"), ("https://us.vwr.com/store/search?keyword={cas}",), "Distributor catalog; account-specific pricing common.", "low", 54, "login_gated", "login_price_common"),

    SupplierAdapter("ChemicalBook", ("chemicalbook.com",), ("https://www.chemicalbook.com/Search_EN.aspx?keyword={cas}",), "Supplier directory; useful RFQ breadth, not price source-of-truth.", "directory", 44, "directory", "directory_rfq"),
    SupplierAdapter("ChemBlink", ("chemblink.com",), ("https://www.chemblink.com/search.aspx?search={cas}",), "Supplier directory; useful for RFQ discovery.", "directory", 42, "directory", "directory_rfq"),
    SupplierAdapter("ChemExper", ("chemexper.com",), ("https://www.chemexper.com/search/cas/{cas}.html",), "Supplier directory; broad catalog leads, not reliable pricing.", "directory", 40, "directory", "directory_rfq"),
    SupplierAdapter("LookChem", ("lookchem.com",), ("https://www.lookchem.com/cas-{cas}.html",), "Supplier directory; useful RFQ lead source.", "directory", 38, "directory", "directory_rfq"),
)

PUBLIC_PRICE_SUPPLIERS = tuple(a.name for a in ADAPTERS if a.source_tier == "price_first")


def sorted_adapters(tiers: tuple[str, ...] | None = None) -> list[SupplierAdapter]:
    adapters = [a for a in ADAPTERS if tiers is None or a.source_tier in tiers]
    return sorted(adapters, key=lambda a: a.search_priority, reverse=True)


def adapter_for_url(url: str) -> SupplierAdapter | None:
    for adapter in ADAPTERS:
        if adapter.matches(url):
            return adapter
    return None


def supplier_name_for_url(url: str, fallback: str = "Unknown supplier") -> str:
    adapter = adapter_for_url(url)
    if adapter:
        return adapter.name
    host = urlparse(url).netloc.lower().replace("www.", "")
    return host.split(".")[0].replace("-", " ").title() if host else fallback


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    path = re.sub(r"/+$", "", unquote(parsed.path or ""))
    # Collapse common language prefixes so GLP Bio /jp /kr /de etc. do not appear as separate products.
    parts = [p for p in path.split("/") if p]
    if parts and parts[0].lower() in LANG_PREFIXES:
        parts = parts[1:]
    path = "/" + "/".join(parts) if parts else ""
    query_pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in SEARCH_QUERY_KEYS]
    return urlunparse((parsed.scheme or "https", host, path, "", urlencode(query_pairs), ""))


def supplier_key_from_url(url: str) -> str:
    adapter = adapter_for_url(url)
    if adapter:
        return adapter.name
    return supplier_name_for_url(url)


def direct_search_results(cas: str, tier: str | None = None):
    from services.search_service import SearchResult
    out = []
    adapters = sorted_adapters((tier,) if tier else None)
    for adapter in adapters:
        for template in adapter.search_url_templates:
            out.append(SearchResult(
                title=f"{adapter.name} CAS search",
                url=template.format(cas=cas),
                snippet=f"Adapter seed v16. Tier: {adapter.source_tier}. Expected behavior: {adapter.expected_behavior}. {adapter.notes}",
                source=f"adapter_seed_v16_{adapter.source_tier}",
                supplier_hint=adapter.name,
            ))
    return out

SLUG_PRODUCT_URL_TEMPLATES: dict[str, tuple[str, ...]] = {
    "MedChemExpress": ("https://www.medchemexpress.com/{slug}.html", "https://www.medchemexpress.com/cas/{cas}.html"),
    "Adooq": ("https://www.adooq.com/{slug}.html", "https://www.adooq.com/search?q={slug}"),
    "AdooQ Bioscience": ("https://www.adooqbioscience.com/{slug}.html",),
    "AbMole": ("https://www.abmole.com/products/{slug}.html", "https://www.abmole.com/search?q={slug}", "https://www.abmole.com/search?q={cas}"),
    "Ambeed": ("https://www.ambeed.com/products/{slug}.html", "https://www.ambeed.com/products/{slug}.html?country=US&currency=USD"),
    "ApexBio": ("https://www.apexbt.com/{slug}.html",),
    "GLP Bio": ("https://www.glpbio.com/{slug}.html",),
    "TargetMol": ("https://www.targetmol.com/compound/{slug}", "https://www.targetmol.com/compound/{slug}?utm_source=cas_sourcing"),
    "SelleckChem": ("https://www.selleckchem.com/products/{slug}.html",),
    "Biosynth": ("https://www.biosynth.com/search?query={slug}",),
    "BioCrick": ("https://www.biocrick.com/{slug}.html", "https://www.biocrick.com/search?keyword={slug}"),
    "ChemFaces": ("https://www.chemfaces.com/search/?q={slug}",),
    "CSNpharm": ("https://www.csnpharm.com/search?q={slug}",),
    "InvivoChem": ("https://www.invivochem.com/search?q={slug}", "https://www.invivochem.com/search.html?q={slug}"),
    "Biorbyt": ("https://www.biorbyt.com/search?q={slug}",),
}


def slugify_product_name(name: str | None) -> str | None:
    text = re.sub(r"\([^)]*standard[^)]*\)", " ", str(name or ""), flags=re.I)
    text = re.sub(r"\bCAS\s*(?:No\.?|Number|#)?\s*[:\-]?\s*\d{2,7}-\d{2}-\d\b", " ", text, flags=re.I)
    text = re.split(r"[|•–—]|\bCAS\b|\bCatalog\b|\bCat\.?\b", text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r"(?i)\b(?:price|stock|size|availability|search|results?|supplier|chemical\s*structure)\b", " ", text)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    if not text or len(text) < 3 or text in {"untitled", "product", "search", "results"}:
        return None
    return text[:80]


def product_name_candidates_from_title(title: str | None) -> list[str]:
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    if not text:
        return []
    parts = []
    first = re.split(r"[|•–—]", text, maxsplit=1)[0].strip()
    if first:
        parts.append(first)
    for m in re.finditer(r"\(([^()]{3,60})\)", text):
        val = m.group(1).strip()
        if not re.search(r"(?i)(standard|solution|cas|catalog|price)", val):
            parts.append(val)
    clean=[]
    for part in parts:
        part = re.sub(r"(?i)\b(?:CAS\s*(?:No\.?|Number)?|Catalog\s*No\.?|Cat\.?\s*No\.?).*", "", part).strip(" -:;,")
        if 3 <= len(part) <= 80 and not re.fullmatch(r"\d{2,7}-\d{2}-\d", part):
            clean.append(part)
    return list(dict.fromkeys(clean))


def supplier_product_url_candidates(supplier: str, product_names: list[str], cas: str | None = None):
    from services.search_service import SearchResult
    templates = SLUG_PRODUCT_URL_TEMPLATES.get(supplier, ())
    out = []
    seen = set()
    for name in product_names:
        slug = slugify_product_name(name)
        if not slug:
            continue
        for template in templates:
            url = template.format(slug=quote(slug), cas=cas or "")
            canon = canonicalize_url(url)
            if canon in seen:
                continue
            seen.add(canon)
            out.append(SearchResult(
                title=f"{supplier} product-name probe: {name}",
                url=url,
                snippet=f"v16 product-name probe generated from CAS-confirmed supplier title/name: {name}",
                source="v16_product_name_probe",
                supplier_hint=supplier,
            ))
    return out


def _catalog_token_is_plausible(token: str) -> bool:
    clean = token.strip().strip(".,;:)#/")
    low = clean.lower()
    if low in BAD_CATALOG_TOKENS or len(clean) < 4 or len(clean) > 60:
        return False
    if re.fullmatch(r"\d{2,7}-\d{2}-\d", clean):
        return False
    if re.search(r"(?i)(search|result|login|register|cart|checkout|shipping|happy|customer|html)$", clean):
        return False
    # Avoid accepting normal words from page text. Catalog/SKU values usually contain digits and letters/separators.
    if not re.search(r"\d", clean):
        return False
    if not (re.search(r"[A-Za-z]", clean) or re.search(r"[-_/]", clean)):
        return False
    return True


def extract_catalog_number(*texts: str) -> str | None:
    hay = " | ".join(t for t in texts if t)
    for pattern in CATALOG_PATTERNS:
        for m in pattern.finditer(hay):
            token = m.group(1).strip().strip(".,;:)")
            if _catalog_token_is_plausible(token):
                return token[:60]
    return None


def extract_snippet_price(snippet: str) -> float | None:
    m = PRICE_RE.search(snippet or "")
    if not m:
        return None
    try:
        val = float((m.group(1) or m.group(2)).replace(",", ""))
        # Guard obvious junk values like free samples or pagination counts masquerading as prices.
        return val if val > 0.01 else None
    except Exception:
        return None


def classify_price_visibility(listed_price: float | None, text: str = "", snippet_price: float | None = None, extraction_status: str = "success") -> str:
    hay = text or ""
    if extraction_status.startswith("failed"):
        return PRICE_FAILED
    if listed_price is not None:
        return PRICE_PUBLIC
    if snippet_price is not None:
        return PRICE_SNIPPET
    if LOGIN_RE.search(hay):
        return PRICE_LOGIN
    if QUOTE_RE.search(hay):
        return PRICE_QUOTE
    return PRICE_HIDDEN


def best_action_for_status(price_visibility_status: str) -> str:
    if price_visibility_status == PRICE_PUBLIC:
        return "Use as catalog price evidence"
    if price_visibility_status == PRICE_SNIPPET:
        return "Open source and verify snippet price"
    if price_visibility_status == PRICE_LOGIN:
        return "Login/check account price or RFQ"
    if price_visibility_status == PRICE_QUOTE:
        return "Send RFQ"
    if price_visibility_status == PRICE_FAILED:
        return "Open source manually"
    return "Check source / RFQ"
