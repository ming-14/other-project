import struct
d = open(r'C:\Users\rikka\Desktop\other-project\TinyEXE\tiny_200.exe','rb').read()
elf = struct.unpack_from('<I', d, 0x3C)[0]
o = elf + 4
oh = o + 20
soh = struct.unpack_from('<H', d, o+16)[0]
sh = oh + soh
print(f"Size: {len(d)}")
print(f"e_lfanew: 0x{elf:X}, PE sig: {d[elf:elf+4]}")
print(f"Machine: 0x{struct.unpack_from('<H', d, o)[0]:X}")
print(f"NSections: {struct.unpack_from('<H', d, o+2)[0]}")
print(f"SOH: 0x{soh:X}")
print(f"Magic: 0x{struct.unpack_from('<H', d, oh)[0]:X}")
print(f"EP: 0x{struct.unpack_from('<I', d, oh+16)[0]:X}")
print(f"IB: 0x{struct.unpack_from('<I', d, oh+28)[0]:X}")
print(f"SA: 0x{struct.unpack_from('<I', d, oh+32)[0]:X}")
print(f"FA: 0x{struct.unpack_from('<I', d, oh+36)[0]:X}")
print(f"SoI: 0x{struct.unpack_from('<I', d, oh+56)[0]:X}")
print(f"SoH: 0x{struct.unpack_from('<I', d, oh+60)[0]:X}")
print(f"Sub: {struct.unpack_from('<H', d, oh+68)[0]}")
print(f"Nrvas: {struct.unpack_from('<I', d, oh+92)[0]}")
print(f"Section at: 0x{sh:X}")
print(f"VS: 0x{struct.unpack_from('<I', d, sh+8)[0]:X}")
print(f"VA: 0x{struct.unpack_from('<I', d, sh+12)[0]:X}")
print(f"SRD: 0x{struct.unpack_from('<I', d, sh+16)[0]:X}")
print(f"PTRD: 0x{struct.unpack_from('<I', d, sh+20)[0]:X}")
print(f"Chars: 0x{struct.unpack_from('<I', d, sh+36)[0]:X}")
print(f"First code bytes: {d[0x200:0x220].hex()}")
