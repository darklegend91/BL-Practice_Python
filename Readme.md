# LLM Fit Advisor

Answers one question: should you run a language model on your own computer, or
pay for a subscription?

You pick from options and give a few numbers. It compares your current
computer, your computer plus a new graphics card, a whole new machine, and the
subscription plans it knows about, then tells you which is cheapest over the
period you care about and why the others were ruled out.

It runs no model and calls no model API. The answer is arithmetic over a
catalog that a crawler fills in.

**No login, no accounts, no API keys.** One `POST` and you have your answer.

## Two ways to use it

Both do exactly the same work. They share one engine and one catalog, so they
cannot give you different answers.

```bash
python -m app            # a menu: ask here, or start the web API
python -m app ask -i     # answer questions in the terminal
python -m app serve      # start the web API at http://localhost:8000/docs
```

## Quick start

```bash
make install
createuser llmfit --createdb && createdb llmfit --owner llmfit
export LLMFIT_DATABASE_URL="postgresql+psycopg://llmfit:llmfit@localhost:5432/llmfit"
python -m app setup      # create the tables, register the example sources
python -m app crawl      # fill the catalog from them
python -m app ask -i     # ask your question in the terminal
```

Prefer the web API? `python -m app serve` and open
<http://localhost:8000/docs>. Not sure? `python -m app` gives you the menu.

Those steps use the bundled example pages. For real data from Wikipedia and
Ollama instead:

```bash
pip install -r requirements-crawler.txt && python -m playwright install chromium
export LLMFIT_CRAWLER=crawl4ai
python -m app.seed --real && python -m app.crawler
```

About forty real rows in half a minute. Read the caveats in
[`docs/guide.md`](docs/guide.md#real-sources) first: the prices are *launch*
prices in USD, and Ollama does not publish enough for any model to count as
confirmed.

Then ask it something over HTTP:

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

Only `workloads` is required. `GET /options` lists every choice and the number
each one means.

## The whole command line

| Command | What it does |
| --- | --- |
| `python -m app` | A menu: ask here, or start the web API |
| `python -m app ask -i` | Answer the questions one at a time |
| `python -m app ask --workloads coding --vram 16 --ram 32` | Straight through, for scripts |
| `python -m app ask --json` | The raw result, for piping |
| `python -m app options` | Every choice and what each one means |
| `python -m app catalog` | What the answer would be based on |
| `python -m app crawl` | Fetch every registered source now |
| `python -m app sources --add URL` | Register a page to read |
| `python -m app setup` | Create the tables and register sources |
| `python -m app serve` | Start the web API instead |

`pip install -e .` also gives you `llmfit` as a command, if you would rather
type that than `python -m app`.

## The whole API

Every `POST` has a `GET` beside it that tells you what to send it.

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

Lost? `curl localhost:8000/` explains everything, including the setup steps.

## How it fits together

```
sources  ->  POST /crawl  ->  pages  ->  extract  ->  hardware / models / plans
                                                              |
                                              POST /recommend -+-> your answer
```

Five tables in one PostgreSQL database. Pydantic validates everything going in
and coming out. The decision itself is a single function that touches no
database and no network, so the same question always gives the same answer.

[`docs/guide.md`](docs/guide.md) has the full walk-through: every endpoint,
the page format the crawler reads, how the costing works, and how to point it
at a site of your own.

## What it will not do

- Add graphics memory and system memory together as if they were one pool.
- Treat a missing price or electricity rate as zero.
- Spread a twelve-month commitment across a two-month comparison.
- Assume a licence allows commercial use because nobody said otherwise.
- Tell you a model will be fast. It checks whether it fits, not how quick it is.

Anything with a fact missing is reported as *uncertain* and listed apart from
the real answers, so it can never win by default.

## Tests

```bash
make test
```

The engine tests need only Python. The crawler and API tests want a PostgreSQL
test database (`createdb llmfit_test --owner llmfit`) and skip without one.
Nothing in the suite touches the internet.
