/* long melis_sys(long nr, long a0, long a1, long a2, long a3): Melis syscall via ecall.
 * The kernel returns from a syscall by jumping into the handler with ra = (address of ecall) + 4, so ra is lost:
 * keep it on the stack around ecall, like the firmware's own stubs. (Without this, `ret` jumped to itself and the
 * first syscall - creating the thread from MInit, during startup.sh - hung the boot.) */
	.section .text

/* Fixed entry points at the start of the module (0xe9000000, checked by lds/climabar.lds): init.axf calls them
 * directly once tools/patch_initaxf.py has put their addresses in its tables, so they must not move.
 * 0xe9000000 + 8 * i: text of preset button i+1 (ViewShowStrSubFreq<i+1>), see preset_text in climabar.c */
#ifndef MINIMAL                            /* the minimal test module (make minimal) has no hooks */
	.globl climabar_hooks
climabar_hooks:
	.irp i, 0, 1, 2, 3, 4, 5
	.balign 8
	li	a1, \i
	j	preset_text
	.endr
	.balign 8
#endif

	.globl melis_sys
	.type melis_sys, @function
melis_sys:
	addi	sp, sp, -16
	sd	ra, 8(sp)
	mv	a7, a0
	mv	a0, a1
	mv	a1, a2
	mv	a2, a3
	mv	a3, a4
	ecall
	ld	ra, 8(sp)
	addi	sp, sp, 16
	ret
	.size melis_sys, . - melis_sys
