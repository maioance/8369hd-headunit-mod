"""English titles in the language tables (apps/Language/*.txt, UTF-16 LE, tab-separated, Chinese key first).

Replaces only the English column of the listed entries, everything else stays byte-identical.
usage: fix_titles.py <stock Language dir> <out Language dir>
"""
import os
import sys

FILES = ('SystemBar.txt', 'Main.txt', 'Bt.txt')   # title bar, home menu, Bluetooth screens
TITLES = {
    '空调': ('air conditioner', 'Air Conditioner'),
    '蓝牙连接名称：': ('Bluetooth Connection nameName:', 'Connected phone:'),
}


def main(src, out):
    os.makedirs(out, exist_ok=True)
    for name in FILES:
        text = open(os.path.join(src, name), 'rb').read().decode('utf-16')
        n = 0
        for key, (old, new) in TITLES.items():
            a, b = f'\t{key}\t{old}\t', f'\t{key}\t{new}\t'
            n += text.count(a)
            text = text.replace(a, b)
        open(os.path.join(out, name), 'wb').write(text.encode('utf-16'))   # with BOM, as the stock files
        print(f'{name}: {n} title(s) changed')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
