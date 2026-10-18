# Zillow Scraper (Python)

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Last verified](https://img.shields.io/badge/last%20verified-2026--10--17-brightgreen.svg)](#how-we-keep-it-working)

Scrape public Zillow listings, property details, Zestimates and price and tax history with Python, as JSON or CSV. No login, no API key, one script.

> **Need this at scale?** The script is for learning and small jobs. The [ToolzerHub Zillow API](https://toolzerhub.com/apis/zillow?utm_source=github&utm_medium=readme&utm_campaign=zillow-scraper) returns the same data and more (listing agent and broker details, full property facts, bulk listing lists for rentals, pending, auction and new construction) as JSON from any server, with no blocks to handle. 100 free credits a month, no card needed.

## What it scrapes

| Command | What you get |
|---|---|
| `search <place>` | Listings in a city, zip code or neighbourhood: `--status sale` (default), `sold` or `rent`, paged with `--limit` |
| `property <zpid or URL>` | One home: price, beds, baths, size, Zestimate, rent estimate, photos, plus price history, tax history and schools |
| `history <zpid or URL>` | Price history, tax history, nearby schools and nearby homes of one property (one request) |

Every `search` row has a `zpid`, the id that `property` and `history` take.

## Quick start

```bash
git clone https://github.com/toolzerhub/zillow-scraper.git
cd zillow-scraper
pip install -r requirements.txt
python zillow_scraper.py search "Seattle, WA" --limit 10
```

More examples:

```bash
python zillow_scraper.py search austin-tx --status sold --limit 50 -o austin-sold.json
python zillow_scraper.py search 98101 --status rent --limit 20
python zillow_scraper.py search "Miami, FL" --limit 100 --csv -o miami.csv
python zillow_scraper.py property 48795376 -o home.json
python zillow_scraper.py property https://www.zillow.com/homedetails/4148-52nd-Ave-SW-Seattle-WA-98116/48795376_zpid/
python zillow_scraper.py history 48795376 -o history.json
```

Every command takes `-o file` to save the result and `--proxy URL` to route through a proxy. The script also reads `HTTPS_PROXY`.

| Flag | Meaning |
|---|---|
| `search <place>` | A city and state (`"Seattle, WA"`), a slug from a Zillow link (`austin-tx`), a zip code, a neighbourhood, or a full Zillow search link |
| `--status sale\|sold\|rent` | `search` only. Default `sale` |
| `--limit 20` | `search` only. How many listings to return. Default 20. Zillow serves 41 per page, up to 20 pages |
| `--csv` | `search` only. Write CSV instead of JSON |
| `--no-history` | `property` only. Skip the second request for price history, tax history and schools |

## Example output

`python zillow_scraper.py property 48795376` (description, photos and history cut short)

```json
{
  "zpid": "48795376",
  "url": "https://www.zillow.com/homedetails/4148-52nd-Ave-SW-Seattle-WA-98116/48795376_zpid/",
  "status": "FOR_SALE",
  "home_type": "SINGLE_FAMILY",
  "address": {
    "street": "4148 52nd Avenue SW",
    "city": "Seattle",
    "state": "WA",
    "zip": "98116"
  },
  "price": 1025000,
  "currency": "USD",
  "zestimate": 1006300,
  "rent_zestimate": 4700,
  "last_sold_price": 651000,
  "last_sold_date": "2016-10-24",
  "beds": 3,
  "baths": 2,
  "sqft": 1800,
  "lot_sqft": 5750,
  "year_built": 1953,
  "tax_annual": 10584.64,
  "latitude": 47.565243,
  "longitude": -122.39846,
  "description": "Welcome to this light-filled MCM gem in the heart of Genesee, just one block from ...",
  "mls_id": "2594350",
  "broker": "Every Door Real Estate",
  "mls_name": "NWMLS as distributed by MLS GRID",
  "facts": { "year_built": 1953, "parking_capacity": 3, "has_garage": true },
  "photo_count": 40,
  "photos": ["https://photos.zillowstatic.com/fp/08bac070dd198d8751a216727b18e1d2-cc_ft_1536.jpg"],
  "price_history": [
    { "date": "2026-10-15", "event": "Listed for sale", "price": 1025000, "price_per_sqft": 569, "source": "NWMLS as distributed by MLS GRID", "is_rental": false },
    { "date": "2016-10-24", "event": "Sold", "price": 651000, "price_per_sqft": 362, "source": "NWMLS as distributed by MLS GRID", "is_rental": false }
  ],
  "tax_history": [
    { "year": 2025, "tax_paid": 10584.64, "assessed_value": 985000 },
    { "year": 2024, "tax_paid": 9114.19, "assessed_value": 906000 }
  ],
  "schools": [
    { "name": "Genesee Hill Elementary School", "rating": 9, "grades": "K-5", "distance_miles": 0.1, "url": "https://www.greatschools.org/washington/seattle/1608-Genesee-Hill-Elementary-School/" }
  ]
}
```

`python zillow_scraper.py search "Seattle, WA" --limit 10` (one listing shown)

```json
{
  "zpid": "48795376",
  "url": "https://www.zillow.com/homedetails/4148-52nd-Ave-SW-Seattle-WA-98116/48795376_zpid/",
  "status": "FOR_SALE",
  "home_type": "SINGLE_FAMILY",
  "address": "4148 52nd Avenue SW",
  "city": "Seattle",
  "state": "WA",
  "zip": "98116",
  "price": 1025000,
  "beds": 3,
  "baths": 2,
  "sqft": 1800,
  "zestimate": 1006300,
  "rent_zestimate": 4700,
  "latitude": 47.565243,
  "longitude": -122.39846,
  "image_url": "https://photos.zillowstatic.com/fp/08bac070dd198d8751a216727b18e1d2-p_e.jpg"
}
```

Full outputs for every command, plus a CSV, a sold search and a rental search, are in [examples/](examples).

## Fields

### search

| Field | Description |
|---|---|
| zpid | Zillow's property id. `null` for rental buildings |
| url | Link to the listing |
| status | `FOR_SALE`, `SOLD`, `FOR_RENT`, `PENDING` and similar |
| home_type | `SINGLE_FAMILY`, `CONDO`, `TOWNHOUSE`, `MULTI_FAMILY`, `APARTMENT_BUILDING`, ... |
| address, city, state, zip | Where it is |
| price | Asking price, sold price for `--status sold`, monthly rent for `--status rent` (the lowest rent for a building) |
| price_max | Rental buildings only: the highest rent |
| beds, baths, sqft | Size. Empty for rental buildings |
| zestimate, rent_zestimate | Zillow's value and rent estimates, when it has them |
| sold_date | ISO 8601 UTC. Sold listings only |
| days_on_zillow | Days since listed, when Zillow says |
| building_name, units | Rental buildings only: the name, and the unit types with `beds` and `rent_from` |
| broker | Listing broker, when the result carries one |
| latitude, longitude, image_url | Location and the main photo |

### property

| Field | Description |
|---|---|
| zpid, url, status, home_type, address | Which home it is, and whether it is for sale, pending, sold and so on |
| price, currency | Current price |
| zestimate, rent_zestimate | Zillow's value and rent estimates, when it has them |
| last_sold_price, last_sold_date | Last sale |
| price_change, price_change_at | Last price cut or rise, with an ISO 8601 UTC time |
| beds, baths, sqft, lot_sqft, year_built | The home. `lot_sqft` is always in square feet |
| hoa_fee_monthly, tax_annual, tax_rate_pct | HOA fee and property tax. `tax_annual` falls back to the latest tax year in `tax_history` |
| latitude, longitude, description | Location and the listing text |
| mls_id, mls_name, broker, listing_agent | Listing source. Zillow leaves the agent and broker off some listings |
| listed_at, days_on_zillow, page_views, favorites | When it was listed (ISO 8601 UTC) and how much attention it gets. Not on every listing |
| facts | A few of Zillow's standard home facts (parking, heating, cooling, stories, ...), only those the listing has |
| photo_count, photos | Photo URLs, the largest size of each |
| price_history | `date`, `event`, `price`, `price_per_sqft`, `source`, `is_rental`. Newest first |
| tax_history | `year`, `tax_paid`, `assessed_value` |
| schools | `name`, `rating` (1 to 10), `grades`, `distance_miles`, `url` |

With `--no-history`, `price_history`, `tax_history` and `schools` are `null`.

### history

`zpid`, `price_history`, `tax_history` and `schools` as above, plus `nearby_homes`: `zpid`, `url`, `status`, `address`, `city`, `price`, `beds`, `baths`, `sqft` for homes nearby. For homes that are not listed, `price` is Zillow's own estimate. An empty list means Zillow has no such records for the home.

## How it works

1. `search` asks for the page Zillow shows a visitor, for example `zillow.com/seattle-wa/` (or `/sold/`, `/rentals/`, `/2_p/` for page 2), as Chrome would. [curl_cffi](https://github.com/lexiforest/curl_cffi) matches the browser's TLS fingerprint. Every request uses a new session with no cookies: Zillow denies a session it has seen before.
2. `property` asks for `zillow.com/homedetails/<zpid>_zpid/`. The page carries its data as JSON in a `__NEXT_DATA__` tag. The home sits inside a JSON string in that JSON. Search results sit in the same tag, 41 per page.
3. Price history, tax history, schools and nearby homes are not on the page. Zillow's site fetches them with one GraphQL call. Zillow only runs queries it already knows, so the script sends the exact query the site sends, saved in `zillow_history_query.json`, with the home's zpid.
4. Everything is cleaned into the fields above: ISO 8601 dates, numbers as numbers, no raw Zillow objects.

## Limits

- Public data only: what Zillow shows a visitor without an account.
- `search` returns at most 820 listings per place (20 pages of 41). Zillow reports a bigger total for busy places but stops paging at 20 pages. Search a zip code or neighbourhood to go deeper.
- `--status rent` returns apartment buildings with a rent range and unit types, and some single homes. Buildings have no `zpid`, and `property` does not read apartment building pages.
- Some states, such as Texas, do not publish sold prices, so `price` is `null` on those sold listings.
- Zillow does not fill every field on every listing. Zestimate, listing agent, page views and listing date are missing on some.
- No agent search and no mortgage rates. No price or bedroom filters yet: filter the JSON or CSV yourself.
- Zillow blocks datacenter and cloud IPs. From a datacenter, `property` pages are always denied (HTTP 403). `search` and `history` sometimes get through, then Zillow rate-limits the IP (HTTP 429). Run it from a home connection, or pass `--proxy` (a residential proxy works best).
- No retry framework, no concurrency. That is on purpose: the script stays short enough to read in one sitting. The one exception: a denied request is asked again up to 3 times, each time as a new session.
- It breaks when Zillow changes its pages. `history` also breaks when Zillow drops the saved query in `zillow_history_query.json`; `property --no-history` and `search` keep working.

## Scaling up

The script is for learning and small jobs. At scale you run into blocks, rate limits, changing page formats and proxy costs. The [ToolzerHub Zillow API](https://toolzerhub.com/apis/zillow?utm_source=github&utm_medium=readme&utm_campaign=zillow-scraper) handles all of that:

| | This script | ToolzerHub API |
|---|---|---|
| Data | Search (for sale, sold, rent), property details, price and tax history, schools, nearby homes, CSV | 4 endpoints: search, property, price and tax history, and bulk listing lists (for sale by agent or owner, pending, auction, new construction, sold, rent, off market). Listing agent and broker details, full property facts |
| Blocks and proxies | Your problem | Handled |
| When Zillow changes | Wait for a fix here | Fixed on our side |
| Cost | Free, plus your proxy | 100 free credits a month, then from $0.99 per 1,000 calls |

## How we keep it working

Every command is run against live Zillow pages before each update, and the "last verified" badge shows the last day they all passed. If something breaks, [open an issue](https://github.com/toolzerhub/zillow-scraper/issues).

Last run, 2026-10-17, 3 to 5 different inputs per command (US cities, zip codes, sold and rental searches, homes in 6 cities):

| Command | Residential proxy | Datacenter IP, no proxy |
|---|---|---|
| `search` (sale, sold, rent, CSV, 10 to 100 listings) | 10 of 10 passed, 1.5 to 7 s | Passed at first; HTTP 429 after a burst of about 15 requests |
| `property` (with history) | 8 of 8 passed, about 4 s | 0 of 5 passed: HTTP 403 every time |
| `history` | 7 of 7 passed, 2 to 3 s | Passed at first; HTTP 429 after a burst of about 15 requests |

## FAQ

**Is scraping Zillow legal?**
Scraping publicly available data is generally allowed in many places, but it depends on your country, what you collect and how you use it. Read the Legal section below.

**Why am I getting "blocked" or "rate-limiting"?**
Zillow blocks most cloud and datacenter IP addresses. Use a home connection or a residential proxy, and slow down.

**Can it get a home from its street address?**
No. Zillow's property pages are keyed by zpid. Run `search` with the zip code and match the address, or take the zpid from a Zillow link.

**Can it get bulk lists of pending, auction or new-construction homes?**
No. The [ToolzerHub API](https://toolzerhub.com/apis/zillow?utm_source=github&utm_medium=readme&utm_campaign=zillow-scraper) can.

## Related scrapers

- [instagram-scraper](https://github.com/toolzerhub/instagram-scraper): public Instagram profiles, posts, comments and search
- [tiktok-scraper](https://github.com/toolzerhub/tiktok-scraper): public TikTok profiles, videos, comments and hashtags
- [threads-scraper](https://github.com/toolzerhub/threads-scraper): public Threads profiles, posts, replies and search
- [reddit-scraper](https://github.com/toolzerhub/reddit-scraper): public subreddits, posts, comments, search and user posts
- [linkedin-scraper](https://github.com/toolzerhub/linkedin-scraper): public LinkedIn jobs, companies, profiles and posts
- [google-maps-scraper](https://github.com/toolzerhub/google-maps-scraper): public Google Maps places, details and reviews
- [facebook-ad-library-scraper](https://github.com/toolzerhub/facebook-ad-library-scraper): public Meta Ad Library ads by keyword or advertiser, with their videos and images

## Legal and responsible use

This project is for education and for collecting **publicly available** data. You are responsible for how you use it.

- **Public data only.** The script reads pages anyone can see without an account. Do not use it to get around logins, paywalls, CAPTCHAs or other access controls.
- **Terms and robots rules.** Zillow's terms of service may restrict automated access. Read them and decide for yourself; following them is your responsibility.
- **Personal data.** Listings can contain personal data, such as agent names and property addresses. Laws such as the GDPR (EU and UK) and the CCPA (California) may apply. Collect only what you need, have a lawful basis, keep it secure, delete it when you no longer need it, and respect people's requests to access or erase their data.
- **Copyright.** Listing text, photos and Zestimates belong to Zillow, the listing brokers and the photographers. Do not republish them without permission.
- **Be gentle.** Keep request rates low and do not disrupt the service.
- **No warranty.** The software is provided "as is" under the MIT License, without warranty of any kind. The authors are not liable for any claim or damage arising from its use.
- **Not affiliated.** This project is not affiliated with, endorsed by or sponsored by Zillow Group, Inc. Zillow and Zestimate are trademarks of Zillow, Inc.
- **Takedown requests.** If you own rights in something here and want it changed or removed, email contact@toolzerhub.com.

This section is not legal advice. If you are unsure, talk to a lawyer.

## License

[MIT](LICENSE) © ToolzerHub
