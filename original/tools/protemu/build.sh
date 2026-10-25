#!/bin/sh
# Build protemu: harness.c against Musashi (the 68000 core from MAME), with the 68000's trace
# exception, address errors and prefetch switched on. Clones Musashi into ./Musashi if needed.
set -e
cd "$(dirname "$0")"
[ -d Musashi ] || git clone --depth 1 https://github.com/kstenerud/Musashi
cd Musashi
gcc -o m68kmake m68kmake.c
./m68kmake . m68k_in.c > /dev/null
cd ..
cat > conf.h <<'EOF'
#define M68K_EMULATE_TRACE          M68K_OPT_ON
#define M68K_EMULATE_ADDRESS_ERROR  M68K_OPT_ON
#define M68K_EMULATE_PREFETCH       M68K_OPT_ON
#define M68K_INSTRUCTION_HOOK       M68K_OPT_SPECIFY_HANDLER
#define M68K_INSTRUCTION_CALLBACK(pc) instr_hook(pc)
void instr_hook(unsigned int pc);
EOF
gcc -O2 -include conf.h -IMusashi -o protemu harness.c Musashi/m68kcpu.c Musashi/m68kops.c Musashi/m68kdasm.c \
    Musashi/softfloat/softfloat.c -lm
echo "built $(pwd)/protemu"
