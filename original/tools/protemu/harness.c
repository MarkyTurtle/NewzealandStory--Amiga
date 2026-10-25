/* protemu: run the New Zealand Story protection code in Musashi (a 68000 with the trace
 * exception, 68000 address errors and prefetch), logging every distinct instruction as it was
 * when executed (decrypted).  Built by build.sh against Musashi (github.com/kstenerud/Musashi).
 *
 *   protemu IMAGE LOADADDR START [options]
 *     -s SR -a SSP          initial SR / supervisor stack (default $2000 / $7F000)
 *     -m N                  stop after N instructions (default 50,000,000)
 *     -L FILE               write the listing (distinct pc+bytes, first-seen order) to FILE
 *     -k KEY -K PC          when PC is reached, set d0 = KEY (to supply the Copylock result)
 *     -j PC -J TARGET       when PC is reached, jump to TARGET (skip the disk check)
 *     -x LO-HI              stop when the PC leaves LO-HI (default: never)
 *     -d FILE ADDR LEN      at the end, dump memory ADDR..ADDR+LEN to FILE (repeatable)
 *     -D                    don't stop on disk access (CIA-B PRB / DSKLEN writes are ignored)
 *     -o OFF                68000 address errors on jumps to odd addresses, stacked PC = jump + OFF
 *     -T ADDR               the trace decoder's state (last decrypted address, its long): makes -j
 *                           re-encrypt / decrypt as the trace handler would
 *     -r REG=VAL            initial register (d0-d7, a0-a6)
 *     -S PC [-n N]          stop when PC is reached (the Nth time)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "m68k.h"

static uint8_t ram[0x80000];
static unsigned long steps, max_steps = 50000000;
static int stop_flag; static char stop_msg[256];
static int stop_on_disk = 1;
static unsigned key_pc = 0xFFFFFFFF, key_val; static unsigned jmp_pc = 0xFFFFFFFF, jmp_to;
static unsigned tvd_state = 0; static unsigned stop_pc = 0xFFFFFFFF; static int stop_count = 1;      /* -T: the trace decoder's state (address of last decrypted, its long) */
static unsigned lo = 0, hi = 0xFFFFFFFF;
/* 68000 address error on a jump to an odd address: Musashi stacks its own IR and PC; a real
 * 68000 stacks the jump's opcode, and a PC a few bytes after the jump (-o: offset from it) */
static int ae_fix = 0, ae_off = 2; static unsigned prev_pc, prev_op; static int naerr;

/* distinct instruction log */
#define MAXI 400000
static struct { unsigned pc; uint8_t b[10]; int n; int traced; unsigned long first; } ilog[MAXI];
static int ni;
static unsigned ring[64]; static int ringp;

static unsigned rd8(unsigned a) { a &= 0xFFFFFF; return a < sizeof ram ? ram[a] : 0; }
unsigned int m68k_read_memory_8(unsigned int a) {
    a &= 0xFFFFFF;
    if (a < sizeof ram) return ram[a];
    if (a == 0xBFE001) return 0xFF;                 /* CIA-A PRA: no buttons, drive not ready */
    if (a >= 0xDFF000 && a < 0xDFF200) return 0;
    return 0;
}
unsigned int m68k_read_memory_16(unsigned int a) { return m68k_read_memory_8(a) << 8 | m68k_read_memory_8(a + 1); }
unsigned int m68k_read_memory_32(unsigned int a) { return m68k_read_memory_16(a) << 16 | m68k_read_memory_16(a + 2); }
static void disk_stop(unsigned a, unsigned v) {
    if (!stop_on_disk || stop_flag) return;
    stop_flag = 1;
    snprintf(stop_msg, sizeof stop_msg, "drive access: $%X written to $%X at pc $%X", v, a, m68k_get_reg(NULL, M68K_REG_PPC));
    m68k_end_timeslice();
}
void m68k_write_memory_8(unsigned int a, unsigned int v) {
    a &= 0xFFFFFF;
    if (a < sizeof ram) { ram[a] = v; return; }
    if (a == 0xBFD100 && !(v & 0x80)) disk_stop(a, v);   /* motor on */
}
void m68k_write_memory_16(unsigned int a, unsigned int v) {
    a &= 0xFFFFFF;
    if (a == 0xDFF024) disk_stop(a, v);                    /* DSKLEN */
    m68k_write_memory_8(a, v >> 8); m68k_write_memory_8(a + 1, v);
}
void m68k_write_memory_32(unsigned int a, unsigned int v) { m68k_write_memory_16(a, v >> 16); m68k_write_memory_16(a + 2, v); }
unsigned int m68k_read_disassembler_8(unsigned int a) { return rd8(a); }
unsigned int m68k_read_disassembler_16(unsigned int a) { return rd8(a) << 8 | rd8(a + 1); }
unsigned int m68k_read_disassembler_32(unsigned int a) { return m68k_read_disassembler_16(a) << 16 | m68k_read_disassembler_16(a + 2); }

/* simple hash of (pc, first 4 bytes) -> ilog index */
#define HSZ (1 << 20)
static int htab[HSZ];

void instr_hook(unsigned int pc) {
    steps++;
    /* A branch or jump to an odd address. On a 68000 the jump prefetches its target as part of
     * the instruction, so the address error (group 0, ahead of trace) is raised by the jump
     * itself: IR = the jump's opcode, no trace exception. Musashi completes the jump and takes
     * the trace exception first; turn that trace frame into the address-error frame. */
    if (ae_fix && pc == (unsigned)m68k_read_memory_32(0x24) &&
        ((prev_op & 0xF000) == 0x6000 || (prev_op & 0xFFC0) == 0x4EC0)) {
        unsigned sp = m68k_get_reg(NULL, M68K_REG_SP);
        unsigned odd = m68k_read_memory_32(sp + 2);
        if (odd & 1) {
            unsigned sr = m68k_read_memory_16(sp), nsp = sp - 8;
            m68k_write_memory_16(nsp, 0x10 | ((sr & 0x2000) ? 6 : 2));   /* SSW: read, program space */
            m68k_write_memory_32(nsp + 2, odd);                           /* access address */
            m68k_write_memory_16(nsp + 6, prev_op);                       /* IR */
            m68k_write_memory_16(nsp + 8, sr);                            /* SR (trace bit still set) */
            m68k_write_memory_32(nsp + 10, prev_pc + ae_off);             /* PC */
            m68k_set_reg(M68K_REG_SP, nsp);
            pc = m68k_read_memory_32(0x0C);
            m68k_set_reg(M68K_REG_PC, pc);
            naerr++;
        }
    }
    if (pc == stop_pc && --stop_count == 0 && !stop_flag) {
        stop_flag = 1; snprintf(stop_msg, sizeof stop_msg, "reached $%X", pc); m68k_end_timeslice(); m68k_set_reg(M68K_REG_PC, pc);
    }
    if (pc & 1) return;
    prev_pc = pc; prev_op = rd8(pc) << 8 | rd8(pc + 1);
    ring[ringp++ & 63] = pc;
    if (pc == key_pc) m68k_set_reg(M68K_REG_D0, key_val);
    if (pc == jmp_pc) {
        if (tvd_state) {
            /* do what the trace handler would: put back the long it decrypted, decrypt the target */
            unsigned last = m68k_read_memory_32(tvd_state);
            m68k_write_memory_32(last, m68k_read_memory_32(tvd_state + 4));
            unsigned k = ~m68k_read_memory_32(jmp_to - 4); k = (k << 16) | (k >> 16);
            m68k_write_memory_32(tvd_state, jmp_to);
            m68k_write_memory_32(tvd_state + 4, m68k_read_memory_32(jmp_to));
            m68k_write_memory_32(jmp_to, m68k_read_memory_32(jmp_to) ^ k);
        }
        m68k_set_reg(M68K_REG_PC, jmp_to);
        if (pc == key_pc || jmp_to == key_pc) m68k_set_reg(M68K_REG_D0, key_val);
        jmp_pc = 0xFFFFFFFF;
        return;
    }
    if (pc < lo || pc >= hi) {
        if (!stop_flag) { stop_flag = 1; snprintf(stop_msg, sizeof stop_msg, "pc $%X left the range", pc); m68k_end_timeslice(); }
    }
    uint32_t w = rd8(pc) << 24 | rd8(pc + 1) << 16 | rd8(pc + 2) << 8 | rd8(pc + 3);
    unsigned h = (pc * 2654435761u ^ w * 40503u) & (HSZ - 1);
    while (htab[h]) {
        int i = htab[h] - 1;
        if (ilog[i].pc == pc && memcmp(ilog[i].b, (uint8_t[]){rd8(pc), rd8(pc+1), rd8(pc+2), rd8(pc+3)}, 4) == 0) goto done;
        h = (h + 1) & (HSZ - 1);
    }
    if (ni < MAXI) {
        ilog[ni].pc = pc; ilog[ni].first = steps;
        for (int k = 0; k < 10; k++) ilog[ni].b[k] = rd8(pc + k);
        ilog[ni].traced = (m68k_get_reg(NULL, M68K_REG_SR) & 0x8000) != 0;
        htab[h] = ++ni;
    }
done:
    if (steps >= max_steps && !stop_flag) { stop_flag = 1; snprintf(stop_msg, sizeof stop_msg, "stopped after %lu instructions", steps); m68k_end_timeslice(); }
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: protemu IMAGE LOADADDR START [options]\n"); return 2; }
    FILE *f = fopen(argv[1], "rb"); if (!f) { perror(argv[1]); return 1; }
    unsigned load = strtoul(argv[2], 0, 0), start = strtoul(argv[3], 0, 0);
    size_t n = fread(ram + load, 1, sizeof ram - load, f); fclose(f);
    unsigned sr = 0x2000, ssp = 0x7F000; const char *lst = 0;
    struct { const char *fn; unsigned a, l; } dumps[8]; int nd = 0;
    struct { int r; unsigned v; } regset[16]; int nr = 0;      /* -r d0=VAL / a1=VAL */
    for (int i = 4; i < argc; i++) {
        if (!strcmp(argv[i], "-s")) sr = strtoul(argv[++i], 0, 0);
        else if (!strcmp(argv[i], "-a")) ssp = strtoul(argv[++i], 0, 0);
        else if (!strcmp(argv[i], "-m")) max_steps = strtoul(argv[++i], 0, 0);
        else if (!strcmp(argv[i], "-L")) lst = argv[++i];
        else if (!strcmp(argv[i], "-k")) key_val = strtoul(argv[++i], 0, 0);
        else if (!strcmp(argv[i], "-K")) key_pc = strtoul(argv[++i], 0, 0);
        else if (!strcmp(argv[i], "-j")) jmp_pc = strtoul(argv[++i], 0, 0);
        else if (!strcmp(argv[i], "-J")) jmp_to = strtoul(argv[++i], 0, 0);
        else if (!strcmp(argv[i], "-D")) stop_on_disk = 0;
        else if (!strcmp(argv[i], "-T")) tvd_state = strtoul(argv[++i], 0, 0);
        else if (!strcmp(argv[i], "-S")) { stop_pc = strtoul(argv[++i], 0, 0); }
        else if (!strcmp(argv[i], "-n")) { stop_count = strtol(argv[++i], 0, 0); }
        else if (!strcmp(argv[i], "-r") && nr < 16) { char *eq = strchr(argv[++i], '='); regset[nr].r = strtol(argv[i] + 1, 0, 10) + (argv[i][0] == 'a' ? 8 : 0); regset[nr].v = strtoul(eq + 1, 0, 0); nr++; }
        else if (!strcmp(argv[i], "-o")) { ae_fix = 1; ae_off = strtol(argv[++i], 0, 0); }
        else if (!strcmp(argv[i], "-x")) { sscanf(argv[++i], "%x-%x", &lo, &hi); }
        else if (!strcmp(argv[i], "-d") && nd < 8) { dumps[nd].fn = argv[++i]; dumps[nd].a = strtoul(argv[++i], 0, 0); dumps[nd].l = strtoul(argv[++i], 0, 0); nd++; }
    }
    /* reset vectors: SSP and PC at 0 (overwritten by the code later, as on the machine) */
    uint8_t save[8]; memcpy(save, ram, 8);
    ram[0] = ssp >> 24; ram[1] = ssp >> 16; ram[2] = ssp >> 8; ram[3] = ssp;
    ram[4] = start >> 24; ram[5] = start >> 16; ram[6] = start >> 8; ram[7] = start;
    m68k_init(); m68k_set_cpu_type(M68K_CPU_TYPE_68000); m68k_pulse_reset();
    memcpy(ram, save, 8);
    m68k_set_reg(M68K_REG_SR, sr);
    m68k_set_reg(M68K_REG_SP, ssp);
    m68k_set_reg(M68K_REG_PC, start);
    for (int i = 0; i < nr; i++) m68k_set_reg(M68K_REG_D0 + regset[i].r, regset[i].v);
    while (!stop_flag) m68k_execute(100000);
    printf("%lu instructions; %s; %d distinct; %d address errors fixed\n", steps, stop_msg, ni, naerr);
    printf("regs: d0=%08X d1=%08X a0=%08X a4=%08X a7=%08X sr=%04X pc=%08X\n",
           m68k_get_reg(NULL, M68K_REG_D0), m68k_get_reg(NULL, M68K_REG_D1), m68k_get_reg(NULL, M68K_REG_A0),
           m68k_get_reg(NULL, M68K_REG_A4), m68k_get_reg(NULL, M68K_REG_A7), m68k_get_reg(NULL, M68K_REG_SR),
           m68k_get_reg(NULL, M68K_REG_PC));
    printf("last pcs:"); for (int k = 0; k < 16; k++) printf(" %X", ring[(ringp - 16 + k) & 63]); printf("\n");
    if (lst) {
        FILE *o = fopen(lst, "w"); char buf[200];
        for (int i = 0; i < ni; i++) {
            /* disassemble from the logged bytes: put them back temporarily */
            uint8_t keep[10]; unsigned pc = ilog[i].pc;
            for (int k = 0; k < 10; k++) { keep[k] = rd8(pc + k); if (pc + k < sizeof ram) ram[pc + k] = ilog[i].b[k]; }
            int len = m68k_disassemble(buf, pc, M68K_CPU_TYPE_68000);
            char hx[32] = ""; for (int k = 0; k < len && k < 10; k++) sprintf(hx + 2 * k, "%02X", ilog[i].b[k]);
            fprintf(o, "%lu\t%05X\t%-20s\t%s\t%s\n", ilog[i].first, pc, hx, ilog[i].traced ? "T" : "", buf);
            for (int k = 0; k < 10; k++) if (pc + k < sizeof ram) ram[pc + k] = keep[k];
        }
        fclose(o);
    }
    for (int i = 0; i < nd; i++) { FILE *o = fopen(dumps[i].fn, "wb"); fwrite(ram + dumps[i].a, 1, dumps[i].l, o); fclose(o); }
    return 0;
}
