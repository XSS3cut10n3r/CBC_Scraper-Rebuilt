"""Find explicitly configured or conventional local browser request files."""
import os
from pathlib import Path

from .client import ScraperError

SETUP_HELP = '''Browser login is not set up yet.
Run: cbc-scraper setup
Or run: cbc-scraper setup --template
Then follow the instructions in edit_this_request.txt.
Then run your original command again.'''


def find_request(explicit=None, data_dir=Path('data')):
    configured = explicit or os.environ.get('CBC_REQUEST_FILE')
    if configured:
        path = Path(configured).expanduser()
        if not path.is_file():
            raise ScraperError('The selected request file does not exist. Run cbc-scraper setup to choose it again.')
        return path
    if os.environ.get('CBC_COOKIE'):
        return None
    root = Path(__file__).resolve().parent.parent
    for path in [Path('edit_this_request.txt'), Path('sample_request.txt'), Path(data_dir) / 'request.txt',
                 root / 'edit_this_request.txt',
                 root / 'sample_request.txt', root / 'data' / 'request.txt']:
        if path.is_file():
            return path
    raise ScraperError(SETUP_HELP)


REQUEST_TEMPLATE = '''# CBC Scraper browser login
#
# 1. Log in at https://nsa-codebreaker.org in your browser.
# 2. Press F12 (or open Developer Tools), choose Network, and reload the page.
# 3. Select the /challenge request to nsa-codebreaker.org.
# 4. Under Headers > Request Headers, find Cookie and copy its entire value.
#    Include all name=value pairs, separated by semicolons.
# 5. Replace PASTE_COOKIE_VALUE_HERE below with that value. Save this file.
# 6. Run cbc-scraper. It finds this file automatically.
#
# Alternative: delete the Cookie line and paste the entire request using
# Network > right-click the request > Copy > Copy as cURL (bash).
# Keep the comments; copied commands are parsed, never executed.
#
# This file contains your login. Keep it private. It is ignored by Git.
# If your login expires, repeat these steps with a fresh browser request.

Cookie: PASTE_COOKIE_VALUE_HERE
'''
