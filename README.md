![Codebreaker Challenge Stats (Unofficial)](assets/readme-banner.png)

School leaderboards, fastest first solves, and your personal task times in the terminal.

## Get started

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e .
cbc-scraper
```

Pick an option from the menu. Choose **Set up / refresh browser login** on your first run, or put your copied browser cURL request in `sample_request.txt`.

## Shortcuts

```sh
cbc-scraper submissions                       # Your attempts and times
cbc-scraper leaderboard --task 'Task 8'       # Earliest school solves
cbc-scraper leaderboard --school 'Georgia'   # Filter schools
cbc-scraper submissions --display             # Saved results, offline
cbc-scraper setup                             # Refresh your login
```

**Solve Time** runs from the previous task's last submission to the current task's last submission. **Total** starts at your first task0 submission. Times include breaks; submissions are approximate completion markers.

More options: `cbc-scraper --help`. Login files and results stay local and are excluded from Git.

Based on [code-zm/cbc_scraper](https://github.com/code-zm/cbc_scraper). [GPL-3.0-or-later](COPYING).
