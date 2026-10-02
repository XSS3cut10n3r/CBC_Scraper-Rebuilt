"""Find explicitly configured or conventional local browser request files."""
import os
from pathlib import Path

from .client import ScraperError

SETUP_HELP = '''Browser login is not set up yet.
Run: cbc-scraper setup
Or save your browser's copied cURL request as sample_request.txt in this folder.
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
    for path in [Path('sample_request.txt'), Path(data_dir) / 'request.txt',
                 root / 'sample_request.txt', root / 'data' / 'request.txt']:
        if path.is_file():
            return path
    raise ScraperError(SETUP_HELP)
