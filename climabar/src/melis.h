/* Minimal Melis kernel interface for a standalone module on the 8369HD firmware.
 * Syscall numbers come from the d1s-melis SDK (include/melis/ekernel/kapi.h, SWINO table);
 * the display layer layout is the one the firmware's /dev/disp driver uses (192 bytes,
 * enums packed to one byte), which differs from the SDK's sunxi_display2.h after fb.crop. */
#ifndef MELIS_H
#define MELIS_H

#include <stdint.h>

/* --- syscalls: a7 = number, a0..a5 = arguments, ecall */
long melis_sys(long nr, long a0, long a1, long a2, long a3);

#define SYS_KRNL_TCreate          0x10000100
#define SYS_KRNL_TDel             0x10000101
#define SYS_KRNL_TaskNameSet      0x10000107
#define SYS_KRNL_TimeDly          0x1000010c
#define SYS_KRNL_TimeGet          0x1000010f
#define SYS_MEMS_Palloc           0x10000200
#define SYS_MEMS_Pfree            0x10000201
#define SYS_MEMS_VA2PA            0x10000202
#define SYS_MEMS_CleanDCacheRegion 0x10000214
#define SYS_MEMS_CleanFlushDCacheRegion 0x10000215
#define SYS_FSYS_fopen            0x10000308
#define SYS_FSYS_fclose           0x10000302
#define SYS_FSYS_fread            0x1000030a
#define SYS_FSYS_fwrite           0x10000315
#define SYS_TIME_GetTime          0x10000905
#define SYS_TIME_GetDate          0x10000907
#define SYS_open_r                0x10001a01
#define SYS_close_r               0x10001a00
#define SYS_ioctl                 0x10001a1a

#define esKRNL_TCreate(fn, arg, stack, prio) melis_sys(SYS_KRNL_TCreate, (long)(fn), (long)(arg), (stack), (prio))
#define esKRNL_TDel(prio)            melis_sys(SYS_KRNL_TDel, (prio), 0, 0, 0)
#define esKRNL_TaskNameSet(tid, nm)  melis_sys(SYS_KRNL_TaskNameSet, (tid), (long)(nm), 0, 0)
#define esKRNL_TimeDly(ticks)        melis_sys(SYS_KRNL_TimeDly, (ticks), 0, 0, 0)     /* 1 tick = 10 ms */
#define esKRNL_TimeGet()             ((uint32_t)melis_sys(SYS_KRNL_TimeGet, 0, 0, 0, 0))
#define esMEMS_Palloc(pages)         ((void *)melis_sys(SYS_MEMS_Palloc, (pages), 0, 0, 0)) /* 1 KiB pages */
#define esMEMS_Pfree(p, pages)       melis_sys(SYS_MEMS_Pfree, (long)(p), (pages), 0, 0)
#define esMEMS_VA2PA(va)             ((unsigned long)melis_sys(SYS_MEMS_VA2PA, (long)(va), 0, 0, 0))
/* write the CPU's cached pixels back to RAM, where the display engine reads them. Not FlushDCacheRegion: on the
 * C906 that only invalidates (drops what was drawn but still in the cache) */
#define esMEMS_CleanDCacheRegion(p, n) melis_sys(SYS_MEMS_CleanDCacheRegion, (long)(p), (n), 0, 0)
/* write back and drop the cached copy: the next read comes from RAM (memory another master such as G2D writes) */
#define esMEMS_CleanFlushDCacheRegion(p, n) melis_sys(SYS_MEMS_CleanFlushDCacheRegion, (long)(p), (n), 0, 0)
#define esFSYS_fopen(path, mode)     ((void *)melis_sys(SYS_FSYS_fopen, (long)(path), (long)(mode), 0, 0))
#define esFSYS_fclose(fp)            melis_sys(SYS_FSYS_fclose, (long)(fp), 0, 0, 0)
#define esFSYS_fread(buf, sz, n, fp)  ((uint32_t)melis_sys(SYS_FSYS_fread, (long)(buf), (sz), (n), (long)(fp)))
#define esFSYS_fwrite(buf, sz, n, fp) ((uint32_t)melis_sys(SYS_FSYS_fwrite, (long)(buf), (sz), (n), (long)(fp)))
#define esTIME_GetTime(t)            melis_sys(SYS_TIME_GetTime, (long)(t), 0, 0, 0)   /* u8 hour, minute, second */
#define esTIME_GetDate(d)            melis_sys(SYS_TIME_GetDate, (long)(d), 0, 0, 0)   /* u16 year; u8 month, day */
#define sys_open(path, flags)        ((int)melis_sys(SYS_open_r, 0, (long)(path), (flags), 0))
#define sys_ioctl(fd, cmd, arg)      melis_sys(SYS_ioctl, (fd), (cmd), (long)(arg), 0)

#define EXEC_prioself  0xff
#define KRNL_priolevel5 0x15

/* --- module descriptor (MAGIC section) */
typedef struct { uint8_t mid; uint8_t pad[7]; } melis_mp;
typedef struct {
	char magic[8];        /* "ePDK.mod" */
	uint32_t version;
	uint32_t type;        /* load address = 0xe0000000 + type * 1 MiB */
	uint32_t heapaddr;
	uint32_t heapsize;
	void *mif[7];         /* MInit, MExit, MOpen, MClose, MRead, MWrite, MIoctrl */
} melis_magic;

/* --- /dev/disp layer configuration */
#define DISP_LAYER_SET_CONFIG 0x47
#define DISP_LAYER_GET_CONFIG 0x48
#define DISP_FORMAT_RGB_888   0x08
#define DISP_FORMAT_ARGB_8888 0x00
#define LAYER_CONFIG_SIZE     192
enum {
	LC_MODE = 0, LC_ZORDER = 1, LC_ALPHA_MODE = 2, LC_ALPHA_VALUE = 3,
	LC_WIN = 4,                     /* s32 x, y; u32 w, h */
	LC_FB_ADDR = 24,                /* u64 addr[3] */
	LC_FB_SIZE = 48,                /* u32 w, h (plane 0) */
	LC_FB_FORMAT = 84, LC_FB_PREMUL = 100,
	LC_FB_CROP = 104,               /* s64 x, y, w, h in 32.32 fixed point */
	LC_ENABLE = 176, LC_CHANNEL = 180, LC_LAYER_ID = 184,
};

#endif
