"""The volume popup (apps/Data/VolumeBar.data + Language/VolumeBar.txt): a full-width bar at the top of the screen,
made from the display settings' backlight row (emulator/tools/build_volume_bar.py), with a Material Symbols speaker
instead of the word "Volume" and the stock teal slider in white (tools/teal_to_white.py).

usage: build_volume_popup.py <stock apps dir> <out apps dir> <Material Symbols cache dir>
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))
import teal_to_white                                  # noqa: E402
from theme import BG                                  # noqa: E402

BUILD_VOLUME_BAR = os.path.join(os.path.dirname(__file__), '../emulator/tools/build_volume_bar.py')
ICON, ICON_MUTED, ICON_PX, ICON_COLOUR = 'volume_up', 'volume_off', 30, '#d2d6d8'
BAR = dict(y=0, panel=70, width=1024, color=','.join(map(str, BG)), alpha=255, effect=3)   # top of the screen, full
#                                                                             width, the screen background, slides down


def icon(cache, name, out):
    svg = open(os.path.join(cache, name + '.svg')).read().replace('<svg ', f'<svg fill="{ICON_COLOUR}" ', 1)
    tinted = out + '.svg'
    open(tinted, 'w').write(svg)
    subprocess.run(['magick', '-background', 'none', '-density', '384', tinted, '-resize', f'{ICON_PX}x{ICON_PX}',
                    'PNG32:' + out], check=True)
    return out


def main(src, out, cache):
    data = os.path.join(out, 'Data', 'VolumeBar.data')
    os.makedirs(os.path.dirname(data), exist_ok=True)
    os.makedirs(os.path.join(out, 'Language'), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        args = [sys.executable, BUILD_VOLUME_BAR, os.path.join(src, 'Data', 'SetupVideo.data'), data,
                '--icon', icon(cache, ICON, os.path.join(tmp, 'icon.png')),
                '--icon-muted', icon(cache, ICON_MUTED, os.path.join(tmp, 'muted.png')),
                '--lang', os.path.join(src, 'Language', 'Setup.txt'), os.path.join(out, 'Language', 'VolumeBar.txt')]
        for k, v in BAR.items():
            args += [f'--{k}', str(v)]
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
    teal_to_white.main([data])


if __name__ == '__main__':
    main(*sys.argv[1:4])
