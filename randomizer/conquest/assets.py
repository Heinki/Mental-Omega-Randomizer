"""Read native artwork from nested and encrypted Westwood archives.

The MIX header/RSA layout is documented by OpenRA's MixFile and
BlowfishKeyProvider readers. Blowfish uses Python's bundled OpenSSL library.
"""

import base64
import ctypes
import ctypes.util
from functools import lru_cache
from pathlib import Path
import re
import ssl
import struct
import sys

from randomizer.core.paths import GAME_ROOT
from randomizer.core.mix import mix_hashes


@lru_cache(maxsize=1)
def _crypto():
    candidates = [str(Path(ssl._ssl.__file__).parent / 'libcrypto-3.dll'),
                  str(Path(getattr(sys, '_MEIPASS', sys.base_prefix)) / 'libcrypto-3.dll'),
                  ctypes.util.find_library('crypto')]
    for name in filter(None, candidates):
        try:
            library = ctypes.CDLL(name)
            library.BF_set_key.restype = None
            library.BF_ecb_encrypt.restype = None
            library.BF_set_key.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
            library.BF_ecb_encrypt.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
            return library
        except (OSError, AttributeError):
            continue
    raise ValueError('OpenSSL Blowfish support is unavailable for installed unit artwork.')


def _decryptor(key_block):
    public = base64.b64decode('AihRvNoIbTn85FZRYNZRcT+i6KpU+maCsEqr3Q5q+LDB5tH7Tz2qQ38V')
    modulus = int.from_bytes(public[2:], 'big')
    width = (modulus.bit_length() - 2) // 8
    key = b''.join(pow(int.from_bytes(key_block[i:i+width+1], 'little'),65537,modulus)
                   .to_bytes(width+1,'little')[:width] for i in range(0,80,width+1))[:56]
    library = _crypto()
    schedule = ctypes.create_string_buffer(4168)  # 18 + 4*256 uint32 values.
    library.BF_set_key(schedule,len(key),key)
    def decrypt(data):
        if len(data)%8:
            raise ValueError('Truncated encrypted MIX header.')
        output = bytearray()
        block = ctypes.create_string_buffer(8)
        for offset in range(0,len(data),8):
            library.BF_ecb_encrypt(data[offset:offset+8],block,schedule,0)
            output.extend(block.raw)
        return bytes(output)
    return decrypt


@lru_cache(maxsize=256)
def _index(path, modified, total, offset=0, length=None):
    length = total if length is None else length
    with Path(path).open('rb') as handle:
        def read(position,count):
            if position<0 or count<0 or position+count>length:
                raise ValueError('Invalid native MIX member bounds.')
            handle.seek(offset+position)
            data=handle.read(count)
            if len(data)!=count:
                raise ValueError('Truncated native MIX member.')
            return data
        first=read(0,6)
        classic=struct.unpack_from('<H',first)[0]!=0
        flags=0 if classic else struct.unpack_from('<I',first)[0]
        if flags&0x20000:
            decrypt=_decryptor(read(4,80))
            count=struct.unpack_from('<H',decrypt(read(84,8)))[0]
            size=(6+count*12+7)//8*8
            header=decrypt(read(84,size))
            data_start=84+size
        else:
            start=0 if classic else 4
            count=struct.unpack_from('<H',read(start,2))[0]
            header=read(start,6+count*12)
            data_start=start+len(header)
        entries={key:(offset+data_start+position,size) for key,position,size in struct.iter_unpack('<III',header[6:6+count*12])}
        # Some installed MO archives retain deleted/stale index entries.
        # Reject those entries individually; valid artwork remains readable.
        return {key: (pos, size) for key, (pos, size) in entries.items()
                if offset <= pos <= offset + length and 0 <= size <= offset + length - pos}


def _find(path, name, *, offset=0, length=None, depth=0):
    stat=path.stat()
    entries=_index(str(path),stat.st_mtime_ns,stat.st_size,offset,length)
    for key in mix_hashes(name):
        if key in entries:
            pos,size=entries[key]
            with path.open('rb') as handle:
                handle.seek(pos)
                return handle.read(size)
    if depth>=3:
        return None
    for nested in ('localmd.mix','local.mix','genericmd.mix','generic.mix','conqmd.mix','conquer.mix',
                   'cachemd.mix','cache.mix','isotemmd.mix','isotemp.mix','temmd.mix','temperat.mix'):
        entry=next((entries[key] for key in mix_hashes(nested) if key in entries),None)
        if entry:
            result=_find(path,name,offset=entry[0],length=entry[1],depth=depth+1)
            if result is not None:
                return result
    return None


def asset(name):
    """Match expansion precedence before falling back to base-game art."""
    def priority(path):
        match=re.fullmatch(r'(expandmo|expandmd|ecachemd|expand|ecache)(\d+)',path.stem,re.I)
        return (({'expandmo':5,'expandmd':4,'ecachemd':3,'expand':2,'ecache':1}[match[1].lower()],int(match[2]),path.name.lower())
                if match else (0,0,path.name.lower()))
    loose=GAME_ROOT/name
    if loose.is_file():
        return loose.read_bytes()
    for path in sorted(GAME_ROOT.glob('*.mix'),key=priority,reverse=True):
        try:
            data=_find(path,name)
        except (ValueError,struct.error):
            continue
        if data is not None:
            return data
    return None
