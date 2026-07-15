# Actor index

> Vendored from Apify's official `apify-ultimate-scraper` skill (github.com/apify/agent-skills).
> Use with `scripts/run_actor.py --actor <ID> --input '<JSON>'`. Fetch any actor's input schema
> before running: `GET https://api.apify.com/v2/acts/{a~b}` or `apify actors info "ID" --input --json`
> if the Apify CLI is installed. Tiers: `apify` = Apify-maintained (prefer), `community` = fills gaps.
> Check pricing/deprecation first with `run_actor.py --actor <ID> --info-only` (see gotchas.md).

## Google Maps

| Actor | Tier | Best for |
|-------|------|----------|
| compass/crawler-google-places | apify | business listings (default for this skill) |
| compass/google-maps-extractor | apify | detailed business data, faster/cheaper basics |
| compass/Google-Maps-Reviews-Scraper | apify | reviews, ratings |
| compass/enrich-google-maps-dataset-with-contacts | apify | email enrichment of an existing gmaps dataset (pass `datasetId`) |
| compass/contact-details-scraper-standby | apify | quick contact extract, <1s standby latency |
| lukaskrivka/google-maps-with-contact-details | community | listings + contacts |
| curious_coder/google-maps-reviews-scraper | community | cheap review scraping |

## LinkedIn (all PPE — estimate cost first)

| Actor | Tier | Best for |
|-------|------|----------|
| harvestapi/linkedin-profile-search | community | find profiles (cheaper: ~$0.001–0.01/result) |
| harvestapi/linkedin-profile-scraper | community | profile with email (`includeEmail: true`) |
| harvestapi/linkedin-company | community | company details, headcount, industry |
| harvestapi/linkedin-company-employees | community | employee lists |
| harvestapi/linkedin-job-search | community | job listings |
| harvestapi/linkedin-post-search | community | post search |
| harvestapi/linkedin-post-comments | community | post comments (warm-lead mining) |
| harvestapi/linkedin-profile-search-by-name | community | find by name |
| apimaestro/linkedin-companies-search-scraper | community | company search (pricier) |
| apimaestro/linkedin-company-detail | community | company deep data |
| apimaestro/linkedin-profile-full-sections-scraper | community | full profile data |
| dev_fusion/linkedin-profile-scraper | community | mass scraping + email, mid-range |

## Google Search and Trends

| Actor | Tier | Best for |
|-------|------|----------|
| apify/google-search-scraper | apify | SERP, ads, AI overviews (SERP-based lead discovery) |
| apify/google-trends-scraper | apify | trend data |
| tri_angle/bing-search-scraper | apify | Bing SERP data |

## Enrichment and contacts

| Actor | Tier | Best for |
|-------|------|----------|
| apify/social-media-leads-analyzer | apify | emails from websites |
| vdrmota/contact-info-scraper | community | contact extraction from URL lists (cost-effective batch) |
| code_crafter/leads-finder | community | B2B leads |
| apify/website-content-crawler | apify | clean site text for AI qualification/icebreakers |

## Instagram

| Actor | Tier | Best for |
|-------|------|----------|
| apify/instagram-scraper | apify | all Instagram data |
| apify/instagram-profile-scraper | apify | profiles, followers, bio |
| apify/instagram-post-scraper | apify | posts, engagement metrics |
| apify/instagram-comment-scraper | apify | post and reel comments |
| apify/instagram-hashtag-scraper | apify | posts by hashtag |
| apify/instagram-api-scraper | apify | API-based, no login |
| apify/instagram-search-scraper | apify | search users, places |

## Facebook

| Actor | Tier | Best for |
|-------|------|----------|
| apify/facebook-posts-scraper | apify | posts, videos, engagement |
| apify/facebook-search-scraper | apify | page search |
| apify/facebook-page-contact-information | apify | page contact info |
| apify/facebook-reviews-scraper | apify | page reviews |
| apify/facebook-ads-scraper | apify | ad library, creatives |
| apify/facebook-groups-scraper | apify | public group content |
| apify/facebook-events-scraper | apify | events, attendees |

## TikTok

| Actor | Tier | Best for |
|-------|------|----------|
| clockworks/tiktok-scraper | apify | all TikTok data |
| clockworks/tiktok-profile-scraper | apify | profiles, videos |
| clockworks/tiktok-user-search-scraper | apify | user search |

## YouTube

| Actor | Tier | Best for |
|-------|------|----------|
| streamers/youtube-scraper | apify | videos, metrics |
| streamers/youtube-channel-scraper | apify | channel info |
| streamers/youtube-comments-scraper | apify | video comments |

## X/Twitter

| Actor | Tier | Best for |
|-------|------|----------|
| apidojo/tweet-scraper | community | tweet search |
| apidojo/twitter-user-scraper | community | user profiles |
| apidojo/twitter-profile-scraper | community | profiles + recent tweets |

## Reviews (cross-platform)

| Actor | Tier | Best for |
|-------|------|----------|
| tri_angle/yelp-scraper | apify | Yelp business data |
| tri_angle/yelp-review-scraper | apify | Yelp reviews |
| tri_angle/hotel-review-aggregator | apify | 7-platform hotel reviews |
| tri_angle/restaurant-review-aggregator | apify | 6-platform restaurant reviews |
| tri_angle/social-media-sentiment-analysis-tool | apify | sentiment analysis |

## Real estate and hospitality

| Actor | Tier | Best for |
|-------|------|----------|
| tri_angle/airbnb-scraper | apify | Airbnb listings |
| tri_angle/redfin-search | apify | Redfin property search |
| tri_angle/real-estate-aggregator | apify | multi-source listings |
| tri_angle/fast-zoopla-properties-scraper | apify | UK properties |

## SEO tools (highest per-result costs — batch carefully)

| Actor | Tier | Best for |
|-------|------|----------|
| radeance/similarweb-scraper | community | traffic, rankings |
| radeance/ahrefs-scraper | community | backlinks, keywords |
| radeance/semrush-scraper | community | domain authority |
| radeance/ubersuggest-scraper | community | keyword suggestions |

## Content and web crawling

| Actor | Tier | Best for |
|-------|------|----------|
| apify/website-content-crawler | apify | clean text for AI |
| apify/web-scraper | apify | general web scraping |
| apify/cheerio-scraper | apify | fast HTML parsing |
| apify/playwright-scraper | apify | JS-heavy sites |
| apify/camoufox-scraper | apify | anti-bot sites |
| apify/sitemap-extractor | apify | sitemap URLs |

## Other platforms

| Actor | Tier | Best for |
|-------|------|----------|
| trudax/reddit-scraper-lite | community | Reddit posts (intent-based lead mining) |
| tri_angle/telegram-scraper | apify | Telegram messages |
| tri_angle/social-media-finder | apify | cross-platform search |
| tri_angle/website-changes-detector | apify | website monitoring |
| janbuchar/github-contributors-scraper | community | GitHub contributors |
| powerai/northdata-search-scraper | community | northdata.com UI scrape (only if no official ND API key) |

If nothing here matches, search the store: `GET https://api.apify.com/v2/store?search=KEYWORDS&limit=10`
(or `apify actors search "KEYWORDS" --json`). Rank by `stats.totalUsers30Days`; prefer `apify`-tier.
