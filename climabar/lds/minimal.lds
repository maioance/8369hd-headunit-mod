/* The minimal test module (Makefile: minimal). Module type 0x90 (EMOD_TYPE_EXTERNAL_MODS): loaded at 0xe9000000, free up to init.axf (0xe9100000).
 * 0x8d/0x8e are taken on the 8369HD: wireless.mod (0x8c) spans 0xe8c00000-0xe8e3f510. */
MEMORY
{
    dram0_0_seg (RWX) :  org = 0xc2000000, len = 0x4000000
    dram0_1_seg (RWX) :  org = 0xe0000000, len = 0x10000000
    dram0_2_seg (RWX) :  org = 0xe9000000, len = 0x100000
    magic_info_seg (R) : org = 0xffff0000, len = 0x100
}

INCLUDE configuration_riscv.lds

ENTRY(CB_MInit)
INCLUDE section.lds
