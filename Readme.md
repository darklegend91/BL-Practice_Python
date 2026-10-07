# LLM Fit Advisor

Answers one question: should you run a language model on your own computer, or
pay for a subscription?

You pick from fixed options and give a few numbers. It compares the computer
you already have, that computer plus a new graphics card, a whole new machine,
and the subscription plans it knows about, then tells you which is cheapest
over the period you care about and why the others were ruled out.

It runs no model and calls no model API. The answer is arithmetic over a
catalog that a crawler fills in. There are no accounts, no logins and no API
keys.

## Two ways to use it

The terminal and the web API do the same work. They call the same engine over
the same catalog, so they cannot give you different answers.

```bash
python -m app            # a menu: ask here, or start the web API
python -m app ask -i     # answer the questions in the terminal
python -m app serve      # start the web API at http://localhost:8000/docs
```

Run it with no command and it asks which you want:

```
LLM Fit Advisor 0.2.0

How do you want to use it?

  1  Answer some questions here and get a recommendation
  2  Start the web API instead  (http://localhost:8000/docs)
  3  Show what is in the catalog
  4  Fetch the sources again
  5  Show the questions and what each answer means
  q  Quit
```

## Getting it running

Needs Python 3.12 or newer and PostgreSQL.

```bash
make install                                    # virtualenv and dependencies
createuser llmfit --createdb
createdb llmfit --owner llmfit
export LLMFIT_DATABASE_URL="postgresql+psycopg://llmfit:llmfit@localhost:5432/llmfit"

make setup      # create the five tables, register the example sources
make crawl      # read those sources into the catalog
make cli        # ask your question
```

`make` is only a shortcut: every target is a single `python -m app` command,
all of them in the table below.

### Using real data instead

The steps above read bundled example pages describing invented products, so the
app works before you have sources of your own. For real figures from Wikipedia
and Ollama:

```bash
pip install -r requirements-crawler.txt
python -m playwright install chromium
export LLMFIT_CRAWLER=crawl4ai
make real       # register the real sources and fetch them
```

About forty real rows in half a minute. **Read the caveats** in
[`docs/guide.md`](docs/guide.md#real-sources) first. The short version: prices
are *launch* prices in US dollars, so ask with `--region US --currency USD`;
and Ollama publishes neither layer counts nor licences nor what a model is good
at, so every real model comes back as *uncertain* rather than confirmed.

## The command line

| Command | What it does |
| --- | --- |
| `python -m app` | The menu above |
| `python -m app ask -i` | Answer the questions one at a time |
| `python -m app ask --workloads coding --vram 16 --ram 32` | Straight through, for scripts |
| `python -m app ask --json` | The raw result, for piping |
| `python -m app ask --all` | Show every ruled-out option, not just the first five |
| `python -m app ask --currency INR` | Prices converted, with the rate shown |
| `python -m app ask --currency INR --rate USD=88.20` | Your own rate instead of the shipped one |
| `python -m app options` | Every choice and the number it turns into |
| `python -m app catalog` | What the answer would be based on |
| `python -m app crawl` | Fetch every registered source now |
| `python -m app sources --add URL` | Register a page to read |
| `python -m app setup` | Create the tables and register sources |
| `python -m app serve` | Start the web API instead |

Add `--help` to any of them. `pip install -e .` also gives you `llmfit` as a
command if you would rather type that.

The `make` targets are `install`, `setup`, `crawl`, `real`, `cli`, `run`,
`menu` and `test`.

## The web API

Start it with `python -m app serve`, then:

```bash
curl -X POST localhost:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{
    "workloads": ["coding"],
    "usage": "medium",
    "months": 24,
    "electricity_per_kwh": "0.32",
    "existing_computer": {"gpu_vram_gb": "16", "system_ram_gb": "32"}
  }'
```

Only `workloads` is required. Every `POST` has a `GET` beside it that tells you
what to send.

| Endpoint | What it does |
| --- | --- |
| `GET /` | Start here. What this is, how to set it up, every endpoint explained |
| `POST /recommend` | Send your answers, get the recommendation |
| `GET /recommend` | What to send to `POST /recommend`, with an example to copy |
| `GET /options` | What you are allowed to choose |
| `GET /catalog` | The data the answer was based on |
| `GET /pages` | What the crawler fetched |
| `GET /sources`, `POST /sources` | The pages the crawler visits |
| `GET /sources/help` | What to send to `POST /sources` |
| `POST /crawl` | Fetch them all again now |
| `GET /crawl` | What `POST /crawl` does |
| `GET /health` | Up, and database reachable |

Lost? `curl localhost:8000/` explains the whole thing, setup steps included,
and <http://localhost:8000/docs> is the same API you can click through.

## How it fits together

```
 sources  ->  crawl  ->  pages  ->  adapters  ->  hardware / models / plans
                                                           |
                                                           v
                    python -m app ask   or   POST /recommend   ->  your answer
```

Five tables in one PostgreSQL database. Pydantic validates everything going in
and coming out. One reader per kind of page lives in `app/adapters/`, and a
source says which one understands it.

The decision itself is a single function that touches no database and no
network, so the same question always gives the same answer.

[`docs/guide.md`](docs/guide.md) is the full walk-through: both ways to run it,
every endpoint, the page format the crawler reads, how the costing works, and
how to point it at a site of your own.

## What it will not do

- Add graphics memory and system memory together as if they were one pool.
- Treat a missing price or electricity rate as zero.
- Spread a twelve-month commitment across a two-month comparison.
- Assume a licence allows commercial use because nobody said otherwise.
- Tell you a model will be fast. It checks whether it fits, not how quick it is.
- Call an exchange-rate service. Rates are written down in `app/rates.py` with
  the date they were checked, and every converted price says which rate it used.

Anything with a fact missing is reported as *uncertain* and listed apart from
the confirmed answers, so it can never win by default. When a page does not
look the way a reader expects, it returns nothing rather than guessing, and
says so in `GET /pages`.

## Tests

```bash
make test
```

The engine, rendering and adapter tests need only Python. The crawler, CLI and
API tests want a PostgreSQL test database and skip cleanly without one:

```bash
createdb llmfit_test --owner llmfit
```

Nothing in the suite touches the internet. The adapters are tested against real
crawled pages saved under `tests/fixtures/real`.
