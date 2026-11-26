/* Diagnostic module: same name, type, load address and startup line as climabar.mod, but a few hundred bytes and
 * no display work. THREAD=1: creates and names its thread exactly like climabar.mod, then sleeps. */
#include <stdint.h>
#include "melis.h"

static melis_mp g_mp;

#if THREAD
static void idle_thread(void *arg)
{
	(void)arg;
	esKRNL_TaskNameSet(0xff, "climabar");
	for (;;) esKRNL_TimeDly(1000);
}
int32_t CB_MInit(void) { esKRNL_TCreate(idle_thread, 0, 0x2000, KRNL_priolevel5); return 0; }
#else
int32_t CB_MInit(void) { return 0; }
#endif
int32_t CB_MExit(void) { return 0; }
melis_mp *CB_MOpen(uint32_t mid, uint32_t mode) { (void)mode; g_mp.mid = (uint8_t)mid; return &g_mp; }
int32_t CB_MClose(melis_mp *mp) { (void)mp; return 0; }
uint32_t CB_MRead(void *p, uint32_t s, uint32_t n, melis_mp *mp) { (void)p; (void)s; (void)n; (void)mp; return 0; }
uint32_t CB_MWrite(const void *p, uint32_t s, uint32_t n, melis_mp *mp) { (void)p; (void)s; (void)n; (void)mp; return 0; }
long CB_MIoctrl(melis_mp *mp, uint32_t cmd, int32_t aux, void *buf) { (void)mp; (void)cmd; (void)aux; (void)buf; return 0; }

const melis_magic modinfo __attribute__((section(".magic"), used)) = {
	{ 'e', 'P', 'D', 'K', '.', 'm', 'o', 'd' }, 0x01000000, 0x90, 0xF0000, 0x400,
	{ CB_MInit, CB_MExit, CB_MOpen, CB_MClose, CB_MRead, CB_MWrite, CB_MIoctrl },
};
