import struct, os

def ror13(name):
    h = 0
    for c in name + '\0':
        h = ((h >> 13) | (h << 19)) & 0xFFFFFFFF
        h = (h + ord(c)) & 0xFFFFFFFF
    return h

HWF = ror13("WriteFile")
HEP = ror13("ExitProcess")
msg = b"This is a demo program.\r\n"
ML = len(msg)

c = bytearray()
def E(b):
    if isinstance(b, int): c.append(b)
    else: c.extend(b)

# PEB walk -> kernel32 base in edi
E(b'\x64\xA1\x30\x00\x00\x00')  # mov eax,fs:[30]
E(b'\x8B\x40\x0C')               # mov eax,[eax+C]
E(b'\x8B\x40\x14')               # mov eax,[eax+14]
E(b'\x8B\x00')                    # mov eax,[eax]
E(b'\x8B\x00')                    # mov eax,[eax]
E(b'\x8B\x78\x10')               # mov edi,[eax+10]

# Get stdout from PEB -> esi
E(b'\x64\xA1\x30\x00\x00\x00')  # mov eax,fs:[30]
E(b'\x8B\x40\x10')               # mov eax,[eax+10]
E(b'\x8B\x70\x1C')               # mov esi,[eax+1C]

# Find WriteFile
E(b'\x68'); E(struct.pack('<I', HWF))
E(b'\x57')
E(b'\xE8'); E(struct.pack('<i', 0)); cwf = len(c) - 4

# WriteFile(stdout, msg, ML, 0, 0)
E(b'\x6A\x00\x6A\x00')
E(b'\x6A' + bytes([ML]))
E(b'\x68'); E(struct.pack('<I', 0)); mvp = len(c) - 4
E(b'\x56\xFF\xD0')

# Find ExitProcess
E(b'\x68'); E(struct.pack('<I', HEP))
E(b'\x57')
E(b'\xE8'); E(struct.pack('<i', 0)); cep = len(c) - 4

# ExitProcess(0)
E(b'\x6A\x00\xFF\xD0')

# --- find_func ---
ffs = len(c)
E(b'\x53\x55\x56\x57')          # push ebx,ebp,esi,edi
E(b'\x8B\x44\x24\x18')          # mov eax,[esp+24]
E(b'\x8B\x4C\x24\x14')          # mov ecx,[esp+20]
E(b'\x8B\xE8')                   # mov ebp,eax
E(b'\x8B\x50\x3C')              # mov edx,[eax+3C]
E(b'\x8B\x54\x10\x78')          # mov edx,[eax+edx+78]
E(b'\x01\xEA')                   # add edx,ebp
E(b'\x51')                       # push ecx
E(b'\x8B\x4A\x18')              # mov ecx,[edx+18]
E(b'\x8B\x5A\x20')              # mov ebx,[edx+20]
E(b'\x01\xEB')                   # add ebx,ebp

lo = len(c)
E(b'\x49')                       # dec ecx
E(b'\x78\x00'); jf = len(c) - 1  # js fail
E(b'\x8B\x34\x8B')              # mov esi,[ebx+ecx*4]
E(b'\x01\xEE')                   # add esi,ebp
E(b'\x31\xFF')                   # xor edi,edi
ho = len(c)
E(b'\xAC\x84\xC0')              # lodsb; test al,al
E(b'\x74\x00'); jz = len(c) - 1  # jz cmp
E(b'\xC1\xCF\x0D')              # ror edi,13
E(b'\x01\xC7')                   # add edi,eax
E(b'\xEB'); E((ho - (len(c) + 1)) & 0xFF)
co = len(c); c[jz] = (co - jz - 2) & 0xFF
E(b'\x39\x3C\x24')              # cmp [esp],edi
E(b'\x75'); E((lo - (len(c) + 1)) & 0xFF)
E(b'\x8B\x42\x24\x01\xE8')      # mov eax,[edx+24]; add eax,ebp
E(b'\x0F\xB7\x0C\x48')          # movzx ecx,word[eax+ecx*2]
E(b'\x8B\x42\x1C\x01\xE8')      # mov eax,[edx+1C]; add eax,ebp
E(b'\x8B\x04\x88\x01\xE8')      # mov eax,[eax+ecx*4]; add eax,ebp
E(b'\x59\x5F\x5E\x5D\x5B')      # pop ecx,edi,esi,ebp,ebx
E(b'\xC2\x08\x00')              # ret 8
fo = len(c); c[jf] = (fo - jf - 2) & 0xFF
E(b'\x59\x31\xC0\x5F\x5E\x5D\x5B\xC2\x08\x00')

# message
moff = len(c); c.extend(msg)

# Build PE
IB = 0x400000; SA = 0x1000; FA = 0x200
HDR = 0x200  # headers take 0x200 bytes on disk
CRVA = SA; CPTR = HDR

# patch calls
ff_file = ffs + CPTR
struct.pack_into('<i', c, cwf, ff_file - (cwf + CPTR + 5))
struct.pack_into('<i', c, cep, ff_file - (cep + CPTR + 5))
struct.pack_into('<I', c, mvp, IB + CRVA + moff)

csz = ((len(c) + FA - 1) // FA) * FA
pe = bytearray(HDR + csz)

# DOS
pe[0]=0x4D; pe[1]=0x5A
struct.pack_into('<I', pe, 0x3C, 0x80)

# PE sig
struct.pack_into('<I', pe, 0x80, 0x4550)

# COFF
struct.pack_into('<H', pe, 0x84, 0x14C)
struct.pack_into('<H', pe, 0x86, 1)
struct.pack_into('<H', pe, 0x94, 0xE0)
struct.pack_into('<H', pe, 0x96, 0x0102)

# Optional header
O = 0x98
struct.pack_into('<H', pe, O, 0x010B)
struct.pack_into('<I', pe, O+16, CRVA)
struct.pack_into('<I', pe, O+28, IB)
struct.pack_into('<I', pe, O+32, SA)
struct.pack_into('<I', pe, O+36, FA)
struct.pack_into('<H', pe, O+40, 6)
struct.pack_into('<H', pe, O+48, 6)
struct.pack_into('<I', pe, O+56, SA + ((len(c)+SA-1)//SA)*SA)
struct.pack_into('<I', pe, O+60, HDR)
struct.pack_into('<H', pe, O+68, 3)
struct.pack_into('<I', pe, O+72, 0x100000)
struct.pack_into('<I', pe, O+76, 0x1000)
struct.pack_into('<I', pe, O+80, 0x100000)
struct.pack_into('<I', pe, O+84, 0x1000)
struct.pack_into('<I', pe, O+92, 0)

# Section
S = 0x178
pe[S]=0x2E
struct.pack_into('<I', pe, S+8, len(c))
struct.pack_into('<I', pe, S+12, CRVA)
struct.pack_into('<I', pe, S+16, csz)
struct.pack_into('<I', pe, S+20, CPTR)
struct.pack_into('<I', pe, S+36, 0xE0000060)

pe[CPTR:CPTR+len(c)] = c

out = r'C:\Users\rikka\Desktop\other-project\TinyEXE\tiny_200.exe'
with open(out, 'wb') as f: f.write(pe)
print(f"Size: {len(pe)} bytes, Code: {len(c)} bytes")
