# Baulogic Planning Monitor

> Automated weekly lead generation for premium and ultra-prime London residential developments. Built by a sole marketer to do the work of an outbound research team.

I'm the only marketer at [Baulogic](https://baulogic.com), a UK hardwired connected home technology company. Our product is installed during the first-fix stage of new builds — which means our addressable market in any given week is the small set of London developers, housebuilders, and self-builders who've just been granted (or are applying for) planning permission for a new residential build in a postcode where our price point makes sense.

That information is public. Every London borough publishes its planning applications to the Greater London Authority's [Planning London Datahub](https://www.london.gov.uk/programmes-strategies/planning/digital-planning/planning-london-datahub). The problem is volume: ~120 applications per week across just Westminster and Kensington & Chelsea, the vast majority of which are roof extensions, tree works, and shopfront alterations that have nothing to do with us.

So I built this. It runs every Monday morning, reads the API, filters out everything that isn't a new residential build, scores what's left by postcode tier and value signals, and emails me a ranked digest.

## What it does

Every Monday at 08:00 UK time, the system:

1. Queries the PLD API for all applications validated in the last 7 days across Westminster and Kensington & Chelsea
2. Filters to new-build residential only — rejects extensions, refurbishments, conversions, alterations, tree works, signage, telecoms, anything Baulogic isn't a fit for
3. Scores each qualifying application out of 100 using postcode tier (ultra-prime → prime → other), value-signal keywords (basement, mews, listed, swimming pool, etc.), and recency
4. Sends a ranked HTML digest to my inbox via [Resend](https://resend.com)
5. Commits a markdown copy of the digest to `/digests/` in this repo as an audit trail

## Stack

- **Python 3.11** — pipeline logic
- **GitHub Actions** — scheduled runs, free compute, secret management
- **Planning London Datahub API** — Elasticsearch v7.9, public read access
- **Resend** — transactional email
- **No database** — markdown digests serve as the audit trail; if I need to query historic leads I read them from the repo

## Results from the first run

117 applications fetched, 2 qualified.

The top-scored lead was application **26/03056/FULL** — a £100M+ mixed-use redevelopment at 8–10 Broadway, Westminster: demolition of existing buildings and erection of six residential buildings, 14 to 20 storeys high, with three basement levels. Exactly the kind of project Baulogic exists to serve.

The system found this in 90 seconds, from a public dataset, with no human effort beyond setting up the rules. The same week, a competitor's sales team paid £40k+ for the same intelligence from a property data platform.

## What this taught me

Three things I'd carry into any future automation project:

**1. Filtering is binary; scoring is ranked. Don't conflate them.** My first instinct was to threshold the score and drop low-rated leads. That would have hidden them. Better to apply hard rules in the filter (is this a new build, yes or no?) and use scoring purely for ordering. The lowest-scored lead in the email is still a lead — it just goes to the bottom.

**2. The expensive part is the schema, not the code.** Writing the Python took an hour. Working out what "qualifying lead" actually means for Baulogic — which application types, which keywords are signals, which are disqualifiers — took several conversations with myself and a careful look at real PLD data. The keyword lists in `src/filter.py` are the actual product.

**3. Public sector APIs are often weirder than they look.** PLD is Elasticsearch v7.9 behind a custom header, returns UK date strings, has data entry quirks (one application had `valid_date: "05/03/3036"`). Robust ingestion code pays for itself the first time the data does something unexpected.

## Architecture
