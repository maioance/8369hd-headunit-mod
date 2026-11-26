"""Small, verified patches to init.axf (8369HD, APP 20250320).

Each patch checks the original bytes first, so it refuses to touch another firmware version.
  door_popup: a door / boot / seat-belt change no longer opens the full-screen "Vehicle information"
              app (CarComputer); climabar.mod shows the car card / belt icon instead.
              0xe91e2432  jal 0xe915fc82 (EnterApp "CarComputer")  ->  nop
  bt_music_first: opening Bluetooth without a page (from Home) starts on BT Music instead of Dial.
              0xe9152404  c.li s0,1 (page 1 = Dial)  ->  c.j 0xe9152506 (s0 = 201 = BT Music)
  belt_binding: the status bar's seat-belt control ("ViewShowImageDashSeatBelt", added to SystemBar.data etc. by
              tools/add_belt_control.py) works on every screen. Each app binds control names to handlers through
              its own (name, handler) table; only one table has the belt entry (handler 0xe9168fe4: shows the
              symbol while the int at 0xe931e874 is non-zero; climabar.mod sets it from the belt bits). In every
              other table that binds the Bluetooth symbol, one entry no screen uses is pointed at the belt name +
              handler instead.
  (aa_stay, removed: kept the unit from jumping into Android Auto when a session started; that also bypassed the
              stock start of a wireless session (type 900: flag 0xe931df90 -> main loop opens the screen and closes the
              connect screen) and Android Auto had no sound. Not needed since no_startup_link: a session starts only
              from the Auto button, where its screen is wanted.)
  no_startup_link: a wireless link (Android Auto, CarPlay) the phone offers is opened only while its screen is shown
              (the Auto button). The connect handler 0xe91a89e6 opens it at once when the link's screen is shown
              (+116, set by lib_link_show) or bStartUpReconnectLink is on; otherwise it skips it only in the first
              50 s after power-on. Now bStartUpReconnectLink defaults to 0 (the key is not in Config.ini) and the
              50 s limit is gone, so an offer outside the Auto screen is always skipped.
              Without this, wireless Android Auto started by itself and took the phone's media from BT.
              0xe91b68f0  c.li a2,1 (default of bStartUpReconnectLink)  ->  c.li a2,0
              0xe91a8a70  bltu a5,a0,0xe91a8a80 (more than 50 s since power-on: open it)  ->  nop
  preset_names: the radio preset buttons show the learned RDS station name: the handlers of their two text
              controls (ViewShowStrSubFreq<i> and ViewShowStrSubFreq<i>Num, i = 1..6) in the radio screen's
              (name, handler) table point to the hooks at 0xe9000000 + 8 * i in climabar.mod (climabar_hooks in
              src/start.S), which call the stock handler and replace its text with the name when one is known.
  climate_no_popup: a climate change no longer opens the full-screen AirCondition app (climabar.mod shows its strip);
              the full climate page still opens from its button and refreshes. The climate decoder (0xe91e2566) opens
              the app unless the climate UI block's +4 is set (then it only marks a refresh): the check is gone.
              0xe91e2568  c.beqz a4,0xe91e2576  ->  c.nop

usage: patch_initaxf.py <init.axf> <out init.axf> [patch ...]   (default: all)
"""
import sys

BASE, FILE_OFF = 0xe9100000, 0x16c        # init.axf LOAD segment: vaddr 0xe9100000 at file offset 0x16c
NOP = bytes.fromhex('13000000')
BELT_ENTRY = (0xe9272a78).to_bytes(8, 'little') + (0xe9168fe4).to_bytes(8, 'little')   # "ViewShowImageDashSeatBelt"


PATCHES = {
    'door_popup': (0xe91e2432, bytes.fromhex('ef d0 17 85'), NOP),
    'no_startup_link': [
        (0xe91b68f0, bytes.fromhex('0546'), bytes.fromhex('0146')),
        (0xe91a8a70, bytes.fromhex('63e8a700'), NOP),
    ],
    'climate_no_popup': (0xe91e2568, bytes.fromhex('19c7'), bytes.fromhex('0100')),
    'bt_music_first': (0xe9152404, bytes.fromhex('05 44'), bytes.fromhex('09 a2')),
    'preset_names': [(table + 16 * k + 8, (h).to_bytes(8, 'little'), (0xe9000000 + 8 * k).to_bytes(8, 'little'))
                     for table, handlers in (
                         (0xe9277c18, (0xe9177202, 0xe91771f6, 0xe91771ea, 0xe91771de, 0xe91771d2, 0xe91771c6)),  # ViewShowStrSubFreq<i>
                         (0xe9277c78, (0xe917713e, 0xe9177132, 0xe9177126, 0xe917711a, 0xe917710e, 0xe9177102)),  # ...<i>Num (no unit)
                     ) for k, h in enumerate(handlers)],
    'belt_binding': [(va, bytes.fromhex(old), BELT_ENTRY) for va, old in (
        (0xe9266b68, '487126e900000000801415e900000000'),   # Bt:  ViewShowImageBtConnectWireless
        (0xe926d358, '387226e900000000a0bf15e900000000'),   # ViewShowImageBtConnect2
        (0xe9274f58, 'f85827e900000000c21117e900000000'),   # ViewShowImagePlayMode2
        (0xe9277220, '387226e9000000008c3117e900000000'),   # ViewShowImageBtConnect2
        (0xe9277998, '508227e9000000004e5417e900000000'),   # Radio: ViewShowImageStEx
        (0xe9278e18, '387226e900000000ec7b17e900000000'),   # ViewShowImageBtConnect2
        (0xe927ae70, '18cc27e9000000001ea617e900000000'),   # ViewShowImageColorLamp
        (0xe9288a70, '409128e900000000aa5418e900000000'),   # ViewShowImageBtConnect3
        (0xe9289af8, '387226e9000000009e7218e900000000'),   # ViewShowImageBtConnect2
    )],
}


def main(src, out, names):
    data = bytearray(open(src, 'rb').read())
    for name in names or PATCHES:
        p = PATCHES[name]
        for va, old, new in p if isinstance(p, list) else [p]:
            o = va - BASE + FILE_OFF
            cur = bytes(data[o:o + len(old)])
            if cur == new:
                print(f'{name}: 0x{va:x} already applied')
                continue
            if cur != old:
                sys.exit(f'{name}: unexpected bytes at 0x{va:x}: {cur.hex()} (expected {old.hex()}) - other firmware?')
            data[o:o + len(new)] = new
            print(f'{name}: 0x{va:x} {old.hex()} -> {new.hex()}')
    open(out, 'wb').write(data)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
