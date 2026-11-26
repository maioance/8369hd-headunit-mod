/* climabar.mod: compact climate strip drawn on its own display layer.
 * Reads the climate state init.axf keeps at *(0xe932b210) and shows it at the bottom of the
 * screen for a few seconds whenever it changes, above the GUI and Android Auto.
 * A second, full-screen overlay layer shows the radio station name, learned names on the presets,
 * the door card and the now-playing card; the seat-belt symbol is drawn by the firmware itself.
 * Artwork comes from the PNGs in assets/ and positions from layout.json (build/assets.h). */
#include <stdarg.h>
#include "melis.h"
#include "assets.h"

#define MAYBE_UNUSED __attribute__((unused))

#define W        1024
#define H        STRIP_H
#define Y0       STRIP_Y
#define FB_BYTES (W * H * 4)
#define FB_PAGES ((FB_BYTES + 1023) / 1024)

/* features that draw on the overlay layer */
#define OVERLAY  (RADIO_NAME || DOORS || NOW_PLAYING || BT_TITLE)

/* ---- init.axf (8369HD, APP 20250320) addresses; firmware_ok() refuses any other init.axf ---- */
/* pointer to the decoded climate state; doors and belts live in the same block */
#define CLIMATE_PTR ((uint8_t *volatile *)0xe932b210)
enum { AC_REARLIGHT = 0, AC_MAXFRONT = 4, AC_DUAL = 8, AC_AUTOLOW = 12, AC_AUTOHIGH = 16, AC_CYCLE = 20,
       AC_ON = 24, AC_FAN = 28, AC_FLOW_WINDSHIELD = 36, AC_FLOW_FACE = 40, AC_FLOW_FEET = 44,
       AC_TEMP_L = 48, AC_TEMP_R = 49, AC_AUTOCYCLE = 68, AC_SNAPSHOT = 72,
       AC_BOOT = 116, AC_DOOR_RR = 120, AC_DOOR_RL = 124, AC_DOOR_FR = 128, AC_DOOR_FL = 132,
       AC_BELT_DRIVER = 104, AC_BELT_PASSENGER = 168 };
/* temperature codes: VW CAN box 0 = LO, 31 = HI, else 17.5 + 0.5 * v; other boxes use 254 / 255 */
#define IS_TEMP_LO(c) ((c) == 0 || (c) == 254)
#define IS_TEMP_HI(c) ((c) == 31 || (c) == 255)
/* current app -> handle (+0) -> descriptor (+24) -> name (+0), e.g. "Radio", "Main", "Link" */
#define CUR_APP_PTR   ((uint8_t *volatile *)0xe932ace0)
#define PTY_LIST_OPEN ((volatile int32_t *)0xe931eac0)   /* programme-type list over the radio screen */
#define RADIO         ((volatile uint8_t *)0xe93284e8)   /* +0 band (0..2 FM), +4 frequency, +8.. 6 presets per band */
#define RADIO_FREQ    (*(volatile uint32_t *)(RADIO + 4)) /* FM: 10 kHz units, 8750 = 87.50 MHz; AM: kHz */
#define RADIO_PRESET(i) (*(volatile uint32_t *)(RADIO + 8 + 4 * (RADIO[0] * 6 + (i))))   /* of the current band (e91b1710) */
#define RADIO_PS      ((volatile char *)0xe93285b4)      /* 8 chars, written by the MCU 0xB4 RDS frame */
#define BT_OBJ_PTR    ((uint8_t *volatile *)0xe9321080) /* BT control object: ID3 title at +0x60e (256 bytes) */
#define BT_ID3_TITLE  0x60e                              /* + 0x100 artist, + 0x200 album */
#define BT_PAGE       (*(volatile int32_t *)0xe92df2e4) /* page of the "Bt" app: 201 = BT Music */
#define CAN_PAGE      (*(volatile int32_t *)0xe92df3c8) /* page of the "Can" app: 201 = Vehicle information, 101 = climate */
#define BELT_WARN     (*(volatile int32_t *)0xe931e874) /* read by the "ViewShowImageDashSeatBelt" handler only */
#define LINKS_PTR     ((uint8_t *volatile *)0xe9327dd8) /* link states, 2048 bytes per link (6 = Android Auto wireless) */
#define LINK_AA_WIRELESS 6
#define LINK_ACTIVE   96                                 /* int: set by the link's event callback while a session runs */
#define BT_SEND       ((void (*)(const char *))0xe91930e8) /* line to the BT module, e.g. "AT#CD" (disconnect) */

static melis_mp g_mp;
static int g_disp = -1;
static volatile int g_quit;

/* ---- diagnostic log: only when a USB stick holds an (empty) climabar_log.txt ----
 * Lines are kept in RAM and the file is rewritten at most once a second (log_flush, from the UI loop), so writing
 * the log never holds up the display. A power cut loses at most the last second. */
#define LOG_MAX 16384
static char g_log[LOG_MAX];
static unsigned g_log_n, g_log_dirty;
static char g_log_path[] = "F:\\climabar_log.txt";       /* [0] = 0: no log */

static void log_put(char c) { if (g_log_n < LOG_MAX - 1) g_log[g_log_n++] = c; }
static void log_num(unsigned long v, unsigned base, int neg)
{
	char b[24];
	int n = 0;
	if (neg) log_put('-');
	do { b[n++] = "0123456789abcdef"[v % base]; v /= base; } while (v);
	while (n) log_put(b[--n]);
}

/* printf subset: %d %u %x %s %c; one line per call */
static void lg(const char *fmt, ...)
{
	if (!g_log_path[0] || g_log_n >= LOG_MAX - 1) return;
	va_list ap;
	va_start(ap, fmt);
	log_put('['); log_num(esKRNL_TimeGet() / 100, 10, 0); log_put('s'); log_put(']'); log_put(' ');
	for (const char *f = fmt; *f; f++) {
		if (*f != '%') { log_put(*f); continue; }
		switch (*++f) {
		case 'd': { long v = va_arg(ap, int); log_num(v < 0 ? -v : v, 10, v < 0); break; }
		case 'u': log_num(va_arg(ap, unsigned), 10, 0); break;
		case 'x': log_num(va_arg(ap, unsigned long), 16, 0); break;
		case 'c': log_put((char)va_arg(ap, int)); break;
		case 's': for (const char *t = va_arg(ap, const char *); t && *t; t++) log_put(*t); break;
		default: log_put(*f); break;
		}
	}
	va_end(ap);
	log_put('\r'); log_put('\n');
	g_log_dirty = 1;
}

static void log_flush(void)
{
	static uint32_t next;
	uint32_t now = esKRNL_TimeGet();
	if (!g_log_path[0] || !g_log_dirty || (int32_t)(now - next) < 0) return;
	void *fp = esFSYS_fopen(g_log_path, "wb");
	if (fp) { (void)esFSYS_fwrite(g_log, 1, g_log_n, fp); esFSYS_fclose(fp); }
	g_log_dirty = 0;
	next = now + 100;
}

/* the first USB drive (F: .. Z:) with climabar_log.txt on it, or none: then lg() does nothing */
static void log_open(void)
{
	for (char d = 'F'; d <= 'Z'; d++) {
		g_log_path[0] = d;
		void *fp = esFSYS_fopen(g_log_path, "rb");
		if (fp) { esFSYS_fclose(fp); return; }
	}
	g_log_path[0] = 0;
}

/* ---- safety ---- */
/* the code of two init.axf functions this module knows (EnterApp main path, go-to-app): with another init.axf
 * every address above means something else, so the module does nothing */
static int firmware_ok(void)
{
	return *(volatile uint64_t *)0xe915fc90 == 0x84aae486fc26715dull &&
	       *(volatile uint64_t *)0xe919d478 == 0xf04ee826e4227179ull;
}

/* a firmware update file on a USB drive (F: .. Z:) */
static int update_stick_present(void)
{
	char p[sizeof UPDATE_PATH];
	for (unsigned i = 0; i < sizeof p; i++) p[i] = UPDATE_PATH[i];
	for (char d = 'F'; d <= 'Z'; d++) {
		p[0] = d;
		void *f = esFSYS_fopen(p, "rb");
		if (f) { esFSYS_fclose(f); return 1; }
	}
	return 0;
}

/* ---- firmware state ---- */
/* a plausible pointer: module / app data at 0xe0000000.. (virtual), or heap memory, which on the device is DRAM
 * by its physical address 0x40000000.. (malloc'd objects such as the current app or the BT object live there) */
static int in_ram(uintptr_t p)
{
	uint32_t top = (uint32_t)p >> 28;
	return p && (uint64_t)p >> 32 == 0 && (top == 0xe || top == 0x4);
}

static const char *cur_app(void)
{
	uintptr_t s = (uintptr_t)*CUR_APP_PTR, h, d, n;
	if (!in_ram(s) || !in_ram(h = *(uintptr_t *)s) || !in_ram(d = *(uintptr_t *)(h + 24)) || !in_ram(n = *(uintptr_t *)d))
		return "";
	return (const char *)n;
}

static int app_is(const char *want)
{
	const char *a = cur_app();
	int i = 0;
	for (; want[i]; i++) if (a[i] != want[i]) return 0;
	return a[i] == 0;
}

/* the full-screen climate page is open: it shows everything the strip would */
static int climate_page_open(void) { return app_is("Can") && CAN_PAGE == 101; }

static int32_t field(const uint8_t *s, int off) { return *(const int32_t *)(s + off); }

/* ---- display layers ---- */
static void put32(uint8_t *c, int off, uint32_t v) { *(uint32_t *)(c + off) = v; }
static void put64(uint8_t *c, int off, uint64_t v) { *(uint64_t *)(c + off) = v; }

/* window (x, y, w, h) on screen, showing the same rectangle of a screen-sized buffer (or all of a smaller one) */
static void layer_window(uint8_t *c, int x, int y, int w, int h, int cx, int cy)
{
	put32(c, LC_WIN, x); put32(c, LC_WIN + 4, y); put32(c, LC_WIN + 8, w); put32(c, LC_WIN + 12, h);
	put64(c, LC_FB_CROP, (uint64_t)cx << 32); put64(c, LC_FB_CROP + 8, (uint64_t)cy << 32);
	put64(c, LC_FB_CROP + 16, (uint64_t)w << 32); put64(c, LC_FB_CROP + 24, (uint64_t)h << 32);
}

static void layer_setup(uint8_t *c, uint32_t *fb, int x, int y, int w, int h, int id)
{
	for (int i = 0; i < LAYER_CONFIG_SIZE; i++) c[i] = 0;
	c[LC_ZORDER] = 255; c[LC_ALPHA_VALUE] = 255;            /* buffer mode, per-pixel alpha, above the GUI (layer 0) */
	/* the display engine reads RAM by physical address: a virtual one makes it read outside RAM (it hung the
	 * device: logo only, reboot loop with CAN). The stock GUI converts the same way. */
	put64(c, LC_FB_ADDR, esMEMS_VA2PA(fb));
	put32(c, LC_FB_SIZE, w); put32(c, LC_FB_SIZE + 4, h);
	c[LC_FB_FORMAT] = DISP_FORMAT_ARGB_8888;
	layer_window(c, x, y, w, h, 0, 0);
	put32(c, LC_CHANNEL, 1); put32(c, LC_LAYER_ID, id);
}

static int layer_enable(uint8_t *c, int on)
{
	unsigned long arg[3] = { 0, (unsigned long)c, 1 };     /* screen, configs, count */
	c[LC_ENABLE] = (uint8_t)on;
	int r = (int)sys_ioctl(g_disp, DISP_LAYER_SET_CONFIG, arg);
	if (r) lg("layer %u enable=%d failed: %d", c[LC_LAYER_ID], on, r);
	return r;
}

/* ---- drawing into straight-alpha ARGB buffers ---- */
/* source-over of one pixel */
static void px_over(uint32_t *d, uint32_t sv)
{
	uint32_t sa = sv >> 24, dv = *d, da = dv >> 24;
	if (!sa) return;
	if (sa == 255 || !da) { *d = sv; return; }
	uint32_t ia = 255 - sa, oa = sa + da * ia / 255;
	uint32_t r = (((sv >> 16) & 255) * sa + ((dv >> 16) & 255) * da * ia / 255) / oa;
	uint32_t g = (((sv >> 8) & 255) * sa + ((dv >> 8) & 255) * da * ia / 255) / oa;
	uint32_t b = ((sv & 255) * sa + (dv & 255) * da * ia / 255) / oa;
	*d = oa << 24 | r << 16 | g << 8 | b;
}

/* an image at (x, y) of a fw x fh buffer, clipped to it */
static void blit(uint32_t *fb, int fw, int fh, const img_t *im, int x, int y)
{
	for (int j = 0; j < im->h; j++) {
		if ((unsigned)(y + j) >= (unsigned)fh) continue;
		for (int i = 0; i < im->w; i++)
			if ((unsigned)(x + i) < (unsigned)fw) {
				int k = j * im->w + i;
				px_over(&fb[(y + j) * fw + x + i], im->px ? im->px[k] : (uint32_t)im->a[k] << 24 | im->rgb);
			}
	}
}

/* next character of a UTF-8 string; a byte that does not start a valid sequence is taken as Latin-1 */
static MAYBE_UNUSED uint32_t utf8_next(const char **p, const char *end)
{
	const uint8_t *s = (const uint8_t *)*p;
	uint32_t c = *s;
	int n = c >= 0xf0 ? 3 : c >= 0xe0 ? 2 : c >= 0xc0 ? 1 : 0;
	if (n && s + n < (const uint8_t *)end + 1) {
		uint32_t v = c & (0x3f >> n);
		int ok = 1;
		for (int i = 1; i <= n; i++) { if ((s[i] & 0xc0) != 0x80) { ok = 0; break; } v = v << 6 | (s[i] & 0x3f); }
		if (ok) { *p += n + 1; return v; }
	}
	*p += 1;
	return c;
}

/* glyph of a character: printable ASCII first, then the font's extra characters; -1 = not in the font */
static MAYBE_UNUSED int glyph_of(const font_t *f, uint32_t c)
{
	if (c >= 32 && c < 127) return (int)c - 32;
	for (int i = 0; i < f->n_extra; i++) if (f->cp[i] == c) return 95 + i;
	return -1;
}

static MAYBE_UNUSED int text_width(const font_t *f, const char *t, int len)
{
	int w = 0;
	for (const char *p = t, *end = t + len; p < end;) { int g = glyph_of(f, utf8_next(&p, end)); if (g >= 0) w += f->w[g]; }
	return w;
}

/* UTF-8 text centred on cx in a transparent ARGB buffer of width fw (rows 0 .. f->h) */
static MAYBE_UNUSED void draw_text(uint32_t *fb, int fw, const font_t *f, const char *t, int len, int cx, uint32_t rgb)
{
	int x = cx - text_width(f, t, len) / 2;
	for (const char *p = t, *end = t + len; p < end;) {
		int g = glyph_of(f, utf8_next(&p, end));
		if (g < 0) continue;
		uint32_t i = f->off[g];                    /* 4-bit alpha, two pixels per byte, low nibble first */
		int gw = f->w[g];
		for (int y = 0; y < f->h; y++)
			for (int k = 0; k < gw; k++, i++) {
				uint32_t v = f->a[i >> 1] >> ((i & 1) * 4) & 15;
				if (v && (unsigned)(x + k) < (unsigned)fw) px_over(&fb[y * fw + x + k], v * 17 << 24 | rgb);
			}
		x += gw;
	}
}

/* longest start of t[0..n) that fits max_w (cut at a character, "..." appended); t needs 3 spare bytes */
static MAYBE_UNUSED int fit_text(const font_t *f, char *t, int n, int max_w)
{
	if (text_width(f, t, n) <= max_w) return n;
	const char ell[3] = { (char)0xe2, (char)0x80, (char)0xa6 };   /* "…" (on the stack: no .srodata) */
	int ew = text_width(f, ell, 3), len = n;
	while (len > 0 && text_width(f, t, len) + ew > max_w) {
		len--;
		while (len > 0 && ((uint8_t)t[len] & 0xc0) == 0x80) len--;    /* UTF-8 continuation byte */
	}
	while (len > 0 && t[len - 1] == ' ') len--;
	for (int i = 0; i < 3; i++) t[len + i] = ell[i];
	return len + 3;
}

/* coverage (0..255) of pixel (i, j) in a w x h rectangle with corner radius r, 4x4 samples */
static MAYBE_UNUSED uint32_t round_cov(int i, int j, int w, int h, int r)
{
	int cx = i < r ? r : i >= w - r ? w - r : -1, cy = j < r ? r : j >= h - r ? h - r : -1;
	if (cx < 0 || cy < 0) return 255;
	int in = 0;
	for (int sy = 0; sy < 4; sy++)
		for (int sx = 0; sx < 4; sx++) {
			int dx = (i - cx) * 8 + sx * 2 + 1, dy = (j - cy) * 8 + sy * 2 + 1;   /* 1/8 px units */
			if (dx * dx + dy * dy <= r * r * 64) in++;
		}
	return in * 255 / 16;
}

/* hue (0..359) -> RGB with saturation / value 0..255 */
static MAYBE_UNUSED uint32_t hue_rgb(int h, int s, int v)
{
	int f = h % 60 * 255 / 60, p = v * (255 - s) / 255, q = v * (255 - s * f / 255) / 255, t = v * (255 - s * (255 - f) / 255) / 255;
	int r, g, b;
	switch (h / 60) {
	case 0: r = v; g = t; b = p; break;
	case 1: r = q; g = v; b = p; break;
	case 2: r = p; g = v; b = t; break;
	case 3: r = p; g = q; b = v; break;
	case 4: r = t; g = p; b = v; break;
	default: r = v; g = p; b = q; break;
	}
	return (uint32_t)r << 16 | (uint32_t)g << 8 | (uint32_t)b;
}

/* ---- radio: learned station names, E:\climabar_ps.bin = "CBPS", count, {freq, name[8]} * count ---- */
#if RADIO_NAME || PRESET_NAMES
#define PS_FILE       "E:\\climabar_ps.bin"
#define PS_MAX        64
#define LEARN_TICKS   300     /* a new station: the name once it has been on air 3 s in total */
#define RELEARN_TICKS 3000    /* a known station: another name only after 30 s and twice as long as the stored one */
#define CAND_MAX      8       /* PS texts timed per station */

typedef struct { uint32_t freq; char name[8]; } ps_entry;
static struct { char magic[4]; uint32_t n; ps_entry e[PS_MAX]; } g_tab;
static uint32_t g_tab_gen;    /* bumped on every change of g_tab: the preset names are redrawn */

static MAYBE_UNUSED int radio_screen(void) { return app_is("Radio") && !*PTY_LIST_OPEN; }

static int trimmed(const char *ps)
{
	int len = 0;
	for (int i = 0; i < 8; i++) if (ps[i] && ps[i] != ' ') len = i + 1;
	return len;
}

static int same8(const char *a, const char *b) { for (int i = 0; i < 8; i++) if (a[i] != b[i]) return 0; return 1; }

static void tab_load(void)
{
	void *fp = esFSYS_fopen(PS_FILE, "rb");
	if (fp) { (void)esFSYS_fread(&g_tab, 1, sizeof g_tab, fp); esFSYS_fclose(fp); }
	if (g_tab.magic[0] != 'C' || g_tab.magic[1] != 'B' || g_tab.magic[2] != 'P' || g_tab.magic[3] != 'S' || g_tab.n > PS_MAX)
		{ g_tab.magic[0] = 'C'; g_tab.magic[1] = 'B'; g_tab.magic[2] = 'P'; g_tab.magic[3] = 'S'; g_tab.n = 0; }
}

static void tab_save(void)
{
	void *fp = esFSYS_fopen(PS_FILE, "wb");
	if (!fp) { lg("cannot write %s", PS_FILE); return; }
	(void)esFSYS_fwrite(&g_tab, 1, 8 + g_tab.n * sizeof(ps_entry), fp);
	esFSYS_fclose(fp);
}

static int tab_index(uint32_t freq)
{
	for (uint32_t i = 0; i < g_tab.n; i++) if (g_tab.e[i].freq == freq) return (int)i;
	return -1;
}

static void tab_learn(uint32_t freq, const char *ps)
{
	int i = tab_index(freq);
	if (i < 0) {
		if (g_tab.n == PS_MAX) {                          /* drop the oldest */
			for (i = 1; i < PS_MAX; i++) g_tab.e[i - 1] = g_tab.e[i];
			i = PS_MAX - 1;
		} else i = (int)g_tab.n++;
	}
	g_tab.e[i].freq = freq;
	for (int k = 0; k < 8; k++) g_tab.e[i].name[k] = ps[k];
	g_tab_gen++;
	tab_save();
}

/* Many stations rotate texts in the PS (name, song, slogans): every PS text is timed while it is on air, and the
 * station's name is the one on air longest in total. Only once the PS changed after tuning (not a leftover of the
 * previous station). */
static void learn_poll(const char *ps)
{
	static struct { char ps[8]; uint32_t t; } cand[CAND_MAX];
	static int ncand, fresh;
	static uint32_t freq, last;
	static char tune_ps[8];
	uint32_t f = RADIO_FREQ, now = esKRNL_TimeGet(), dt = now - last;
	last = now;
	if (dt > 10) dt = 10;
	if (f != freq) { freq = f; fresh = 0; ncand = 0; for (int k = 0; k < 8; k++) tune_ps[k] = ps[k]; }
	if (!fresh && (!trimmed(ps) || !same8(ps, tune_ps))) fresh = 1;
	if (!fresh || !trimmed(ps) || RADIO[0] > 2) return;
	int c = 0;
	while (c < ncand && !same8(cand[c].ps, ps)) c++;
	if (c == ncand) {
		if (ncand < CAND_MAX) ncand++;
		else {                                              /* full: replace the one on air shortest */
			c = 0;
			for (int k = 1; k < ncand; k++) if (cand[k].t < cand[c].t) c = k;
		}
		for (int k = 0; k < 8; k++) cand[c].ps[k] = ps[k];
		cand[c].t = 0;
	}
	cand[c].t += dt;
	int best = 0;
	for (int k = 1; k < ncand; k++) if (cand[k].t > cand[best].t) best = k;
	if (cand[best].t < LEARN_TICKS) return;
	int i = tab_index(f);
	if (i >= 0) {
		if (same8(g_tab.e[i].name, cand[best].ps)) return;
		uint32_t stored = 0;                                /* how long the stored name has been on air now */
		for (int k = 0; k < ncand; k++) if (same8(cand[k].ps, g_tab.e[i].name)) stored = cand[k].t;
		if (cand[best].t < RELEARN_TICKS || cand[best].t < 2 * stored) return;
	}
	tab_learn(f, cand[best].ps);
}
#endif

/* the frequency as the stock radio writes it: "87.50" (FM, 10 kHz units) or "531" (AM, kHz); returns its length */
static int freq_text(char *buf, uint32_t band, uint32_t f)
{
	char d[12];
	int n = 0, len = 0;
	uint32_t v = band <= 2 ? f / 100 : f;
	do { d[n++] = '0' + v % 10; v /= 10; } while (v);
	while (n) buf[len++] = d[--n];
	if (band <= 2) { buf[len++] = '.'; buf[len++] = '0' + f % 100 / 10; buf[len++] = '0' + f % 10; }
	return len;
}

/* Text of preset button i (0..5): init.axf's GUI calls this (through climabar_hooks in start.S, see
 * tools/patch_initaxf.py preset_names) instead of its own ViewShowStrSubFreq handler (e917714a), with the same
 * contract: buf is the control's text, rewritten only when the key in *cache changes, then *dirty = 1.
 * The firmware draws the text itself, so it is as stable as the stock button: the learned station name, or the
 * frequency like the stock handler ("%d.%02d" FM, "%d" AM). */
void preset_text(char *buf, long i, long unused, int32_t *cache, int32_t *dirty)
{
	uint32_t band = RADIO[0], f = RADIO_PRESET(i);
	int len = 0, t = -1;
	(void)unused;
#if PRESET_NAMES
	if (band <= 2) t = tab_index(f);
	int32_t key = (int32_t)(f | band << 16 | (g_tab_gen & 0xff) << 24);
#else
	int32_t key = (int32_t)(f | band << 16);
#endif
	if (*cache == key) return;
	*cache = key;
	*dirty = 1;
	if (t >= 0) {
#if PRESET_NAMES
		const char *nm = g_tab.e[t].name;
		len = trimmed(nm);
		for (int k = 0; k < len; k++) buf[k] = nm[k];
#endif
	} else len = freq_text(buf, band, f);
	buf[len] = 0;
}

/* ---- overlay: one full-screen layer (ch1, layer 2) for everything outside the climate strip ---- */
#if OVERLAY
#define OV_W 1024
#define OV_H 600
#define OV_PAGES ((OV_W * OV_H * 4 + 1023) / 1024)
static uint32_t *g_ofb;                /* what the overlay shows: straight-alpha ARGB, mostly transparent */
static uint32_t *g_dfb;                /* what the display reads (see ov_present) */
static uint8_t g_ocfg[LAYER_CONFIG_SIZE];
static int g_box[4] = { -1, 0, 0, 0 }; /* the overlay layer's window while enabled; x0 = -1: disabled */

static void ov_clear(int x, int y, int w, int h)
{
	for (int j = y < 0 ? 0 : y; j < y + h && j < OV_H; j++)
		for (int i = x < 0 ? 0 : x; i < x + w && i < OV_W; i++) g_ofb[j * OV_W + i] = 0;
}

static MAYBE_UNUSED void ov_blit(const img_t *im, int x, int y) { blit(g_ofb, OV_W, OV_H, im, x, y); }

/* pixel k of an image, ARGB */
static uint32_t img_px(const img_t *im, int k) { return im->px ? im->px[k] : (uint32_t)im->a[k] << 24 | im->rgb; }

/* an image drawn pct percent of its size at (x, y), bilinear: rarely drawn art shown larger without larger art in
 * memory. Colours are interpolated premultiplied by alpha, so edges do not darken. */
static MAYBE_UNUSED void ov_blit_scaled(const img_t *im, int x, int y, int pct)
{
	int dw = im->w * pct / 100, dh = im->h * pct / 100;
	for (int j = 0; j < dh; j++) {
		if ((unsigned)(y + j) >= OV_H) continue;
		int sy = (int)(((j * 2 + 1) * 100 * 128 / pct - 128) / 2);            /* source y, 1/128 px */
		if (sy < 0) sy = 0;
		int y0 = sy >> 7, fy = sy & 127, y1 = y0 + 1 < im->h ? y0 + 1 : y0;
		for (int i = 0; i < dw; i++) {
			if ((unsigned)(x + i) >= OV_W) continue;
			int sx = (int)(((i * 2 + 1) * 100 * 128 / pct - 128) / 2);
			if (sx < 0) sx = 0;
			int x0 = sx >> 7, fx = sx & 127, x1 = x0 + 1 < im->w ? x0 + 1 : x0;
			uint32_t p[4] = { img_px(im, y0 * im->w + x0), img_px(im, y0 * im->w + x1),
			                  img_px(im, y1 * im->w + x0), img_px(im, y1 * im->w + x1) };
			uint32_t wt[4] = { (128 - fx) * (128 - fy), fx * (128 - fy), (128 - fx) * fy, fx * fy };   /* sum 16384 */
			uint32_t a = 0, r = 0, g = 0, b = 0;
			for (int k = 0; k < 4; k++) {
				uint32_t pa = p[k] >> 24, w = wt[k] * pa;
				a += wt[k] * pa; r += w * (p[k] >> 16 & 255); g += w * (p[k] >> 8 & 255); b += w * (p[k] & 255);
			}
			if (a < 16384) continue;                                         /* alpha < 1 */
			uint32_t v = (a >> 14) << 24 | (r / a) << 16 | (g / a) << 8 | b / a;
			px_over(&g_ofb[(y + j) * OV_W + x + i], v);
		}
	}
}

static void overlay_init(void)
{
	g_ofb = esMEMS_Palloc(OV_PAGES);
	g_dfb = esMEMS_Palloc(OV_PAGES);
	if (!g_ofb || !g_dfb) { lg("overlay: no memory"); g_ofb = 0; return; }
	for (int i = 0; i < OV_W * OV_H; i++) g_ofb[i] = g_dfb[i] = 0;
	esMEMS_CleanDCacheRegion(g_dfb, OV_W * OV_H * 4);
	layer_setup(g_ocfg, g_dfb, 0, 0, OV_W, OV_H, 2);
}

/* The D1s display engine does not alpha-blend layers of the same channel: inside its window the overlay simply
 * replaces the GUI layer (channel 1, layer 0), transparent pixels included - they came out black on the device.
 * So the overlay layer only covers the box around what is shown, and there it shows the GUI's own pixels with our
 * drawing blended on top, opaque. Without a GUI layer (Android Auto / CarPlay video on channel 0, which IS blended
 * with channel 1) the plain transparent drawing is shown. Called every poll while something is shown. */
static void ov_present(int x0, int y0, int x1, int y1)
{
	uint8_t gui[LAYER_CONFIG_SIZE];
	for (int i = 0; i < LAYER_CONFIG_SIZE; i++) gui[i] = 0;
	put32(gui, LC_CHANNEL, 1); put32(gui, LC_LAYER_ID, 0);
	unsigned long arg[3] = { 0, (unsigned long)gui, 1 };
	sys_ioctl(g_disp, DISP_LAYER_GET_CONFIG, arg);
	const uint8_t *src = (const uint8_t *)(uintptr_t)*(uint64_t *)(gui + LC_FB_ADDR);   /* heap: physical = virtual */
	int over_gui = gui[LC_ENABLE] && gui[LC_FB_FORMAT] == DISP_FORMAT_RGB_888 && in_ram((uintptr_t)src) &&
	               *(uint32_t *)(gui + LC_FB_SIZE) == OV_W && *(uint32_t *)(gui + LC_FB_SIZE + 4) == OV_H;
	int moved = x0 != g_box[0] || y0 != g_box[1] || x1 != g_box[2] || y1 != g_box[3];
	if (over_gui) {
		/* the GUI redraws in place (a button is cleared, then drawn): copy its pixels only when they are the same
		 * as one poll ago, else a half-drawn (black) moment would stay on screen until the next poll */
		static uint32_t last_sum;
		uint32_t sum = 0;
		/* the firmware draws parts of the GUI with the G2D engine, straight into RAM: without this the CPU can
		 * keep reading its old cached pixels (black, from before the redraw) for a while */
		esMEMS_CleanFlushDCacheRegion((void *)(src + y0 * OV_W * 3), (y1 - y0) * OV_W * 3);
		for (int y = y0; y < y1; y++) {
			const uint8_t *g = src + (y * OV_W + x0) * 3;
			for (int i = 0; i < (x1 - x0) * 3; i++) sum = sum * 31 + g[i];
		}
		int stable = sum == last_sum;
		last_sum = sum;
		if (!stable && !moved) return;
	}
	for (int y = y0; y < y1; y++) {
		const uint32_t *c = g_ofb + y * OV_W;
		uint32_t *d = g_dfb + y * OV_W;
		if (!over_gui) { for (int x = x0; x < x1; x++) d[x] = c[x]; continue; }
		const uint8_t *g = src + y * OV_W * 3;
		for (int x = x0; x < x1; x++) {
			uint32_t v = c[x], a = v >> 24;
			if (a == 255) { d[x] = v; continue; }
			uint32_t gb = g[3 * x], gg = g[3 * x + 1], gr = g[3 * x + 2], ia = 255 - a;   /* RGB888 in memory: B G R */
			d[x] = 0xff000000u | ((((v >> 16) & 255) * a + gr * ia) / 255) << 16 | ((((v >> 8) & 255) * a + gg * ia) / 255) << 8 |
			       (((v & 255) * a + gb * ia) / 255);
		}
	}
	esMEMS_CleanDCacheRegion(g_dfb + y0 * OV_W, (y1 - y0) * OV_W * 4);
	if (moved) {                                                     /* window = crop = the box */
		layer_window(g_ocfg, x0, y0, x1 - x0, y1 - y0, x0, y0);
		layer_enable(g_ocfg, 1);
		g_box[0] = x0; g_box[1] = y0; g_box[2] = x1; g_box[3] = y1;
	}
}

static MAYBE_UNUSED void box_add(int *b, int x, int y, int w, int h)
{
	if (x < b[0]) b[0] = x;
	if (y < b[1]) b[1] = y;
	if (x + w > b[2]) b[2] = x + w;
	if (y + h > b[3]) b[3] = y + h;
}

/* called from the UI loop every 50 ms; cs = the climate block (doors), or 0 */
static void overlay_poll(const uint8_t *cs)
{
	static int on, name_on, door_on, door_shown, bt_on, np_on;
	int dirty = 0;
	(void)cs; (void)dirty; (void)door_shown; (void)bt_on; (void)np_on;
	if (!g_ofb) return;

#if RADIO_NAME
	{   /* where the stock radio screen has the big frequency (its digits are moved away by radio/build_radio.py):
		 * the live RDS PS, changing as the station sends it, or the frequency while there is none; same font and
		 * size as the stock digits */
		static char shown[12];
		char t[12], ps[8];
		int len = 0;
		for (int i = 0; i < 8; i++) ps[i] = RADIO_PS[i];
		if (radio_screen()) {
			int b = 0, e = RADIO[0] <= 2 ? trimmed(ps) : 0;      /* the PS without its padding */
			while (b < e && ps[b] == ' ') b++;
			for (int i = b; i < e; i++) t[len++] = ps[i];
			if (!len) len = freq_text(t, RADIO[0], RADIO_FREQ);
		}
		if (len > 11) len = 11;
		t[len] = 0;
		int same = 1;
		for (int i = 0; i <= len; i++) if (t[i] != shown[i]) { same = 0; break; }
		if (len && (!name_on || !same)) {
			ov_clear(RADIO_NAME_X, RADIO_NAME_Y, RADIO_NAME_W, FONT_NAME.h);
			draw_text(g_ofb + RADIO_NAME_Y * OV_W + RADIO_NAME_X, OV_W, &FONT_NAME, t, len, RADIO_NAME_W / 2, RADIO_NAME_COLOR);
			for (int i = 0; i <= len; i++) shown[i] = t[i];
			name_on = dirty = 1;
		} else if (!len && name_on) {
			ov_clear(RADIO_NAME_X, RADIO_NAME_Y, RADIO_NAME_W, FONT_NAME.h);
			shown[0] = 0; name_on = 0; dirty = 1;
		}
	}
#endif

#if DOORS
#define DS(v)   ((v) * DOORS_SCALE / 100)                     /* art coordinates -> screen, at the card's scale */
#define DOORS_W DS(IMG_DOOR_CARD.w)
#define DOORS_H DS(IMG_DOOR_CARD.h)
	{   /* car card while a door / the boot is open, kept DOORS_HIDE_TICKS after everything is closed */
		static uint32_t door_until;
		int doors = 0;
		uint32_t now = esKRNL_TimeGet();
		/* the full Vehicle information page already shows the car */
		if (cs && !(app_is("Can") && CAN_PAGE == 201))
			doors = (field(cs, AC_DOOR_FL) != 0) | (field(cs, AC_DOOR_FR) != 0) << 1 | (field(cs, AC_DOOR_RL) != 0) << 2 |
			        (field(cs, AC_DOOR_RR) != 0) << 3 | (field(cs, AC_BOOT) != 0) << 4;
		if (doors) door_until = now + DOORS_HIDE_TICKS;
		int want = doors || (door_on && (int32_t)(now - door_until) < 0);
		if (want != door_on || (want && (doors != door_shown || dirty))) {
			ov_clear(DOORS_X, DOORS_Y, DOORS_W, DOORS_H);
			if (want) {
				ov_blit_scaled(&IMG_DOOR_CARD, DOORS_X, DOORS_Y, DOORS_SCALE);
				if (doors & 1) ov_blit_scaled(&IMG_DOOR_FL, DOORS_X + DS(DOOR_FL_X), DOORS_Y + DS(DOOR_FL_Y), DOORS_SCALE);
				if (doors & 2) ov_blit_scaled(&IMG_DOOR_FR, DOORS_X + DS(DOOR_FR_X), DOORS_Y + DS(DOOR_FR_Y), DOORS_SCALE);
				if (doors & 4) ov_blit_scaled(&IMG_DOOR_RL, DOORS_X + DS(DOOR_RL_X), DOORS_Y + DS(DOOR_RL_Y), DOORS_SCALE);
				if (doors & 8) ov_blit_scaled(&IMG_DOOR_RR, DOORS_X + DS(DOOR_RR_X), DOORS_Y + DS(DOOR_RR_Y), DOORS_SCALE);
				if (doors & 16) ov_blit_scaled(&IMG_DOOR_BOOT, DOORS_X + DS(DOOR_BOOT_X), DOORS_Y + DS(DOOR_BOOT_Y), DOORS_SCALE);
			} else {
				name_on = 0;                              /* the card covered it: redraw next poll */
			}
			door_on = want; door_shown = doors; dirty = 1;
		}
	}
#endif

#if NOW_PLAYING
	{   /* a card with a generated cover, title and artist for a few seconds when the BT song changes */
		static char key[96];
		static uint32_t np_until;
		const uint8_t *o = *BT_OBJ_PTR;
		char title[160], artist[160];
		int tn = 0, an = 0;
		uint32_t h = 2166136261u;                  /* FNV-1a of the album (or artist): the cover colour */
		if (in_ram((uintptr_t)o)) {
			for (; tn < 150 && o[BT_ID3_TITLE + tn]; tn++) title[tn] = (char)o[BT_ID3_TITLE + tn];
			for (; an < 150 && o[BT_ID3_TITLE + 0x100 + an]; an++) artist[an] = (char)o[BT_ID3_TITLE + 0x100 + an];
			const uint8_t *al = o + BT_ID3_TITLE + 0x200;
			if (!al[0]) al = o + BT_ID3_TITLE + 0x100;
			for (int i = 0; i < 150 && al[i]; i++) h = (h ^ al[i]) * 16777619u;
		}
		/* song identity: title + artist (only the first bytes; enough to notice a change) */
		char k[96];
		int kn = 0;
		for (int i = 0; i < tn && kn < 60; i++) k[kn++] = title[i];
		k[kn++] = 1;
		for (int i = 0; i < an && kn < 94; i++) k[kn++] = artist[i];
		k[kn] = 0;
		int changed = 0;
		for (int i = 0; i <= kn; i++) if (k[i] != key[i]) { changed = 1; break; }
		uint32_t now = esKRNL_TimeGet();
		int blocked = (app_is("Bt") && BT_PAGE == 201) || (NP_HIDE_IN_PROJECTION && app_is("Link"));
		if (changed) {
			for (int i = 0; i <= kn; i++) key[i] = k[i];
			if (tn && !blocked) {
				np_until = now + NP_TICKS;
				for (int j = 0; j < NP_H; j++)        /* card */
					for (int i = 0; i < NP_W; i++)
						g_ofb[(NP_Y + j) * OV_W + NP_X + i] = (NP_ALPHA * round_cov(i, j, NP_W, NP_H, 14) / 255) << 24 | NP_BG;
				int cx0 = NP_X + 8, cy0 = NP_Y + (NP_H - NP_COVER) / 2, hue = h % 360;
				uint32_t c1 = hue_rgb(hue, 170, 210), c2 = hue_rgb((hue + 40) % 360, 200, 120);
				for (int j = 0; j < NP_COVER; j++)    /* cover: diagonal gradient, rounded */
					for (int i = 0; i < NP_COVER; i++) {
						int t = (i + j) * 255 / (2 * NP_COVER - 2);
						uint32_t r = (((c1 >> 16) & 255) * (255 - t) + ((c2 >> 16) & 255) * t) / 255;
						uint32_t g = (((c1 >> 8) & 255) * (255 - t) + ((c2 >> 8) & 255) * t) / 255;
						uint32_t b = ((c1 & 255) * (255 - t) + (c2 & 255) * t) / 255;
						px_over(&g_ofb[(cy0 + j) * OV_W + cx0 + i], round_cov(i, j, NP_COVER, NP_COVER, 10) << 24 | r << 16 | g << 8 | b);
					}
				ov_blit(&IMG_NP_NOTE, cx0 + (NP_COVER - IMG_NP_NOTE.w) / 2, cy0 + (NP_COVER - IMG_NP_NOTE.h) / 2);
				int tx = cx0 + NP_COVER + 14, tw = NP_X + NP_W - 14 - tx;
				int len = fit_text(&FONT_BT_TITLE, title, tn, tw);
				draw_text(g_ofb + (NP_Y + 3) * OV_W, OV_W, &FONT_BT_TITLE, title, len,
				          tx + text_width(&FONT_BT_TITLE, title, len) / 2, NP_TITLE_COLOR);
				len = fit_text(&FONT_BT_TITLE, artist, an, tw);
				draw_text(g_ofb + (NP_Y + NP_H - FONT_BT_TITLE.h - 3) * OV_W, OV_W, &FONT_BT_TITLE, artist, len,
				          tx + text_width(&FONT_BT_TITLE, artist, len) / 2, NP_ARTIST_COLOR);
				np_on = dirty = 1;
			}
		}
		if (np_on && (blocked || (int32_t)(now - np_until) >= 0)) {
			ov_clear(NP_X, NP_Y, NP_W, NP_H);
			np_on = 0; dirty = 1;
		}
	}
#endif

#if BT_TITLE
	{   /* BT Music: the song title from the phone in the title bar (the stock "Title" is moved off screen) */
		static char shown[160];
		int want = app_is("Bt") && BT_PAGE == 201;
		char t[160];
		int n = 0;
		if (want) {
			const uint8_t *o = *BT_OBJ_PTR;
			if (in_ram((uintptr_t)o)) for (; n < 150 && o[BT_ID3_TITLE + n]; n++) t[n] = (char)o[BT_ID3_TITLE + n];
			if (!n) for (; BT_TITLE_EMPTY[n]; n++) t[n] = BT_TITLE_EMPTY[n];
		}
		t[n] = 0;
		int changed = want != bt_on;
		for (int i = 0; want && !changed && i <= n; i++) if (t[i] != shown[i]) changed = 1;
		if (changed) {
			ov_clear(BT_TITLE_CX - BT_TITLE_W / 2, BT_TITLE_Y, BT_TITLE_W, FONT_BT_TITLE.h);
			if (want) {
				for (int i = 0; i <= n; i++) shown[i] = t[i];
				int len = fit_text(&FONT_BT_TITLE, t, n, BT_TITLE_W);
				draw_text(g_ofb + BT_TITLE_Y * OV_W, OV_W, &FONT_BT_TITLE, t, len, BT_TITLE_CX, BT_TITLE_COLOR);
			}
			bt_on = want; dirty = 1;
		}
	}
#endif

	int any = name_on || door_on || bt_on || np_on;
	if (any) {
		int b[4] = { OV_W, OV_H, 0, 0 };
#if RADIO_NAME
		if (name_on) box_add(b, RADIO_NAME_X, RADIO_NAME_Y, RADIO_NAME_W, FONT_NAME.h);
#endif
#if DOORS
		if (door_on) box_add(b, DOORS_X, DOORS_Y, DOORS_W, DOORS_H);
#endif
#if NOW_PLAYING
		if (np_on) box_add(b, NP_X, NP_Y, NP_W, NP_H);
#endif
#if BT_TITLE
		if (bt_on) box_add(b, BT_TITLE_CX - BT_TITLE_W / 2, BT_TITLE_Y, BT_TITLE_W, FONT_BT_TITLE.h);
#endif
		if (b[0] < 0) b[0] = 0;
		if (b[1] < 0) b[1] = 0;
		if (b[2] > OV_W) b[2] = OV_W;
		if (b[3] > OV_H) b[3] = OV_H;
		if (b[2] > b[0] && b[3] > b[1]) ov_present(b[0], b[1], b[2], b[3]);
	}
	if (any != on) { if (!any) { layer_enable(g_ocfg, 0); g_box[0] = -1; } on = any; }
}

static void overlay_off(void) { if (g_ofb && g_box[0] >= 0) layer_enable(g_ocfg, 0); }
#endif /* OVERLAY */

/* ---- the climate strip ---- */
static uint32_t *g_fb;                 /* W x H */
static uint8_t g_cfg[LAYER_CONFIG_SIZE];

/* show the top `v` rows of the strip at the bottom of the screen (v = H: fully in place) */
static void strip_offset(int v, int on)
{
	layer_window(g_cfg, 0, Y0 + H - v, W, v, 0, 0);
	layer_enable(g_cfg, on);
}

/* slide the strip in from the bottom edge (dir = 1) or back out (dir = -1), easing out */
static void slide(int dir)
{
	for (int i = 1; i < SLIDE_STEPS; i++) {
		int t = i * 1000 / SLIDE_STEPS, e = 1000 - (1000 - t) * (1000 - t) / 1000;   /* ease-out, 0..1000 */
		int v = H * e / 1000;
		v = dir > 0 ? v : H - v;
		strip_offset(v ? v : 1, 1);
		esKRNL_TimeDly(1);
	}
	strip_offset(H, dir > 0);
}

static void strip_show(int on)
{
	if (SLIDE_STEPS) slide(on ? 1 : -1);
	else strip_offset(H, on);
}

/* temperature in the stock image font: "22.0°C", "LO", "HI" */
static void draw_temp(uint8_t code, int x, int y, int right_align)
{
	static const img_t *const digit[10] = { &IMG_DIGIT_0, &IMG_DIGIT_1, &IMG_DIGIT_2, &IMG_DIGIT_3, &IMG_DIGIT_4,
	                                        &IMG_DIGIT_5, &IMG_DIGIT_6, &IMG_DIGIT_7, &IMG_DIGIT_8, &IMG_DIGIT_9 };
	const img_t *glyph[6];
	int n = 0, w = 0;
	if (IS_TEMP_LO(code)) glyph[n++] = &IMG_TEMP_LO;
	else if (IS_TEMP_HI(code)) glyph[n++] = &IMG_TEMP_HI;
	else {
		int t10 = 175 + 5 * code;            /* 17.5 + 0.5 * code, in tenths of a degree */
		if (t10 >= 100) glyph[n++] = digit[t10 / 100 % 10];
		glyph[n++] = digit[t10 / 10 % 10];
		glyph[n++] = &IMG_DOT;
		glyph[n++] = digit[t10 % 10];
		glyph[n++] = &IMG_CELSIUS;
	}
	for (int k = 0; k < n; k++) w += glyph[k]->w;
	if (right_align) x -= w;
	for (int k = 0; k < n; k++) { blit(g_fb, W, H, glyph[k], x, y + IMG_DIGIT_0.h - glyph[k]->h); x += glyph[k]->w; }
}

enum center { CENTER_FAN, CENTER_AIRFLOW };

static void draw(const uint8_t *s, enum center center)
{
	static const img_t *const bar_on[7] = { &IMG_FAN_BAR1_ON, &IMG_FAN_BAR2_ON, &IMG_FAN_BAR3_ON, &IMG_FAN_BAR4_ON,
	                                        &IMG_FAN_BAR5_ON, &IMG_FAN_BAR6_ON, &IMG_FAN_BAR7_ON };
	static const img_t *const bar_off[7] = { &IMG_FAN_BAR1_OFF, &IMG_FAN_BAR2_OFF, &IMG_FAN_BAR3_OFF, &IMG_FAN_BAR4_OFF,
	                                         &IMG_FAN_BAR5_OFF, &IMG_FAN_BAR6_OFF, &IMG_FAN_BAR7_OFF };
	for (int i = 0; i < W * H; i++) g_fb[i] = STRIP_BG;

	/* the middle shows either the fan speed or the airflow (several directions can be active) */
	if (center == CENTER_FAN) {
		blit(g_fb, W, H, &IMG_FAN_PANEL, FAN_PANEL_X, FAN_PANEL_Y);
		for (int k = 0; k < FAN_BARS && k < 7; k++)
			blit(g_fb, W, H, k < s[AC_FAN] ? bar_on[k] : bar_off[k], FAN_PANEL_X + FAN_BAR_POS[k][0], FAN_PANEL_Y + FAN_BAR_POS[k][1]);
	} else {
		/* one Material Symbols pictogram per combination: windshield << 2 | face << 1 | feet */
		static const img_t *const flow[8] = {
			&IMG_AIRFLOW_NONE, &IMG_AIRFLOW_FEET, &IMG_AIRFLOW_FACE, &IMG_AIRFLOW_FACE_FEET,
			&IMG_AIRFLOW_WS, &IMG_AIRFLOW_WS_FEET, &IMG_AIRFLOW_WS_FACE, &IMG_AIRFLOW_WS_FACE_FEET };
		int k = (field(s, AC_FLOW_WINDSHIELD) != 0) << 2 | (field(s, AC_FLOW_FACE) != 0) << 1 | (field(s, AC_FLOW_FEET) != 0);
		blit(g_fb, W, H, flow[k], AIRFLOW_X, AIRFLOW_Y);
	}

	draw_temp(s[AC_TEMP_L], TEMP_LEFT_X, TEMP_LEFT_Y, TEMP_LEFT_RIGHT_ALIGN);
	draw_temp(s[AC_TEMP_R], TEMP_RIGHT_X, TEMP_RIGHT_Y, TEMP_RIGHT_RIGHT_ALIGN);

	/* status icons: lit while the function is on, dimmed otherwise */
#define ICON(name, on) blit(g_fb, W, H, (on) ? &IMG_##name##_ON : &IMG_##name##_OFF, ICON_##name##_X, ICON_##name##_Y)
	ICON(AC, field(s, AC_ON));
	ICON(SYNC, !field(s, AC_DUAL));      /* SYNC = not dual-zone */
	ICON(AUTO, field(s, AC_AUTOHIGH) || field(s, AC_AUTOLOW));
	/* air intake, always lit: fresh air, or recirculation (automatic: "REC A") */
	blit(g_fb, W, H, !field(s, AC_CYCLE) ? &IMG_FRESH_ON : field(s, AC_AUTOCYCLE) ? &IMG_RECIRC_AUTO_ON : &IMG_RECIRC_ON,
	     ICON_RECIRC_X, ICON_RECIRC_Y);
	ICON(MAX_FRONT, field(s, AC_MAXFRONT));
	ICON(REAR_DEFROST, field(s, AC_REARLIGHT));
#undef ICON

	esMEMS_CleanDCacheRegion(g_fb, FB_BYTES);
}

/* ---- the module's thread ---- */
/* Wireless Android Auto only from the Auto button, Bluetooth music otherwise.
 * The phone offers Android Auto once, when its Bluetooth connects; the firmware ignores the offer unless the Auto
 * screen ("Link") is open (patch_initaxf.py no_startup_link). The Bluetooth connection is renewed (AT#CD, then AT#CC =
 * connect the last phone, as the BT Setup buttons do) when:
 *  - the Auto screen is open and no projection starts within AA_WAIT: the phone offers Android Auto again, and the
 *    open screen takes it (once per visit of the screen);
 *  - a projection ended on the Auto screen (disconnected from the phone) and the screen is left: the phone, still
 *    holding its media for Android Auto, gives it back to Bluetooth music. Not while the Auto screen is open, where
 *    the new offer would start Android Auto again.
 * A session is seen in the Android Auto link's state, set by the event callback init.axf gives wireless.mod. After a
 * renewal the phone needs some seconds to start Android Auto: no second renewal within AA_START. */
#define AA_WAIT     300                /* 3 s */
#define AA_BT_DOWN  500                /* give up waiting for the disconnect after 5 s */
#define AA_START    3000               /* 30 s */
static void aa_manage(int bt)
{
	static int waiting, projecting, renew_on_leave, renewing, last_link;
	static uint32_t since, renewed_at;
	uint32_t now = esKRNL_TimeGet();
	int in_link = app_is("Link");
	const uint8_t *links = *LINKS_PTR;
	int proj = in_ram((uintptr_t)links) && *(const int32_t *)(links + LINK_AA_WIRELESS * 2048 + LINK_ACTIVE) > 0;
	if (last_link && !proj) renew_on_leave = 1;                /* the session ended, wherever */
	last_link = proj;

	if (renewing) {                    /* disconnect sent: reconnect once it is down (never leave the phone off) */
		if (bt == 2 && (int32_t)(now - since) < AA_BT_DOWN) return;
		BT_SEND("AT#CC");
		renewing = 0; renewed_at = now;
		return;
	}
	if (!in_link) {
		if (renew_on_leave && bt == 2) {
			BT_SEND("AT#CD");
			renewing = 1; since = now;
		}
		renew_on_leave = waiting = projecting = 0;
		return;
	}
	if (proj != projecting) {
		if (!proj) renew_on_leave = 1;
		projecting = proj; waiting = 0;
		return;
	}
	if (projecting || renew_on_leave) return;
	if (!waiting) { waiting = 1; since = now; return; }
	if (waiting == 1 && (int32_t)(now - since) >= AA_WAIT) {
		waiting = 2;                   /* once per visit */
		if (bt != 2) return;           /* no phone on Bluetooth: nothing to renew */
		if (renewed_at && (int32_t)(now - renewed_at) < AA_START) return;
		BT_SEND("AT#CD");
		renewing = 1; since = now;
	}
}

static void ui_thread(void *arg)
{
	uint8_t last[AC_SNAPSHOT];
	uint32_t hide_at = 0;
	int shown = 0, primed = 0;
	unsigned polls = 0;
	enum center center = CENTER_DEFAULT_AIRFLOW ? CENTER_AIRFLOW : CENTER_FAN;
	(void)arg;
	esKRNL_TaskNameSet(EXEC_prioself, "climabar");

	/* safety: let the app (and its USB firmware update) start first; with an update stick in (Update\8369HD.img
	 * on any USB drive), do nothing at all - restoring the original firmware then runs exactly as stock */
	esKRNL_TimeDly(START_DELAY_TICKS);
	if (update_stick_present()) goto out;
	log_open();
	lg("climabar start (log on %c:)", g_log_path[0]);
	if (!firmware_ok()) { lg("stop: unknown init.axf"); goto out; }

	g_disp = sys_open("/dev/disp", 2);
	g_fb = esMEMS_Palloc(FB_PAGES);
	if (g_disp < 0 || !g_fb) { lg("stop: disp fd=%d strip fb=%x", g_disp, (unsigned long)g_fb); goto out; }
	layer_setup(g_cfg, g_fb, 0, Y0, W, H, 1);
#if RADIO_NAME || PRESET_NAMES
	tab_load();
#endif
#if OVERLAY
	overlay_init();
#endif

	while (!g_quit) {
		const uint8_t *s = *CLIMATE_PTR;
		int on_page = climate_page_open();
		if (s) {
			int changed = 0, fan_changed = 0, flow_changed = 0;
			for (int i = 0; i < AC_SNAPSHOT; i++)
				if (s[i] != last[i]) {
					changed = 1;
					if (i == AC_FAN) fan_changed = 1;
					if (i >= AC_FLOW_WINDSHIELD && i < AC_FLOW_FEET + 4) flow_changed = 1;
					last[i] = s[i];
				}
			if (changed && primed && !on_page) {   /* ignore the first read at start-up */
				/* show what was just changed; a new popup for anything else starts with the default */
				if (fan_changed) center = CENTER_FAN;
				else if (flow_changed) center = CENTER_AIRFLOW;
				else if (!shown) center = CENTER_DEFAULT_AIRFLOW ? CENTER_AIRFLOW : CENTER_FAN;
				draw(s, center);
				if (!shown) { strip_show(1); shown = 1; }
				hide_at = esKRNL_TimeGet() + SHOW_TICKS;
			}
			primed = 1;
		}
		if (shown && (on_page || (int32_t)(esKRNL_TimeGet() - hide_at) >= 0)) { strip_show(0); shown = 0; }

#if BELT
		{   /* the status bar's own seat-belt control (ViewShowImageDashSeatBelt) shows its symbol while BELT_WARN is
			 * non-zero: the firmware draws it, so the volume popup covers it like the other status symbols */
			int belts = 0;
			if (s && !(BELT_HIDE_IN_PROJECTION && app_is("Link")))
				belts = field(s, AC_BELT_DRIVER) != 0 || field(s, AC_BELT_PASSENGER) != 0;
			if (BELT_WARN != belts) BELT_WARN = belts;
		}
#endif
#if RADIO_NAME || PRESET_NAMES
		{
			char ps[8];
			for (int i = 0; i < 8; i++) ps[i] = RADIO_PS[i];
			learn_poll(ps);
		}
#endif
#if OVERLAY
		overlay_poll(s);
#endif
		{
			const uint8_t *bto = *BT_OBJ_PTR;
			aa_manage(in_ram((uintptr_t)bto) ? bto[12] : 254);
		}

		/* first 3 minutes, every 2 s: an update stick stops the module; a log stick put in late starts the log */
		if (++polls % 40 == 0 && polls <= 3600) {
			if (update_stick_present()) { lg("update stick found: stopping"); break; }
			if (!g_log_path[0]) { log_open(); lg("climabar log started late (on %c:)", g_log_path[0]); }
		}
		log_flush();
		esKRNL_TimeDly(5);                     /* poll every 50 ms */
	}
	if (shown) strip_offset(H, 0);
#if OVERLAY
	overlay_off();
#endif
#if BELT
	BELT_WARN = 0;
#endif
	log_flush();
out:
	esKRNL_TDel(EXEC_prioself);
}

int32_t CB_MInit(void)
{
	esKRNL_TCreate(ui_thread, 0, 0x2000, KRNL_priolevel5);
	return 0;
}
int32_t CB_MExit(void) { g_quit = 1; return 0; }
melis_mp *CB_MOpen(uint32_t mid, uint32_t mode) { (void)mode; g_mp.mid = (uint8_t)mid; return &g_mp; }
int32_t CB_MClose(melis_mp *mp) { (void)mp; return 0; }
uint32_t CB_MRead(void *p, uint32_t s, uint32_t n, melis_mp *mp) { (void)p; (void)s; (void)n; (void)mp; return 0; }
uint32_t CB_MWrite(const void *p, uint32_t s, uint32_t n, melis_mp *mp) { (void)p; (void)s; (void)n; (void)mp; return 0; }
long CB_MIoctrl(melis_mp *mp, uint32_t cmd, int32_t aux, void *buf) { (void)mp; (void)cmd; (void)aux; (void)buf; return 0; }

const melis_magic modinfo __attribute__((section(".magic"), used)) = {
	{ 'e', 'P', 'D', 'K', '.', 'm', 'o', 'd' }, 0x01000000, 0x90, 0xF0000, 0x400,   /* type 0x90: EMOD_TYPE_EXTERNAL_MODS */
	{ CB_MInit, CB_MExit, CB_MOpen, CB_MClose, CB_MRead, CB_MWrite, CB_MIoctrl },
};
