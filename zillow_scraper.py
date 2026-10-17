"""Scrape public Zillow listings and property pages with Python. No login, no API key."""
import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

from curl_cffi import requests

BASE = "https://www.zillow.com"
# Zillow only runs queries it already knows. This file holds one such query (the one the
# property page sends for its history); when `history` fails, re-capture it from a browser.
QUERY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zillow_history_query.json")
PAGE_SIZE = 41  # Zillow's own page size
MAX_PAGES = 20  # Zillow stops paging after 20 pages
ATTEMPTS = 3
DENIED = ("Access to this page has been denied", "px-captcha")
STATUS_PATH = {"sale": "", "sold": "sold/", "rent": "rentals/"}
FACT_KEYS = (
    "yearBuilt", "stories", "heating", "cooling", "appliances", "basement", "flooring", "roofType",
    "architecturalStyle", "constructionMaterials", "parkingCapacity", "garageParkingCapacity",
    "hasGarage", "hasPrivatePool", "fireplaces", "laundryFeatures", "view", "waterfrontFeatures",
)
CSV_COLUMNS = [
    "zpid", "url", "status", "home_type", "address", "city", "state", "zip", "price", "price_max", "beds", "baths",
    "sqft", "zestimate", "rent_zestimate", "sold_date", "days_on_zillow", "building_name", "broker",
    "latitude", "longitude", "image_url",
]


class ScrapeError(Exception):
    pass


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat() if isinstance(ms, (int, float)) and ms > 0 else None


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def drop_empty(d):
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def zpid_from(value):
    """Accept a zpid or any Zillow homedetails link that contains one."""
    value = value.strip()
    m = re.search(r"(\d{4,12})_zpid", value) or re.fullmatch(r"(\d{4,12})", value)
    if not m:
        if "/apartments/" in value:
            raise ScrapeError("Apartment building pages are not supported. Pass a home's zpid or its /homedetails/ link.")
        raise ScrapeError(f"Not a zpid or a Zillow homedetails link: {value}. Find zpids with the search command.")
    return m.group(1)


def region_slug(value):
    """'Seattle, WA' -> 'seattle-wa'. A zip code, a Zillow link or a ready slug also work."""
    value = value.strip()
    if "zillow.com/" in value:
        parts = [p for p in value.split("zillow.com/", 1)[1].split("?")[0].split("/") if p]
        parts = [p for p in parts if p not in ("homes", "sold", "rentals") and not re.fullmatch(r"\d+_p", p)]
        value = parts[0].replace("_rb", "") if parts else ""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ScrapeError("Pass a place, such as 'Seattle, WA', 'austin-tx' or a zip code like 98101.")
    return slug


class Zillow:
    def __init__(self, proxy=None):
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    def _send(self, method, url, **kwargs):
        """One request. Every try is a new browser identity: Zillow denies one that has been seen before."""
        for attempt in range(1, ATTEMPTS + 1):
            try:
                # A fresh session, no cookies and no referer on purpose. Reusing them gets the request denied.
                with requests.Session(impersonate="chrome", proxies=self.proxies) as http:
                    resp = http.request(method, url, timeout=60, **kwargs)
            except requests.RequestsError as exc:
                raise ScrapeError(f"Network error: {exc}") from exc
            if resp.status_code == 404:
                raise ScrapeError("Not found. Check the zpid or the place.")
            if resp.status_code == 429:
                raise ScrapeError("Zillow is rate-limiting this IP (HTTP 429). Wait a few minutes, or use --proxy.")
            if resp.status_code == 403 or any(m in resp.text for m in DENIED):
                if attempt < ATTEMPTS:
                    time.sleep(1)
                    continue
                raise ScrapeError(
                    "Zillow blocked this request (HTTP 403). Datacenter and cloud IPs are blocked: "
                    "try a home connection or --proxy with a residential proxy."
                )
            if resp.status_code != 200:
                raise ScrapeError(f"Unexpected HTTP {resp.status_code} from Zillow.")
            return resp
        raise ScrapeError("Zillow did not answer.")

    def _page_props(self, path):
        html = self._send("GET", BASE + path).text
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            raise ScrapeError("Zillow sent a page without data. Try again, or use a home connection or --proxy.")
        return json.loads(m.group(1))["props"]["pageProps"]

    # --- property --------------------------------------------------------

    def property(self, zpid, history=True):
        props = self._page_props(f"/homedetails/{zpid}_zpid/")
        # The property sits in a JSON string whose key is a query signature that changes per page.
        cache = (props.get("componentProps") or {}).get("gdpClientCache")
        cache = json.loads(cache) if isinstance(cache, str) else cache or {}
        node = next((e["property"] for e in cache.values() if isinstance(e, dict) and e.get("property")), None)
        if not node:
            raise ScrapeError(f"Zillow has no property page for {zpid}.")
        data = clean_property(node)
        if history:
            try:
                extra = self.history(zpid)
            except ScrapeError as exc:
                print(f"Warning: no price or tax history ({exc})", file=sys.stderr)
            else:
                data.update({k: extra[k] for k in ("price_history", "tax_history", "schools")})
                # Some pages leave these two out; the history has them.
                sold = next((e["date"] for e in extra["price_history"] if e["event"] == "Sold"), None)
                data["last_sold_date"] = data["last_sold_date"] or sold
                if data["tax_annual"] is None and extra["tax_history"]:
                    data["tax_annual"] = extra["tax_history"][0]["tax_paid"]
        return data

    def history(self, zpid):
        """Price history, tax history, schools and nearby homes, from the query the property page sends."""
        try:
            with open(QUERY_FILE, encoding="utf-8") as f:
                query = json.load(f)
        except (OSError, ValueError):
            raise ScrapeError(f"Cannot read {os.path.basename(QUERY_FILE)}. Keep it next to the script.")
        variables = dict(query["variables"], zpid=int(zpid))
        variables["contactFormRenderParameter"] = dict(variables["contactFormRenderParameter"], zpid=int(zpid))
        body = json.dumps({"operationName": query["operationName"], "variables": variables, "query": query["query"]})
        resp = self._send("POST", f"{BASE}/graphql/?zpid={zpid}&operationName={query['operationName']}", data=body, headers={
            "content-type": "application/json", "accept": "*/*", "origin": BASE, "referer": f"{BASE}/homedetails/{zpid}_zpid/",
        })
        if "persisted query safelist" in resp.text:
            raise ScrapeError("Zillow no longer accepts the saved history query. Re-capture it from a browser.")
        node = (resp.json().get("data") or {}).get("property")
        if not node or not node.get("zpid"):
            raise ScrapeError("Not found. Check the zpid.")
        return clean_history(node)

    # --- search ----------------------------------------------------------

    def search(self, place, status="sale", limit=20):
        slug = region_slug(place)
        rows, seen = [], set()
        for page in range(1, MAX_PAGES + 1):
            path = f"/{slug}/{STATUS_PATH[status]}" + (f"{page}_p/" if page > 1 else "")
            state = self._page_props(path).get("searchPageState") or {}
            cat = state.get("cat1") or {}
            found = (cat.get("searchResults") or {}).get("listResults") or []
            for row in found:
                item = clean_result(row)
                if item["url"] not in seen:
                    seen.add(item["url"])
                    rows.append(item)
            total_pages = (cat.get("searchList") or {}).get("totalPages") or 1
            if len(rows) >= limit or page >= total_pages or not found:
                break
            time.sleep(1)
        return rows[:limit]


def clean_property(p):
    facts = p.get("resoFacts") or {}
    attr = p.get("attributionInfo") or {}
    addr = p.get("address") or {}
    lot = p.get("lotAreaValue")
    if lot and "acre" in (p.get("lotAreaUnits") or "").lower():
        lot = lot * 43560  # square feet, whichever unit Zillow used
    photos = []
    for photo in p.get("originalPhotos") or p.get("photos") or p.get("responsivePhotos") or []:
        sizes = (photo.get("mixedSources") or {}).get("jpeg") or []
        if sizes:
            photos.append(max(sizes, key=lambda s: s.get("width") or 0)["url"])
    return {
        "zpid": str(p["zpid"]),
        "url": BASE + p["hdpUrl"] if p.get("hdpUrl") else f"{BASE}/homedetails/{p['zpid']}_zpid/",
        "status": p.get("homeStatus"),
        "home_type": p.get("homeType"),
        "address": {"street": addr.get("streetAddress") or p.get("streetAddress"), "city": addr.get("city") or p.get("city"),
                    "state": addr.get("state") or p.get("state"), "zip": addr.get("zipcode") or p.get("zipcode")},
        "price": p.get("price"),
        "currency": p.get("currency"),
        "zestimate": p.get("zestimate"),
        "rent_zestimate": p.get("rentZestimate"),
        "last_sold_price": p.get("lastSoldPrice"),
        "last_sold_date": p.get("dateSoldString") or None,
        "price_change": p.get("priceChange"),
        "price_change_at": iso(p.get("priceChangeDate")),
        "beds": p.get("bedrooms"),
        "baths": p.get("bathrooms"),
        "sqft": p.get("livingArea"),
        "lot_sqft": round(lot) if lot else None,
        "year_built": facts.get("yearBuilt"),
        "hoa_fee_monthly": p.get("monthlyHoaFee"),
        "tax_annual": facts.get("taxAnnualAmount") or p.get("taxAnnualAmount"),
        "tax_rate_pct": p.get("propertyTaxRate"),
        "latitude": p.get("latitude"),
        "longitude": p.get("longitude"),
        "description": p.get("description"),
        "mls_id": p.get("mlsid"),
        "listed_at": iso(p.get("datePosted")),
        "days_on_zillow": p.get("daysOnZillow"),
        "page_views": p.get("pageViewCount"),
        "favorites": p.get("favoriteCount"),
        "listing_agent": attr.get("agentName"),
        "broker": attr.get("brokerName") or p.get("brokerageName"),
        "mls_name": attr.get("mlsName"),
        "facts": drop_empty({snake(k): facts.get(k) for k in FACT_KEYS}),
        "photo_count": p.get("photoCount") or len(photos),
        "photos": photos,
        "price_history": None,  # filled by history()
        "tax_history": None,
        "schools": None,
    }


def clean_history(p):
    return {
        "zpid": str(p["zpid"]),
        "price_history": [
            {"date": r.get("date"), "event": r.get("event"), "price": r.get("price"), "price_per_sqft": r.get("pricePerSquareFoot"),
             "source": r.get("source"), "is_rental": r.get("postingIsRental")}
            for r in p.get("priceHistory") or []
        ],
        "tax_history": [
            {"year": datetime.fromtimestamp(r["time"] / 1000, timezone.utc).year, "tax_paid": round(r["taxPaid"], 2) if r.get("taxPaid") is not None else None,
             "assessed_value": r.get("value")}
            for r in p.get("taxHistory") or [] if r.get("time")
        ],
        "schools": [
            {"name": r.get("name"), "rating": r.get("rating"), "grades": r.get("grades"), "distance_miles": r.get("distance"), "url": r.get("link")}
            for r in p.get("schools") or []
        ],
        "nearby_homes": [
            {"zpid": str(h["zpid"]), "url": BASE + h["hdpUrl"] if h.get("hdpUrl") else None, "status": h.get("homeStatus"),
             "address": (h.get("address") or {}).get("streetAddress"), "city": (h.get("address") or {}).get("city"),
             "price": h.get("price"), "beds": h.get("bedrooms"), "baths": h.get("bathrooms"), "sqft": h.get("livingArea")}
            for h in p.get("nearbyHomes") or []
        ],
    }


def clean_result(r):
    info = (r.get("hdpData") or {}).get("homeInfo") or {}
    loc = r.get("latLong") or {}
    url = r.get("detailUrl") or ""
    building = bool(r.get("isBuilding"))  # apartment buildings: no zpid, a rent range and a list of unit types
    img = r.get("imgSrc") or ""
    price = r.get("unformattedPrice") or info.get("price") or r.get("minBaseRent")
    return {
        "zpid": None if building else str(r["zpid"]),
        "url": url if url.startswith("http") else BASE + url,
        "status": r.get("statusType"),
        "home_type": info.get("homeType") or ("APARTMENT_BUILDING" if building else None),
        "address": r.get("addressStreet"),
        "city": r.get("addressCity"),
        "state": r.get("addressState"),
        "zip": r.get("addressZipcode"),
        "price": price,
        "price_max": r.get("maxBaseRent"),
        "beds": r.get("beds"),
        "baths": r.get("baths"),
        "sqft": r.get("area"),
        "zestimate": r.get("zestimate") or info.get("zestimate"),
        "rent_zestimate": info.get("rentZestimate"),
        "sold_date": iso(info.get("dateSold")),
        "days_on_zillow": info["daysOnZillow"] if info.get("daysOnZillow", -1) >= 0 else None,
        "building_name": r.get("buildingName"),
        "units": [{"beds": to_int(u.get("beds")), "rent_from": to_int(re.sub(r"\D", "", u.get("price") or ""))}
                  for u in r.get("units") or []] or None,
        "broker": r.get("brokerName"),
        "latitude": loc.get("latitude"),
        "longitude": loc.get("longitude"),
        "image_url": img if img.startswith("https://photos.zillowstatic.com/") else None,  # others are map tiles
    }


def write_csv(rows, stream):
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY"), help="proxy URL, e.g. http://user:pass@host:port")
    common.add_argument("-o", "--output", help="write the result to this file")

    parser = argparse.ArgumentParser(description="Scrape public Zillow listings and property pages. No login, no API key.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("property", parents=[common], help="one property: facts, Zestimate, price and tax history")
    p.add_argument("property", help="zpid or a Zillow /homedetails/ link")
    p.add_argument("--no-history", action="store_true", help="skip the second request for price history, tax history and schools")
    p = sub.add_parser("search", parents=[common], help="listings in a city, zip code or neighbourhood")
    p.add_argument("place", help="e.g. 'Seattle, WA', austin-tx, 98101")
    p.add_argument("--status", choices=list(STATUS_PATH), default="sale", help="sale (default), sold or rent")
    p.add_argument("--limit", type=int, default=20, help=f"how many listings to return (default 20, {PAGE_SIZE} per page, up to {MAX_PAGES} pages)")
    p.add_argument("--csv", action="store_true", help="write CSV instead of JSON")
    p = sub.add_parser("history", parents=[common], help="price history, tax history, schools and nearby homes of one property")
    p.add_argument("property", help="zpid or a Zillow /homedetails/ link")
    args = parser.parse_args()

    try:
        zillow = Zillow(args.proxy)
        if args.command == "search":
            if not 1 <= args.limit <= PAGE_SIZE * MAX_PAGES:
                raise ScrapeError(f"--limit must be between 1 and {PAGE_SIZE * MAX_PAGES}.")
            data = zillow.search(args.place, args.status, args.limit)
        elif args.command == "history":
            data = zillow.history(zpid_from(args.property))
        else:
            data = zillow.property(zpid_from(args.property), history=not args.no_history)
    except ScrapeError as exc:
        sys.exit(f"Error: {exc}")

    if args.command == "search" and not data:
        print("No results. Check the place name, or try --status sold.", file=sys.stderr)
    out = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    if getattr(args, "csv", False):
        write_csv(data, out)
    else:
        out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    if args.output:
        out.close()
        print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
