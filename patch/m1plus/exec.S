/* A static MIPS o32 exec shim. Keep the argv[0] expected by Shanling's
 * checkappprocess.sh while executing the verified SD application. No libc,
 * mounts, flash writes or services. If SD exec fails, execute stock immediately. */
.module fp=64
.module oddspreg
.set noreorder
.text
.globl _start
_start:
    lw $t0, 0($sp)
    addiu $t0, $t0, 2
    sll $t0, $t0, 2
    addu $a2, $sp, $t0
    lui $a0, %hi(sd_app)
    addiu $a0, $a0, %lo(sd_app)
    lui $a1, %hi(app_argv)
    addiu $a1, $a1, %lo(app_argv)
    li $v0, 4011
    syscall
    lui $a0, %hi(stock_app)
    addiu $a0, $a0, %lo(stock_app)
    lui $a1, %hi(app_argv)
    addiu $a1, $a1, %lo(app_argv)
    /* Recompute envp: a failed syscall may clobber argument registers. */
    lw $t0, 0($sp)
    addiu $t0, $t0, 2
    sll $t0, $t0, 2
    addu $a2, $sp, $t0
    li $v0, 4011
    syscall
    li $a0, 127
    li $v0, 4001
    syscall
1:  b 1b
    nop
.section .rodata
sd_app: .asciz "/mnt/mmc/M1Pod/bin/demo"
stock_app: .asciz "/release/bin/demo"
.balign 4
app_argv: .word stock_app, 0
