"""Parse psxdatacenter HTML dumps into a CSV database."""
import sys, re, csv, os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LANG_MAP = {
    'E': 'En', 'F': 'Fr', 'G': 'De', 'S': 'Es', 'I': 'It',
    'D': 'Nl', 'P': 'Pt', 'R': 'Ru', 'J': 'Ja', 'K': 'Ko',
    'Sw': 'Sv', 'N': 'No', 'Da': 'Da', 'Fi': 'Fi', 'C': 'Zh',
}

def parse_langs(raw):
    raw = raw.replace('&nbsp;', '').strip()
    if not raw:
        return ''
    codes = re.findall(r'\[([A-Za-z]+)\]', raw)
    if not codes:
        return ''
    return ','.join(LANG_MAP.get(c, c) for c in codes)

def parse_html(path, console, region):
    if not os.path.exists(path):
        print(f'  SKIP: {os.path.basename(path)}')
        return []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    games = []
    # Match: col2 or col6 has serial, col3/col7 has title, col4/col8 has langs
    for m in re.finditer(
        r'class="col[26]"[^>]*>([A-Z]{4}-\d{5})</td>'
        r'\s*<td class="col[37]"[^>]*>([^<]*)</td>'
        r'\s*<td class="col[48]"[^>]*>([^<]*)</td>',
        content
    ):
        serial = m.group(1)
        title = m.group(2).replace('&nbsp;', '').strip()
        langs = parse_langs(m.group(3))
        if title:
            games.append({
                'console': console, 'region': region,
                'serial': serial, 'title': title, 'languages': langs,
            })
    return games

base = os.environ.get('DOWNLOADS', os.path.expanduser('~/Downloads'))
all_games = []

sources = [
    ('PS2', 'NTSC-U', f'{base}/PlayStation 2 DataCenter - NTSC-U List_files/ulist2.html'),
    ('PS2', 'PAL',    f'{base}/PlayStation 2 DataCenter - PAL List_files/plist2.html'),
    ('PS2', 'NTSC-J', f'{base}/PlayStation 2 DataCenter - NTSC-J List_files/jlist2.html'),
    ('PS1', 'NTSC-U', f'{base}/PlayStation DataCenter - NTSC-U List_files/ulist.html'),
    ('PS1', 'PAL',    f'{base}/PlayStation DataCenter - PAL List_files/plist.html'),
    ('PS1', 'NTSC-J', f'{base}/PlayStation DataCenter - NTSC-J List_files/jlist.html'),
    ('PSP', 'NTSC-U', f'{base}/PSP DataCenter - NTSC-U List_files/ulist.html'),
    ('PSP', 'PAL',    f'{base}/PSP DataCenter - PAL List_files/plist.html'),
    ('PSP', 'NTSC-J', f'{base}/PSP DataCenter - NTSC-J List_files/jlist.html'),
]

for console, region, path in sources:
    games = parse_html(path, console, region)
    print(f'{console} {region}: {len(games)} games')
    all_games.extend(games)

print(f'\nTotal: {len(all_games)} games')

csv_path = f'{base}/ai-console-game-patchs/psxdatacenter_db.csv'
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['console', 'region', 'serial', 'title', 'languages'])
    writer.writeheader()
    writer.writerows(all_games)

print(f'CSV: {csv_path}')

# Verify
for serial in ['SLUS-20001', 'SCUS-97113', 'SLUS-20718', 'SLUS-21075',
               'SCES-01438', 'SCUS-94228', 'SLUS-20079']:
    matches = [g for g in all_games if g['serial'] == serial]
    for g in matches:
        print(f'  {g["serial"]} | {g["title"]:40s} | {g["languages"]}')
