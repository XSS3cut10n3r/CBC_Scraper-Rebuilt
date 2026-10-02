# CBC Scraper

An unofficial NSA Codebreaker statistics terminal, rebuilt from [code-zm/cbc_scraper](https://github.com/code-zm/cbc_scraper). GPL-3.0-or-later; see COPYING.

Features include an NSA ASCII banner, current task discovery, historical leaderboards (2018–2025 configurations), task solve rates, school participation, earliest-solving schools per task, school and task filters, personal submission statistics, offline cache viewing, and JSON/CSV exports.

## Install

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Start here

With your virtual environment active, run:

```sh
cbc-scraper
```

Choose a number from the menu: school leaderboards, your submissions, saved results, or login setup. You can also open the menu with `python -m cbc_scraper`.

The original scripts work without flags once login is saved:

```sh
python scrape_submissions.py
python scrape_leaderboards.py
```

## First-time login (or an expired session)

```sh
cbc-scraper setup
```

The setup walks you through copying a browser request and asks for the saved file's path. It saves a private local copy in `data/request.txt`; future runs find it automatically. You only repeat setup when your browser login expires.

If you already have `sample_request.txt`, place it in this project folder and run either script. No setup command or request-file flag is needed.

Advanced options: `--request-file /path/to/request.txt` or `CBC_REQUEST_FILE` selects a specific file. `CBC_COOKIE` supplies cookies directly, and `CBC_CSRF_TOKEN` can supply a token. Automatic discovery checks `sample_request.txt` and `data/request.txt` in the working directory, then the project directory. An explicit request file takes precedence, followed by environment configuration, then automatic discovery. If both conventional files exist, `sample_request.txt` takes precedence.

Copied cURL text is parsed, never executed. Cookie names including `cbweb_session` and `remember_token` are retained, and CSRF is refreshed from the leaderboard page. Cookies are never printed or included in exported results. Login files and data are excluded from Git; keep differently named credential files outside the repository.

```sh
cbc-scraper leaderboard --task 'Task 8' --top 10
cbc-scraper leaderboard --school 'Georgia'
cbc-scraper submissions
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
- **Task interval** measures from the preceding numbered task's last submission to the current task's last submission. Task0 starts at its first submission. Times use hours, minutes, and seconds, including breaks and time before your first attempt on the next task.
- **Since task0** measures cumulative elapsed time from your first task0 submission to each task's last submission. These are approximate task boundaries, not confirmed completion times. Missing preceding tasks or timestamps, unsupported task labels, and reversed boundaries show `N/A` rather than a fabricated interval. Without task0, cumulative times are unavailable.
- Exports include both task intervals and cumulative durations, plus the original `attempt_span` fields (first-to-last submissions within one task) for compatibility. Cached raw submissions are reanalyzed automatically with the new calculations.
- The submission Status column is hidden when no explicit completion statuses are available. Exports retain **Unknown** unless an explicit success/status field exists. The live API currently supplies response prose, and the old challenge-specific success hashes cannot reliably classify new tasks.

Requests use timeouts, HTTPS, a cookie jar, and bounded pagination. Redirects are not followed. Current board and submission endpoints were tested with an authenticated browser request; archive configurations are inherited and have not all been live-verified.

## Tests

```sh
python -m unittest discover -s tests
```
