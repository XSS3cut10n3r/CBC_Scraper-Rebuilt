"""Terminal-native ASCII interpretation of the NSA eagle, shield, and key."""
from rich.text import Text

SEAL = r'''
                     .===========================.
                .===='                           '====.
            .==='       NATIONAL SECURITY AGENCY       '===.
         .=='                                               '==.
       .='          .-----------------------------.            '=.
     .='        .--'                               '--.          '=.
    /         .'             ___                       '.          \
   /         /              / o '>                       \          \
  |         /     __       /   /__          __            \          |
  |        |    /`  `\    /       \       /`  `\           |         |
  |        |   / / /  \__/  /\     \_____/  \ \ \          |         |
  |        |  / / / /     /  \             \ \ \ \        |         |
  |        | / / / / /\  /    \  /\         \ \ \ \       |         |
  |        | |/ / / / /\/      \/\ \ \ \ \ \ \ \ \|       |         |
  |        | / / / / / .-----------------. \ \ \ \ \      |         |
  |        | |/ / / / /| * * * * * * * * |\ \ \ \ \|      |         |
  |        | / / / / / |-----------------| \ \ \ \ \      |         |
  |        | |/ / / /  | ||  ||  ||  || |  \ \ \ \|      |         |
  |        | / / / /   | ||  ||  ||  || |   \ \ \ \      |         |
  |        | |/ / /    \ ||  ||  ||  || /    \ \ \|      |         |
  |        | / / /      \||  ||  ||  ||/      \ \ \      |         |
  |        | |/ / /      \|  ||  ||  |/      \ \ \|      |         |
  |        |  / / / /     \ ||  ||  /      \ \ \ \       |         |
  |        |  |/ / / /     \||  || /      \ \ \ \|       |         |
  |        |   |/ / / /     \|__|/       \ \ \ \|        |         |
  |        |    |/ / /    __/||||\__      \ \ \|         |         |
  |        |     |/ /   _/ /||||||\ \_     \ \|          |         |
  |        |      \/   /_ /||||||||\ _\     \/           |         |
  |        |          /(_\_||||||||_/_)\          .-.     |         |
  |        |     =======((==========))============(   )   |         |
  |         \        |_|_|  \||||/               '-+-'   /          |
   \         \       |_|_|   \||/                       /          /
    \         '.              \/                      .'          /
     '= .       '--.                              .--'        . ='
        '==.        '----------------------------'         .=='
           '===.       UNITED STATES OF AMERICA       .==='
               '====.                            .===='
                    '============================'
'''.strip('\n')

# Five-row block lettering keeps the full word readable in an 80-column terminal.
GLYPHS = {
    'C': (' ####', '##   ', '##   ', '##   ', ' ####'),
    'O': (' ### ', '## ##', '## ##', '## ##', ' ### '),
    'D': ('#### ', '## ##', '## ##', '## ##', '#### '),
    'E': ('#####', '##   ', '#### ', '##   ', '#####'),
    'B': ('#### ', '## ##', '#### ', '## ##', '#### '),
    'R': ('#### ', '## ##', '#### ', '## ##', '## ##'),
    'A': (' ### ', '## ##', '#####', '## ##', '## ##'),
    'K': ('## ##', '## # ', '###  ', '## # ', '## ##'),
}
TITLE = '\n'.join(' '.join(GLYPHS[letter][row] for letter in 'CODEBREAKER') for row in range(5))
WIDTH = max(max(map(len, SEAL.splitlines())), max(map(len, TITLE.splitlines())))
BANNER = '\n'.join(line.ljust(WIDTH) for line in SEAL.splitlines()) + '\n\n' + '\n'.join(
    line.center(WIDTH) for line in TITLE.splitlines()
) + '\n' + 'C H A L L E N G E'.center(WIDTH) + '\n\n' + 'UNOFFICIAL STATS TERMINAL'.center(WIDTH)


def print_banner(console):
    # Preserve the seal geometry on narrow terminals through horizontal cropping.
    # Normal 80-column terminals display the entire artwork.
    text = Text(BANNER, style='bold gold1', no_wrap=True, overflow='crop')
    start = BANNER.index(TITLE.splitlines()[0].strip())
    text.stylize('bold bright_cyan', start, len(BANNER))
    console.print(text, highlight=False)
