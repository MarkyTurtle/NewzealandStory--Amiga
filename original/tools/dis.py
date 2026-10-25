"""dis.py FILE BASE START END  - quick capstone 68000 listing (BASE = load address of offset 0)"""
import sys, capstone
f,base,s,e=sys.argv[1],int(sys.argv[2],0),int(sys.argv[3],0),int(sys.argv[4],0)
d=open(f,'rb').read()
md=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000)
md.skipdata=True
for i in md.disasm(d[s-base:e-base],s):
    print(f"{i.address:06X}  {i.bytes.hex():<20} {i.mnemonic} {i.op_str}")
