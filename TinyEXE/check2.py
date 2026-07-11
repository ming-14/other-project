import struct, sys
for f in ['tiny.exe', 'tiny_588.exe', 'tiny_604.exe', 'tiny_packed.exe']:
    path = rf'C:\Users\rikka\Desktop\other-project\TinyEXE\{f}'
    try:
        d = open(path, 'rb').read()
        elf = struct.unpack_from('<I', d, 0x3C)[0]
        m = struct.unpack_from('<H', d, elf+4)[0]
        sz = len(d)
        arch = 'x64' if m == 0x8664 else 'x86' if m == 0x14C else f'0x{m:X}'
        print(f'{f}: {sz} bytes, {arch}')
    except Exception as e:
        print(f'{f}: error - {e}')
