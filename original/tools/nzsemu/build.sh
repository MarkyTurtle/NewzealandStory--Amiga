#!/bin/sh
# Build nzsemu (emu.c) against Musashi (cloned into ../protemu/Musashi by ../protemu/build.sh if needed).
set -e
cd "$(dirname "$0")"
M=../protemu/Musashi
[ -f $M/m68kops.c ] || sh ../protemu/build.sh
cat > conf.h <<'EOC'
#define M68K_INSTRUCTION_HOOK       M68K_OPT_SPECIFY_HANDLER
#define M68K_INSTRUCTION_CALLBACK(pc) instr_hook(pc)
void instr_hook(unsigned int pc);
EOC
gcc -O2 -include conf.h -I$M -o nzsemu emu.c $M/m68kcpu.c $M/m68kops.c $M/m68kdasm.c $M/softfloat/softfloat.c -lm
echo "built $(pwd)/nzsemu"
