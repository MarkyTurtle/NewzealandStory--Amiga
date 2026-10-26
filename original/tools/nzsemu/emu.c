/* nzsemu: runs The New Zealand Story's main program on a minimal Amiga, for studying it.
 *
 * A 68000 (Musashi) with 512K of chip RAM and just what the game uses: the vertical blank
 * (level 3), CIA-B timer A/B and TOD alarm (level 6), CIA-A (fire buttons, keyboard: level 2),
 * the audio channel 3 interrupt (level 4: the game's sample player), the blitter (area mode,
 * done at once when BLTSIZE is written), the joystick. The disk is not emulated: a call of the
 * game's TrackRead (its jump table entry, $40C) is answered from the extracted tracks (disk/files/tracks/). The display
 * is not drawn: snapshots of memory and the custom registers are written instead, and
 * tools/screen.py draws them by following the copper list.
 *
 * Every executed instruction's address is recorded (coverage), to give the disassembler entry
 * points it cannot find statically.
 *
 *   nzsemu MAIN.bin TRACKDIR SCRIPT
 *
 * SCRIPT, one command a line (# comments):
 *   frames N              run N frames (PAL: 312 lines of 455 CPU cycles)
 *   joy [u][d][l][r][f]   hold these joystick directions / fire (port 1); "joy" alone: none
 *   random N SEED         N frames with a random joystick (held 8-40 frames at a time)
 *   key CODE              press and release a raw key (hex)
 *   poke ADDR VAL [b|w|l] write memory
 *   snap PREFIX           write PREFIX.mem (512K) and PREFIX.regs (the custom registers, 512 bytes)
 *   cover FILE            write the coverage bitmap (1 bit per byte address, $80000 bits)
 *   log FILE              append events (track reads, frame numbers) to FILE
 *   until ADDR [N]        run until the PC reaches ADDR (at most N frames)
 *   call ADDR [D0]        call a routine (interrupts masked, time going on) until it returns
 *   play ADDR N           N frames of: call ADDR, then the rest of the frame (a music player)
 *   audio FILE            log every write to the audio registers and DMACON: "cycle reg value"
 *   load FILE ADDR        copy a file into memory at ADDR
 *   setd1 ADDR VALUE      set d1 whenever the PC reaches ADDR (the vertical blank's add.l d1 to the
 *                         random seed at $BE04, then addq #1: with d1 = -1 the seed changes only when
 *                         the game draws a number, not with the code or the frames; for comparing
 *                         two builds)
 *   passes N SEED ADDR EVERY PREFIX [SNAPADDR]
 *                         N passes of the game loop (counted at ADDR) with a random joystick changed
 *                         there (held 4-20 passes, and given to the game at once: its word at $63DB0);
 *                         a snapshot PREFIX_nnnn every EVERY passes (0: none), at SNAPADDR (default
 *                         ADDR) in that pass; then the frame finished
 *   blittime 1            the blitter busy (DMACONR bit 14) for 2 CPU cycles a memory cycle of each blit
 *                         (one a channel a word, at least 2), so the CPU waits for it as on an A500
 *                         (the bitplanes' and the CPU's own use of chip memory not counted)
 *   trace ADDR            log (to the log file) the frame, line, d0, d1, a0, the words at a6+4, a6+6, a5
 *                         and its object's type ($1C), mirror flag ($10) and script ($14), and the level
 *                         ($641C0), and the blitter's memory cycles so far (blitc: about one a channel a
 *                         word, at least 2; 280 ns each), each time the PC reaches ADDR
 *   watchpc LO HI         log (to the log file) each instruction's first write to each 256-byte block of
 *                         LO-HI
 *   watch LO HI           log (to the log file) the first write to each 256-byte block of LO-HI,
 *                         with the PC that made it
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "m68k.h"

#define RAM 0x80000
static uint8_t ram[RAM];
static uint16_t cust[0x100];          /* custom registers as last written / derived */
static uint16_t intena, intreq, dmacon, adkcon;
static uint8_t cover[RAM / 8];
static const char *trackdir;
static FILE *logf;
static unsigned long frame, line_no;
static unsigned joy;                  /* bits: 1 up 2 down 4 left 8 right 16 fire */
static unsigned until_pc = 0xFFFFFFFF; static int until_hit;
static unsigned trace_pc = 0xFFFFFFFF;
static unsigned set_d1_pc = 0xFFFFFFFF, set_d1_val;
/* passes: the joystick re-rolled per pass of the game loop (each arrival at pass_pc), snapshots
 * every pass_every passes */
static unsigned pass_pc = 0xFFFFFFFF, pass_snap_pc = 0xFFFFFFFF; static long pass_left, pass_count, pass_every, pass_hold;
static int pass_done; static char pass_prefix[400];
static void snapshot(const char *prefix);
static unsigned rnd(void);
static int blits, blit_line; static long blit_words, blit_cycles;
static long cyc_now(void);
static int blit_timed; static long blit_busy_until;   /* blittime: the blitter busy for its cycles */
static FILE *audf;
static unsigned watch_lo = 1, watch_hi = 0; static uint8_t watched[RAM / 256];
static int watch_pcs; static unsigned seen_n, seen[8192];   /* watchpc: (block << 20 | pc) seen */
static void watch(unsigned a) {
    if (watch_pcs && a >= watch_lo && a < watch_hi) {
        unsigned pc = m68k_get_reg(NULL, M68K_REG_PPC), key = (a >> 8) << 20 | (pc & 0xFFFFF);
        for (unsigned i = 0; i < seen_n; i++) if (seen[i] == key) return;
        if (seen_n < 8192) seen[seen_n++] = key;
        if (logf) fprintf(logf, "frame %lu: write to $%05X by pc $%X\n", frame, a, pc);
        return;
    }
    if (a >= watch_lo && a < watch_hi && !watched[a >> 8]) {
        watched[a >> 8] = 1;
        if (logf) fprintf(logf, "frame %lu: first write to $%05X block by pc $%X\n", frame, a & ~0xFF, m68k_get_reg(NULL, M68K_REG_PPC));
    }
}

/* ---- CIAs */
typedef struct {
    uint8_t pra, prb, ddra, ddrb, icr_mask, icr_flags, cra, crb, sdr;
    uint16_t ta, tb, ta_latch, tb_latch;
    uint32_t tod, alarm; int tod_halt; uint32_t tod_latch; int tod_latched;
} cia_t;
static cia_t ciaa, ciab;
static int key_queue[16], kq_n; static int key_delay;

static void update_irq(void) {
    unsigned act = intena & 0x4000 ? (intena & intreq & 0x3FFF) : 0;
    int lvl = 0;
    if (act & 0x6000) lvl = 6; else if (act & 0x1800) lvl = 5; else if (act & 0x0780) lvl = 4;
    else if (act & 0x0070) lvl = 3; else if (act & 0x0008) lvl = 2; else if (act & 0x0007) lvl = 1;
    m68k_set_irq(lvl);
}
static void cia_irq(cia_t *c, int bit) {
    c->icr_flags |= bit;
    if (c->icr_mask & bit) { c->icr_flags |= 0x80; intreq |= (c == &ciaa) ? 0x0008 : 0x2000; update_irq(); }
}

/* ---- audio interrupts: a channel's request is set when its DMA starts a block (and again
 * each time the block repeats); a channel whose DMA is off requests at once (the sound driver
 * waits for that after stopping a channel) */
static long aud_next[4] = {-1, -1, -1, -1}; static long cyc_total;
static void aud_schedule(int ch) {
    unsigned len = cust[(0xA4 + 16 * ch) / 2], per = cust[(0xA6 + 16 * ch) / 2];
    if (!len) len = 0x10000; if (per < 124) per = 124;
    aud_next[ch] = cyc_total + (long)len * 2 * per * 2;
}

/* ---- blitter: area mode, at once */
static uint16_t rw(uint32_t a) { a &= RAM - 2; return ram[a] << 8 | ram[a + 1]; }
static void watch(unsigned a);
static void ww(uint32_t a, uint16_t v) { a &= RAM - 2; watch(a); ram[a] = v >> 8; ram[a + 1] = v; }
static uint32_t ptr(int r) { return ((uint32_t)cust[r / 2] << 16 | cust[r / 2 + 1]) & 0x7FFFE; }
static void blit(uint16_t size) {
    uint16_t con0 = cust[0x40 / 2], con1 = cust[0x42 / 2];
    blits++;
    if (con1 & 1) { blit_line++; goto done; }      /* line mode: not done */
    int h = size >> 6 ? size >> 6 : 1024, w = size & 63 ? size & 63 : 64;
    blit_words += (long)h * w;
    int use = con0 >> 8 & 15, ash = con0 >> 12, bsh = con1 >> 12, mt = con0 & 0xFF, desc = con1 & 2;
    {   /* the blitter's memory cycles (280 ns each): about one a channel a word, at least 2 */
        int n = (use & 8 ? 1 : 0) + (use & 4 ? 1 : 0) + (use & 2 ? 1 : 0) + (use & 1 ? 1 : 0);
        blit_cycles += (long)h * w * (n < 2 ? 2 : n);
        if (blit_timed) blit_busy_until = cyc_now() + 2L * h * w * (n < 2 ? 2 : n);   /* 2 CPU cycles each */
    }
    uint16_t fwm = cust[0x44 / 2], lwm = cust[0x46 / 2];
    uint32_t pa = ptr(0x50), pb = ptr(0x4C), pc = ptr(0x48), pd = ptr(0x54);
    int16_t ma = cust[0x64 / 2], mb = cust[0x62 / 2], mc = cust[0x60 / 2], md = cust[0x66 / 2];
    uint16_t adat = cust[0x74 / 2], bdat = cust[0x72 / 2], cdat = cust[0x70 / 2];
    int step = desc ? -2 : 2;
    int fill = (con1 >> 3) & 3;                     /* IFE / EFE (fill mode) */
    for (int y = 0; y < h; y++) {
        uint16_t olda = 0, oldb = 0; int fc = (con1 >> 2) & 1;
        for (int x = 0; x < w; x++) {
            uint16_t a = use & 8 ? rw(pa) : adat, b = use & 4 ? rw(pb) : bdat, c = use & 2 ? rw(pc) : cdat;
            if (use & 8) pa += step; if (use & 4) pb += step; if (use & 2) pc += step;
            uint16_t am = a;
            if (x == 0) am &= fwm;
            if (x == w - 1) am &= lwm;
            uint16_t as, bs;
            if (!desc) { as = (uint16_t)(((uint32_t)olda << 16 | am) >> ash); bs = (uint16_t)(((uint32_t)oldb << 16 | b) >> bsh); }
            else       { as = (uint16_t)(((uint32_t)am << 16 | olda) >> (16 - ash)); bs = (uint16_t)(((uint32_t)b << 16 | oldb) >> (16 - bsh)); }
            olda = am; oldb = b;
            uint16_t d = 0;
            for (int i = 0; i < 8; i++) if (mt >> i & 1)
                d |= (i & 4 ? as : ~as) & (i & 2 ? bs : ~bs) & (i & 1 ? c : ~c);
            if (fill) {                              /* descending fill, word by word */
                uint16_t o = 0;
                for (int bit = 0; bit < 16; bit++) {
                    int v = d >> bit & 1;
                    if (v) fc ^= 1;
                    int out = (fill & 2) ? (fc ^ v) : (fc | v);
                    if (fill & 1) out = fc | v;
                    o |= out << bit;
                }
                d = o;
            }
            if (use & 1) { ww(pd, d); pd += step; }
        }
        if (use & 8) pa += desc ? -ma : ma; if (use & 4) pb += desc ? -mb : mb;
        if (use & 2) pc += desc ? -mc : mc; if (use & 1) pd += desc ? -md : md;
    }
    cust[0x50 / 2] = pa >> 16; cust[0x52 / 2] = pa; cust[0x4C / 2] = pb >> 16; cust[0x4E / 2] = pb;
    cust[0x48 / 2] = pc >> 16; cust[0x4A / 2] = pc; cust[0x54 / 2] = pd >> 16; cust[0x56 / 2] = pd;
done:
    intreq |= 0x0040; update_irq();
}

/* ---- memory */
static unsigned beam(void) {
    unsigned cyc = 455 - m68k_cycles_remaining();
    if ((int)cyc < 0) cyc = 0; if (cyc > 454) cyc = 454;
    return (line_no << 8 | (cyc / 2)) & 0xFFFF;
}
static unsigned custom_read(unsigned r) {
    switch (r) {
    case 0x002: return (dmacon & 0x3FFF) | (blit_timed && cyc_now() < blit_busy_until ? 0x4000 : 0);
                                                             /* DMACONR: the blitter busy (blittime) */
    case 0x004: return (line_no >> 8) & 1;                   /* VPOSR (PAL OCS) */
    case 0x006: return beam();                               /* VHPOSR */
    case 0x00A: return 0;                                    /* JOY0DAT */
    case 0x00C: {                                            /* JOY1DAT */
        unsigned r1 = joy & 8 ? 1 : 0, l = joy & 4 ? 1 : 0, d = joy & 2 ? 1 : 0, u = joy & 1 ? 1 : 0;
        return (l << 9) | ((l ^ u) << 8) | (r1 << 1) | (r1 ^ d); }
    case 0x010: return adkcon;
    case 0x016: return 0xFF00;                               /* POTGOR: right buttons up */
    case 0x01A: return 0;                                    /* DSKBYTR */
    case 0x01C: return intena;
    case 0x01E:
        for (int ch = 0; ch < 4; ch++)
            if (!((dmacon & 0x200) && (dmacon & (1 << ch)))) intreq |= 0x80 << ch;
        update_irq();
        return intreq;
    }
    return cust[r / 2];
}
static long cyc_now(void);
static void custom_write(unsigned r, unsigned v) {
    v &= 0xFFFF;
    cust[r / 2] = v;
    if (audf && ((r >= 0xA0 && r < 0xE0) || r == 0x096)) fprintf(audf, "%ld %03X %04X\n", cyc_now(), r, v);
    switch (r) {
    case 0x058: blit(v); break;
    case 0x096: { unsigned old = dmacon; dmacon = v & 0x8000 ? dmacon | (v & 0x7FFF) : dmacon & ~v;
        for (int ch = 0; ch < 4; ch++) {
            unsigned m = 0x200 | (1 << ch);
            if ((dmacon & m) == m && (old & m) != m) { intreq |= 0x80 << ch; update_irq(); aud_schedule(ch); }
            if ((dmacon & m) != m) aud_next[ch] = -1;
        }
        break; }
    case 0x09A: intena = v & 0x8000 ? intena | (v & 0x7FFF) : intena & ~v; update_irq(); break;
    case 0x09C: intreq = v & 0x8000 ? intreq | (v & 0x7FFF) : intreq & ~v; update_irq(); break;
    case 0x09E: adkcon = v & 0x8000 ? adkcon | (v & 0x7FFF) : adkcon & ~v; break;
    }
}
static unsigned cia_read(cia_t *c, int reg, int isa) {
    switch (reg) {
    case 0: if (isa) {                                       /* PRA: /FIR1 /FIR0 /RDY /TK0 /WPRO /CHNG */
                unsigned v = 0xFC; if (joy & 16) v &= ~0x80; return (v & ~c->ddra) | (c->pra & c->ddra); }
            return c->pra;
    case 1: return c->prb;
    case 2: return c->ddra; case 3: return c->ddrb;
    case 4: return c->ta & 0xFF; case 5: return c->ta >> 8;
    case 6: return c->tb & 0xFF; case 7: return c->tb >> 8;
    case 8: { uint32_t t = c->tod_latched ? c->tod_latch : c->tod; c->tod_latched = 0; return t & 0xFF; }
    case 9: return ((c->tod_latched ? c->tod_latch : c->tod) >> 8) & 0xFF;
    case 10: c->tod_latch = c->tod; c->tod_latched = 1; return (c->tod >> 16) & 0xFF;
    case 12: return c->sdr;
    case 13: { unsigned f = c->icr_flags; c->icr_flags = 0;
        intreq &= ~(isa ? 0x0008 : 0x2000); update_irq(); return f; }
    case 14: return c->cra; case 15: return c->crb;
    }
    return 0;
}
static void cia_write(cia_t *c, int reg, unsigned v) {
    v &= 0xFF;
    switch (reg) {
    case 0: c->pra = v; break; case 1: c->prb = v; break;
    case 2: c->ddra = v; break; case 3: c->ddrb = v; break;
    case 4: c->ta_latch = (c->ta_latch & 0xFF00) | v; break;
    case 5: c->ta_latch = (c->ta_latch & 0xFF) | v << 8; if (!(c->cra & 1)) c->ta = c->ta_latch; break;
    case 6: c->tb_latch = (c->tb_latch & 0xFF00) | v; break;
    case 7: c->tb_latch = (c->tb_latch & 0xFF) | v << 8; if (!(c->crb & 1)) c->tb = c->tb_latch; break;
    case 8: if (c->crb & 0x80) c->alarm = (c->alarm & 0xFFFF00) | v; else { c->tod = (c->tod & 0xFFFF00) | v; c->tod_halt = 0; } break;
    case 9: if (c->crb & 0x80) c->alarm = (c->alarm & 0xFF00FF) | v << 8; else c->tod = (c->tod & 0xFF00FF) | v << 8; break;
    case 10: if (c->crb & 0x80) c->alarm = (c->alarm & 0x00FFFF) | v << 16; else { c->tod = (c->tod & 0x00FFFF) | v << 16; c->tod_halt = 1; } break;
    case 12: c->sdr = v; break;
    case 13: if (v & 0x80) c->icr_mask |= v & 0x7F; else c->icr_mask &= ~v; break;
    case 14: if (v & 0x10) c->ta = c->ta_latch; c->cra = v & ~0x10; break;
    case 15: if (v & 0x10) c->tb = c->tb_latch; c->crb = v & ~0x10; break;
    }
}
unsigned int m68k_read_memory_8(unsigned int a) {
    a &= 0xFFFFFF;
    if (a < RAM) return ram[a];
    if ((a & 0xFFF000) == 0xBFE000 && (a & 1)) return cia_read(&ciaa, (a >> 8) & 15, 1);
    if ((a & 0xFFF000) == 0xBFD000 && !(a & 1)) return cia_read(&ciab, (a >> 8) & 15, 0);
    if ((a & 0xFFF000) == 0xDFF000) { unsigned v = custom_read(a & 0x1FE); return a & 1 ? v & 0xFF : v >> 8; }
    return 0;
}
unsigned int m68k_read_memory_16(unsigned int a) {
    a &= 0xFFFFFF;
    if (a < RAM) return ram[a] << 8 | ram[a + 1];
    if ((a & 0xFFF000) == 0xDFF000) return custom_read(a & 0x1FE);
    return m68k_read_memory_8(a) << 8 | m68k_read_memory_8(a + 1);
}
unsigned int m68k_read_memory_32(unsigned int a) { return m68k_read_memory_16(a) << 16 | m68k_read_memory_16(a + 2); }
void m68k_write_memory_8(unsigned int a, unsigned int v) {
    a &= 0xFFFFFF;
    if (a < RAM) { watch(a); ram[a] = v; return; }
    if ((a & 0xFFF000) == 0xBFE000 && (a & 1)) { cia_write(&ciaa, (a >> 8) & 15, v); return; }
    if ((a & 0xFFF000) == 0xBFD000 && !(a & 1)) { cia_write(&ciab, (a >> 8) & 15, v); return; }
    if ((a & 0xFFF000) == 0xDFF000) { unsigned r = a & 0x1FE; custom_write(r, a & 1 ? (cust[r / 2] & 0xFF00) | (v & 0xFF) : (v & 0xFF) << 8 | (v & 0xFF)); }
}
void m68k_write_memory_16(unsigned int a, unsigned int v) {
    a &= 0xFFFFFF;
    if (a < RAM) { watch(a); ram[a] = v >> 8; ram[a + 1] = v; return; }
    if ((a & 0xFFF000) == 0xDFF000) { custom_write(a & 0x1FE, v); return; }
    m68k_write_memory_8(a, v >> 8); m68k_write_memory_8(a + 1, v);
}
void m68k_write_memory_32(unsigned int a, unsigned int v) { m68k_write_memory_16(a, v >> 16); m68k_write_memory_16(a + 2, v); }
unsigned int m68k_read_disassembler_8(unsigned int a) { return m68k_read_memory_8(a); }
unsigned int m68k_read_disassembler_16(unsigned int a) { return m68k_read_memory_16(a); }
unsigned int m68k_read_disassembler_32(unsigned int a) { return m68k_read_memory_32(a); }

/* ---- the game's TrackRead, answered from the extracted tracks: intercepted at the jump table's entry
 * (JT_TrackRead, $40C), through which the game makes every read (so the enhanced game too) */
#define TRACKREAD 0x40C
static int track_read(void) {
    unsigned d0 = m68k_get_reg(NULL, M68K_REG_D0) & 0xFFFF, d1 = m68k_get_reg(NULL, M68K_REG_D1) & 0xFFFF;
    unsigned a0 = m68k_get_reg(NULL, M68K_REG_A0);
    int ok = 1;
    for (unsigned k = 0; k < d1; k++) {
        char fn[1024]; snprintf(fn, sizeof fn, "%s/t%03u.bin", trackdir, d0 + k);
        FILE *f = fopen(fn, "rb");
        if (!f || a0 + 5632 * (k + 1) > RAM) { ok = 0; if (f) fclose(f); break; }
        fread(ram + a0 + 5632 * k, 1, 5632, f); fclose(f);
    }
    if (logf) fprintf(logf, "frame %lu: TrackRead track %u count %u to $%X%s\n", frame, d0, d1, a0, ok ? "" : " FAILED");
    return ok;
}

void instr_hook(unsigned int pc) {
    pc &= 0xFFFFFF;
    if (pc < RAM) cover[pc >> 3] |= 1 << (pc & 7);
    if (pc == until_pc) { until_hit = 1; m68k_end_timeslice(); }
    if (pc == set_d1_pc) m68k_set_reg(M68K_REG_D1, set_d1_val);
    if (pc == pass_pc && pass_every < 0) pass_every = -pass_every;
    if (pc == pass_pc && pass_left > 0) {
        pass_count++;
        if (--pass_hold <= 0) {
            joy = rnd() & 31; if ((joy & 3) == 3) joy &= ~2; if ((joy & 12) == 12) joy &= ~4;
            pass_hold = 4 + rnd() % 17;
        }
        /* the game's own reading of it (ReadJoystick, kept at $63DB0 by the vertical blank), now:
           the pass's logic sees it whatever the vertical blank's phase */
        unsigned j = m68k_read_memory_16(0xDFF00C) & 0x303, d2 = (j >> 1) & 0x101;
        j ^= d2; j = (j & 3) | (j >> 6); if (joy & 16) j |= 0x80;
        m68k_write_memory_16(0x63DB0, j);
        if (--pass_left == 0 && !(pass_every > 0 && pass_count % pass_every == 0)) pass_done = 1;
    }
    if (pc == pass_snap_pc && pass_every > 0 && pass_count && pass_count % pass_every == 0) {
        char fn[480]; snprintf(fn, sizeof fn, "%s_%04ld", pass_prefix, pass_count / pass_every); snapshot(fn);
        pass_every = -pass_every;                            /* (once a pass) */
        if (pass_left == 0) pass_done = 1;
    }

    if (pc == trace_pc && logf) {
        unsigned a6 = m68k_get_reg(NULL, M68K_REG_A6);
        unsigned a5 = m68k_get_reg(NULL, M68K_REG_A5);
        fprintf(logf, "frame %lu line %lu: pc $%X d0 $%X d1 $%X a0 $%X a6+4: $%04X $%04X a5 $%X type $%04X mirror $%02X"
                " script $%X level $%04X blitc %ld\n",
                frame, line_no, pc, m68k_get_reg(NULL, M68K_REG_D0), m68k_get_reg(NULL, M68K_REG_D1),
                m68k_get_reg(NULL, M68K_REG_A0), m68k_read_memory_16(a6 + 4), m68k_read_memory_16(a6 + 6), a5,
                a5 < RAM - 0x40 ? m68k_read_memory_16(a5 + 0x1C) : 0, a5 < RAM - 0x40 ? m68k_read_memory_8(a5 + 0x10) : 0,
                a5 < RAM - 0x40 ? m68k_read_memory_32(a5 + 0x14) : 0, m68k_read_memory_16(0x641C0), blit_cycles);
    }
    if (pc == TRACKREAD) {
        int ok = track_read();
        unsigned sp = m68k_get_reg(NULL, M68K_REG_SP);
        m68k_set_reg(M68K_REG_D0, ok ? 0 : 0xFFFFFFFF);
        m68k_set_reg(M68K_REG_PC, m68k_read_memory_32(sp));
        m68k_set_reg(M68K_REG_SP, sp + 4);
    }
}

/* ---- timing: a frame of 312 lines of 455 cycles */
static void cia_tick_timers(cia_t *c, int eclocks) {
    for (int i = 0; i < eclocks; i++) {
        int ta_under = 0;
        if ((c->cra & 1) && !(c->cra & 0x20)) {
            if (c->ta == 0) { ta_under = 1; c->ta = c->ta_latch; cia_irq(c, 1); if (c->cra & 8) c->cra &= ~1; }
            else c->ta--;
        }
        if (c->crb & 1) {
            int mode = (c->crb >> 5) & 3, tick = mode == 0 ? 1 : mode >= 2 ? ta_under : 0;
            if (tick) {
                if (c->tb == 0) { c->tb = c->tb_latch; cia_irq(c, 2); if (c->crb & 8) c->crb &= ~1; }
                else c->tb--;
            }
        }
    }
}
static long cyc_now(void) { long c = 455 - m68k_cycles_remaining(); if (c < 0) c = 0; if (c > 455) c = 455; return cyc_total + c; }
static void run_line(void) {
    m68k_execute(455);
    cyc_total += 455;
    cia_tick_timers(&ciaa, 45); cia_tick_timers(&ciab, 45);
    /* CIA-B TOD counts lines (HSYNC) */
    if (!ciab.tod_halt) { ciab.tod = (ciab.tod + 1) & 0xFFFFFF; if (ciab.tod == ciab.alarm) cia_irq(&ciab, 4); }
    for (int ch = 0; ch < 4; ch++)
        if (aud_next[ch] >= 0 && cyc_total >= aud_next[ch]) { intreq |= 0x80 << ch; update_irq(); aud_schedule(ch); }
    line_no++;
}
static void keyboard_tick(void) {
    if (key_delay > 0) { key_delay--; return; }
    if (kq_n) {
        int k = key_queue[0]; memmove(key_queue, key_queue + 1, --kq_n * sizeof(int));
        ciaa.sdr = ~((k << 1) | (k >> 7)) & 0xFF;            /* the keyboard's encoding */
        cia_irq(&ciaa, 8); key_delay = 3;
    }
}
static void run_frame(void) {
    line_no = 0;
    /* CIA-A TOD counts frames (VSYNC) */
    ciaa.tod = (ciaa.tod + 1) & 0xFFFFFF;
    intreq |= 0x0020; update_irq();                           /* VERTB */
    keyboard_tick();
    for (int l = 0; l < 312 && !until_hit; l++) run_line();
    frame++;
}

static uint32_t rng = 1;
static unsigned rnd(void) { rng = rng * 1103515245 + 12345; return rng >> 16; }
static void snapshot(const char *prefix) {
    char fn[500]; snprintf(fn, sizeof fn, "%s.mem", prefix); FILE *o = fopen(fn, "wb"); fwrite(ram, 1, RAM, o); fclose(o);
    snprintf(fn, sizeof fn, "%s.regs", prefix); o = fopen(fn, "wb");
    for (int i = 0; i < 0x100; i++) { uint16_t v = cust[i]; fputc(v >> 8, o); fputc(v & 0xFF, o); } fclose(o);
}

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: nzsemu MAIN.bin TRACKDIR SCRIPT\n"); return 2; }
    FILE *f = fopen(argv[1], "rb"); if (!f) { perror(argv[1]); return 1; }
    fread(ram + 0x400, 1, RAM - 0x400, f); fclose(f);
    trackdir = argv[2];
    m68k_init(); m68k_set_cpu_type(M68K_CPU_TYPE_68000);
    ram[0] = 0; ram[1] = 7; ram[2] = 0xF0; ram[3] = 0; ram[4] = 0; ram[5] = 0; ram[6] = 4; ram[7] = 0;
    m68k_pulse_reset();
    m68k_set_reg(M68K_REG_SR, 0x2700); m68k_set_reg(M68K_REG_SP, 0x7F000);
    m68k_set_reg(M68K_REG_D0, 0x400); m68k_set_reg(M68K_REG_A0, 0x400); m68k_set_reg(M68K_REG_PC, 0x400);
    ciaa.cra = ciab.cra = 0; ciaa.icr_mask = 0; ciab.icr_mask = 0;
    FILE *sc = fopen(argv[3], "r"); if (!sc) { perror(argv[3]); return 1; }
    char ln[512];
    while (fgets(ln, sizeof ln, sc)) {
        char cmd[32] = "", a1[256] = "", a2[64] = "", a3[16] = "";
        if (sscanf(ln, "%31s %255s %63s %15s", cmd, a1, a2, a3) < 1 || cmd[0] == '#') continue;
        if (!strcmp(cmd, "frames")) { long n = strtol(a1, 0, 0); for (long i = 0; i < n; i++) run_frame(); }
        else if (!strcmp(cmd, "joy")) { joy = 0; for (char *p = a1; *p; p++) joy |= *p == 'u' ? 1 : *p == 'd' ? 2 : *p == 'l' ? 4 : *p == 'r' ? 8 : *p == 'f' ? 16 : 0; }
        else if (!strcmp(cmd, "random")) {
            long n = strtol(a1, 0, 0); rng = strtoul(a2, 0, 0);
            for (long i = 0; i < n;) { joy = rnd() & 31; if ((joy & 3) == 3) joy &= ~2; if ((joy & 12) == 12) joy &= ~4;
                long hold = 8 + rnd() % 33; for (long k = 0; k < hold && i < n; k++, i++) run_frame(); }
            joy = 0;
        }
        else if (!strcmp(cmd, "key")) { int k = strtol(a1, 0, 16); key_queue[kq_n++] = k; key_queue[kq_n++] = k | 0x80; }
        else if (!strcmp(cmd, "poke")) {
            unsigned a = strtoul(a1, 0, 0), v = strtoul(a2, 0, 0);
            if (a3[0] == 'b') m68k_write_memory_8(a, v); else if (a3[0] == 'l') m68k_write_memory_32(a, v); else m68k_write_memory_16(a, v);
        }
        else if (!strcmp(cmd, "snap")) snapshot(a1);
        else if (!strcmp(cmd, "load")) {
            FILE *i = fopen(a1, "rb"); if (!i) { perror(a1); return 1; }
            unsigned a = strtoul(a2, 0, 0); fread(ram + a, 1, RAM - a, i); fclose(i);
        }
        else if (!strcmp(cmd, "cover")) { FILE *o = fopen(a1, "wb"); fwrite(cover, 1, sizeof cover, o); fclose(o); }
        else if (!strcmp(cmd, "audio")) { audf = fopen(a1, "w"); }
        else if (!strcmp(cmd, "call") || !strcmp(cmd, "play")) {
          long reps = !strcmp(cmd, "play") ? strtol(a2, 0, 0) : 1;
          for (long rep = 0; rep < reps; rep++) {
            unsigned sp = m68k_get_reg(NULL, M68K_REG_SP) - 4, sr = m68k_get_reg(NULL, M68K_REG_SR);
            m68k_write_memory_16(0x1F0, 0x60FE);                 /* bra * : where it returns to */
            m68k_write_memory_32(sp, 0x1F0); m68k_set_reg(M68K_REG_SP, sp);
            if (a2[0] && reps == 1 && strcmp(cmd, "play")) m68k_set_reg(M68K_REG_D0, strtoul(a2, 0, 0));
            m68k_set_reg(M68K_REG_SR, 0x2700); m68k_set_reg(M68K_REG_PC, strtoul(a1, 0, 0));
            until_pc = 0x1F0; until_hit = 0;
            for (long n = 0; n < 2000000 && !until_hit; n++) { run_line(); if (line_no >= 312) { line_no = 0; frame++; } }
            until_pc = 0xFFFFFFFF; until_hit = 0;
            m68k_set_reg(M68K_REG_SR, sr);
            if (reps > 1) { while (line_no < 312) run_line(); line_no = 0; frame++; }
          }
        }
        else if (!strcmp(cmd, "trace")) { trace_pc = strtoul(a1, 0, 0); }
        else if (!strcmp(cmd, "blittime")) { blit_timed = atoi(a1); }
        else if (!strcmp(cmd, "setd1")) { set_d1_pc = strtoul(a1, 0, 0); set_d1_val = strtoul(a2, 0, 0); }
        else if (!strcmp(cmd, "passes")) {
            char b[6][400] = {{0}};
            sscanf(ln, "%*s %399s %399s %399s %399s %399s %399s", b[0], b[1], b[2], b[3], b[4], b[5]);
            pass_left = strtol(b[0], 0, 0); rng = strtoul(b[1], 0, 0); pass_pc = strtoul(b[2], 0, 0);
            pass_every = strtol(b[3], 0, 0); snprintf(pass_prefix, sizeof pass_prefix, "%s", b[4]);
            pass_snap_pc = b[5][0] ? strtoul(b[5], 0, 0) : pass_pc;
            pass_count = 0; pass_hold = 0; pass_done = 0;
            for (long n = 0; n < 500000 && !pass_done; n++) run_frame();
            pass_pc = 0xFFFFFFFF; joy = 0;
        }
        else if (!strcmp(cmd, "watchpc")) { watch_pcs = 1; watch_lo = strtoul(a1, 0, 0); watch_hi = strtoul(a2, 0, 0); seen_n = 0; }
        else if (!strcmp(cmd, "watch")) { watch_pcs = 0; watch_lo = strtoul(a1, 0, 0); watch_hi = strtoul(a2, 0, 0); memset(watched, 0, sizeof watched); }
        else if (!strcmp(cmd, "log")) { logf = fopen(a1, "a"); setvbuf(logf, 0, _IOLBF, 0); }
        else if (!strcmp(cmd, "until")) {
            until_pc = strtoul(a1, 0, 0); until_hit = 0; long n = a2[0] ? strtol(a2, 0, 0) : 100000;
            for (long i = 0; i < n && !until_hit; i++) run_frame();
            printf("until $%X: %s at frame %lu\n", until_pc, until_hit ? "reached" : "NOT reached", frame);
            until_pc = 0xFFFFFFFF; until_hit = 0;
        }
        else fprintf(stderr, "unknown command: %s\n", cmd);
    }
    unsigned ncov = 0; for (unsigned i = 0; i < sizeof cover; i++) ncov += __builtin_popcount(cover[i]);
    printf("frames %lu, instructions at %u addresses, blits %d (%d line mode, %ld words), pc $%X sr $%04X\n", frame, ncov, blits, blit_line, blit_words,
           m68k_get_reg(NULL, M68K_REG_PC), m68k_get_reg(NULL, M68K_REG_SR));
    return 0;
}
