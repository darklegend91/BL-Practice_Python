# Guide

What this app is, how the pieces fit together, and how to run it.

## What it does

You answer a handful of multiple-choice questions and give a few numbers. It
tells you whether to run a downloadable language model on your own computer or
pay for a subscription, and shows its working.

It runs no model itself and calls no model API. The answer comes from ordinary
arithmetic over a catalog of hardware, models and plans.

## The flow

```
  sources table          you add URLs here
        |
        v
  POST /crawl            fetches each page with Crawl4AI
        |
        v
  pages table            the Markdown it got back, kept so you can look
        |
        v
  app/extract.py         reads fact blocks out of the Markdown
        |
        v
  hardware / models / plans     the catalog
        |
        v
  POST /recommend        engine compares options and answers
```

Four things are compared: the computer you already have, that computer plus a
new graphics card, a whole new machine, and a subscription. Local options are
tried with each model in the catalog, because whether it runs depends on both.

## Setting it up

You need Python 3.12 or newer and PostgreSQL.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create the database and a user for it:

```bash
createuser llmfit --createdb
createdb llmfit --owner llmfit
```

Point the app at it and create the tables:

```bash
export LLMFIT_DATABASE_URL="postgresql+psycopg://llmfit:llmfit@localhost:5432/llmfit"
.venv/bin/alembic upgrade head
```

Load the example sources and crawl them:

```bash
.venv/bin/python -m app.seed
.venv/bin/python -m app.crawler
```

Start it:

```bash
.venv/bin/uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs> to click through it, or use the endpoints
below.

## The endpoints

There is no login. There are no tokens or headers.

Every `POST` has a `GET` beside it that tells you what to send, so you can find
your way around without leaving the API.

| Endpoint | What it is for |
| --- | --- |
| `GET /` | What the project is, how to set it up, every endpoint explained |
| `GET /options` | Every choice you can make, and the number each one means |
| `POST /recommend` | Send your answers, get the recommendation |
| `GET /recommend` | What to send to `POST /recommend`, with an example to copy |
| `GET /catalog` | The hardware, models and plans the answer used |
| `GET /pages` | What the crawler fetched and how much of it it understood |
| `GET /sources` / `POST /sources` | The pages the crawler visits |
| `GET /sources/help` | What to send to `POST /sources` |
| `POST /crawl` | Fetch every source again now |
| `GET /crawl` | What `POST /crawl` does and what it returns |
| `GET /health` | Is the app up, is the database reachable |

If you are not sure where to begin, `curl localhost:8000/` prints the lot.

`GET /sources` already lists the registered sources, so the instructions for
adding one live at `GET /sources/help` rather than on the bare path.

The help is generated from the same Pydantic models the endpoints validate
against, and tests check that every field is documented and that the example
bodies are really accepted. It cannot drift from the code without a test
failing.

### Asking for a recommendation

Only `workloads` is required. Everything else has a default.

```bash
curl -X POST localhost:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{
    "workloads": ["coding"],
    "usage": "medium",
    "months": 24,
    "electricity_per_kwh": "0.32",
    "existing_computer": {
      "label": "my desk PC",
      "gpu_vram_gb": "16",
      "system_ram_gb": "32",
      "active_watts": "410",
      "idle_watts": "70"
    }
  }'
```

You get back:

- `status` - `recommended`, `only_uncertain_options`, or `nothing_fits`.
- `inputs_used` - the actual numbers your options turned into.
- `best` - the winner, with its month-by-month costs.
- `runners_up` - the rest, in order.
- `uncertain` - options with a fact missing, kept separate on purpose.
- `ruled_out` - everything that cannot work, each with the reason.
- `break_even` - when the winner became cheaper than the others.
- `cases` - the same comparison under low, base and high assumptions.
- `assumptions` - what it assumed, in words.

### Checking what it used

```bash
curl localhost:8000/catalog | python3 -m json.tool
curl localhost:8000/pages  | python3 -m json.tool
```

## Adding your own source

A page is readable if it contains fact blocks like this:

```
## hardware: gpu-16g
- name: SampleVendor Accelerator 16G
- role: gpu
- vram_gb: 16
- active_watts: 420
- idle_watts: 75
- price: 430.00 EUR
- region: DE
```

The heading is `## <kind>: <slug>`, where kind is `hardware`, `model` or
`plan`, and the slug identifies the row. Under it, `- key: value` lines set the
fields. Keys not listed below are ignored; fields not present stay unknown.

**hardware**: `name`, `role` (`gpu` or `system`), `vram_gb`, `ram_gb`,
`active_watts`, `idle_watts`, `price`, `region`, `setup_hours`.
`role` is required - without it we cannot tell a spare part from a whole
computer, and the block is skipped.

**model**: `name`, `params_b`, `quantization`, `weights_gb`, `max_context`,
`layers`, `kv_heads`, `head_dim`, `commercial_use`, `suitable_for`,
`setup_hours`.

**plan**: `provider`, `name`, `price`, `billing_interval` (`monthly` or
`annual`), `min_seats`, `regions`, `max_context`, `messages_per_day`,
`supports_api`, `commercial_use`, `suitable_for`, `setup_hours`.

Prices are written `430.00 EUR`. Lists are comma separated. Yes/no fields
accept `yes` and `no`.

Register the page and crawl it:

```bash
curl -X POST localhost:8000/sources \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://vendor.example.com/prices", "label": "vendor prices"}'

curl -X POST localhost:8000/crawl
```

To fetch real pages rather than the saved examples, set
`LLMFIT_CRAWLER=crawl4ai`, install the crawler extra and its browser:

```bash
.venv/bin/pip install -r requirements-crawler.txt
.venv/bin/python -m playwright install chromium
```

## Real sources

The app ships with readers for two real sites. Register them and crawl:

```bash
export LLMFIT_CRAWLER=crawl4ai
pip install -r requirements-crawler.txt
python -m playwright install chromium
python -m app.seed --real
python -m app.crawler
```

That gives roughly forty rows of real data in half a minute.

| Source | What you get | Reader |
| --- | --- | --- |
| Wikipedia GPU series pages | Card names, memory size, board power, launch price | `wikipedia_gpu` |
| Ollama library tags pages | Model variants, download size, context length | `ollama_models` |

**Read these caveats before trusting the numbers.**

*Prices are launch prices in US dollars*, from Wikipedia, not what a shop
charges today. Ask with `"region": "US"` and `"currency": "USD"` or they are
excluded, which is correct rather than a bug.

*Wikipedia merges cells*, so rows of one table genuinely differ in width and
some carry no memory size at all. Each page therefore has its own list of
layouts in `app/real_sources.py` saying how many cells a row has and which
column is which. Rows that match no layout are counted and reported by
`POST /crawl` instead of being guessed at.

Reusing one page's layouts on another is exactly the mistake to avoid: it looks
like it works and silently produces cards with 276 GB of memory. Two checks
catch it. A memory size must be a size cards actually come in, and the cell has
to be only a number, because `GDDR6X` contains a 6 and is not six gigabytes.
Derive a new page's layouts from that page.

*Ollama does not publish layer counts or licences*, so memory estimates from
those models are marked approximate and commercial use stays unknown. Nor does
it say what a model is good at, so every real model comes back as **uncertain**
rather than confirmed. That is accurate, but it does mean a catalog built only
from these sources returns `only_uncertain_options` with a ranked list, rather
than picking a single winner.

*There is no real source for subscription plans.* Provider pricing pages sit
behind bot protection and do not publish machine-readable terms. Plans still
come from the example page, so a catalog of only real sources has none and the
comparison is between local options alone.

Both sites' robots.txt were checked before being listed, and `app/robots.py`
checks again on every run.

## Adding a site of your own

Write a reader in `app/adapters/`, add it to the table in that package's
docstring, and register a source that names it. Every reader follows one rule:
if the page does not look the way it expects, return nothing. Zero rows is
visible in `GET /pages`; a wrong number quietly entering the catalog is not.

**The fact-block reader is the simple case.** It reads the format above and
nothing else, so an ordinary vendor page yields zero rows rather than wrong
ones. Parsing everywhere is plain string handling, with no regular expressions
and no CSS selectors, which is why it stays readable.

## How the answer is worked out

`app/engine/recommend.py` is one function of your answers and the catalog. It
touches no database and no network, so the same question always gives the same
answer.

**Memory.** Weights, plus a cache that grows with context length and how many
people use it at once, plus an allowance for the runtime. Graphics memory and
system memory are checked separately and never added together. If a model does
not publish its layer sizes the estimate is marked approximate.

**Money.** `Decimal` throughout. Hardware you already own costs nothing extra.
An annual plan is charged in full when it renews, never spread across a shorter
comparison. Minimum seat counts are applied. Electricity is counted for the
whole machine, not just the graphics card's rating.

**Missing facts.** A missing price is not zero. An unknown licence is not
permission. An option with something missing is marked *uncertain* and listed
separately, so it never wins by default.

**Three cases.** Everything is costed again with lower and higher use and power
draw. If the winner changes, the answer says so instead of pretending to be
certain.

## Running the tests

```bash
.venv/bin/python -m pytest
```

The engine tests need nothing but Python. The crawler and API tests use a
PostgreSQL test database and skip if there is not one:

```bash
createdb llmfit_test --owner llmfit
```

No test touches the internet. The crawler tests read saved pages from
`tests/fixtures/pages`.

## Where things are

```text
app/
  main.py        the endpoints
  schemas.py     every Pydantic model
  options.py     the choices, and what each one means
  db.py          five tables
  catalog.py     database rows into engine shapes
  crawler.py     fetch pages, save them, fill the catalog
  extract.py     read fact blocks out of Markdown
  netguard.py    refuse to fetch internal addresses
  seed.py        register the example sources
  engine/        the decision
docs/guide.md    this file
migrations/      one migration that creates the tables
tests/           engine, extractor, crawler, API
```

## Settings

All environment variables, all prefixed `LLMFIT_`. Copy `.env.example` to
`.env` to change them.

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLMFIT_DATABASE_URL` | local `llmfit` database | Where the data lives |
| `LLMFIT_CRAWLER` | `fixture` | `fixture` reads saved pages, `crawl4ai` fetches real ones |
| `LLMFIT_FIXTURE_DIR` | `tests/fixtures/pages` | Where saved pages are |
| `LLMFIT_MAX_PAGE_BYTES` | `524288` | Largest page kept |
| `LLMFIT_ALLOW_PRIVATE_ADDRESSES` | `false` | Leave off unless crawling a local test server |

## What it will not do

- Add graphics memory and system memory together.
- Treat a missing price or electricity rate as zero.
- Spread an annual commitment across a two-month comparison.
- Guess a licence that nobody has confirmed.
- Claim a model is fast enough. It checks whether it fits, not how quick it is.
