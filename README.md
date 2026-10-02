# CBC Scraper

An unofficial NSA Codebreaker statistics terminal, rebuilt from [code-zm/cbc_scraper](https://github.com/code-zm/cbc_scraper). GPL-3.0-or-later; see COPYING.

Features include an NSA ASCII banner, current task discovery, historical leaderboards (2018–2025 configurations), task solve rates, school participation, earliest-solving schools per task, school and task filters, personal submission statistics, offline cache viewing, and JSON/CSV exports.

## Install

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Authentication

In your browser's developer tools, copy a request to nsa-codebreaker.org as cURL and save it locally as `sample_request.txt` or `data/request.txt`. Pass its path with `--request-file`. The text is parsed, never executed. All cookie names are retained, including the current `cbweb_session` and `remember_token`; CSRF is refreshed from the leaderboard page. Cookies are neither printed nor written to the result cache. Request files and data are excluded from Git; keep differently named credential files outside the repository.

Alternatively set `CBC_COOKIE` to the complete Cookie header value and optionally `CBC_CSRF_TOKEN`. No password login is required. Expired cookies require a fresh browser request.

```sh
cbc-scraper --request-file sample_request.txt
cbc-scraper --request-file sample_request.txt --task 'Task 8' --top 10
cbc-scraper --request-file sample_request.txt --school 'Georgia'
cbc-scraper submissions --request-file sample_request.txt
```

## Cache and export

```sh
cbc-scraper --display
cbc-scraper --display --year 2025
cbc-scraper --display --format json --output data/report.json
cbc-scraper --display --format csv --output data/schools.csv
cbc-scraper submissions --display --format csv --output data/attempts.csv
cbc-scraper --year 2024 --request-file sample_request.txt
cbc-scraper --all-years --request-file sample_request.txt
```

`--year` explicitly requests an archived board. Omit it for the current board. Current task labels are discovered from the live page; `--tasks 'Task 0,Task 1,...'` provides an override for the modern sequential board layout. `--all-years` fetches the known 2018–2025 archives. Historical schemas may change independently of the current site.

`--data-dir` selects the cache directory. Existing leaderboard caches containing `raw_data` and submission caches containing `all_submissions` remain readable. Each historical year is now cached separately. Failed fetches preserve the previous cache; writes are atomic with private file permissions. Cached submissions include personal response data, so keep the data directory private. Table filters affect displayed school rankings; exports contain the full dataset. `--no-banner` hides the art; JSON/CSV output never includes it.

The old `python scrape_leaderboards.py` and `python scrape_submissions.py` commands remain available.

## What the numbers mean

- **Fastest schools** ranks the earliest recorded first solution per task, in UTC. It does not measure time spent solving. Schools without a valid first-solve timestamp are excluded from this ranking; ties are ordered by school name.
- **School solve rate** is task solvers divided by that school's registered participants.
- **Attempt span** is time between first and last submissions, not active work time.
- Submission completion is **Unknown** unless an explicit success/status field exists. The live API currently supplies response prose, and the old challenge-specific success hashes cannot reliably classify new tasks.

Requests use timeouts, HTTPS, a cookie jar, and bounded pagination. Redirects are not followed. Current board and submission endpoints were tested with an authenticated browser request; archive configurations are inherited and have not all been live-verified.

## Tests

```sh
python -m unittest discover -s tests
```
