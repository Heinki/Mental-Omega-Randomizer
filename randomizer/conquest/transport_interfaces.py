"""Local interface discovery for explicit ZeroTier-only lobby listeners."""

import ctypes
import ipaddress
import os
import socket
import sys


def unicast_ipv4(value):
    """Return an explicit IPv4 address, never a wildcard or broadcast bind."""
    try:
        address = ipaddress.IPv4Address(str(value).strip())
    except ipaddress.AddressValueError:
        raise ValueError('A specific IPv4 address is required for co-op networking.') from None
    if address.is_unspecified or address.is_multicast or int(address) == 0xFFFFFFFF:
        raise ValueError('Co-op networking requires a specific unicast IPv4 address.')
    return str(address)


def zerotier_ipv4_addresses():
    """Discover active ZeroTier adapters without a service token or CLI tool."""
    interfaces = _windows_interfaces() if os.name == 'nt' else _posix_interfaces()
    addresses = set()
    for names, address in interfaces:
        if any('zerotier' in name.casefold() or name.casefold().startswith('zt')
               for name in names):
            addresses.add(unicast_ipv4(address))
    if not addresses:
        raise ValueError(
            'No active ZeroTier IPv4 interface was found. Connect to your ZeroTier '
            'network and check its Managed IPv4 before hosting.')
    return tuple(sorted(addresses))


def _windows_interfaces():
    # These are the documented IP Helper structure prefixes. Keeping the
    # unused tail out lets Windows report its full structure version/length.
    class SocketAddress(ctypes.Structure):
        _fields_ = [('address', ctypes.c_void_p), ('length', ctypes.c_int)]

    class UnicastAddress(ctypes.Structure):
        pass

    UnicastAddress._fields_ = [
        ('alignment', ctypes.c_uint64), ('next', ctypes.POINTER(UnicastAddress)),
        ('socket_address', SocketAddress),
    ]

    class AdapterAddress(ctypes.Structure):
        pass

    AdapterAddress._fields_ = [
        ('alignment', ctypes.c_uint64), ('next', ctypes.POINTER(AdapterAddress)),
        ('name', ctypes.c_char_p), ('unicast', ctypes.POINTER(UnicastAddress)),
        ('anycast', ctypes.c_void_p), ('multicast', ctypes.c_void_p),
        ('dns_server', ctypes.c_void_p), ('dns_suffix', ctypes.c_wchar_p),
        ('description', ctypes.c_wchar_p), ('friendly_name', ctypes.c_wchar_p),
        ('physical_address', ctypes.c_ubyte * 8), ('physical_length', ctypes.c_uint32),
        ('flags', ctypes.c_uint32), ('mtu', ctypes.c_uint32),
        ('interface_type', ctypes.c_uint32), ('status', ctypes.c_uint32),
    ]
    get_addresses = ctypes.WinDLL('iphlpapi').GetAdaptersAddresses
    get_addresses.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    get_addresses.restype = ctypes.c_uint32
    size = ctypes.c_uint32(15000)
    for _ in range(3):
        buffer = ctypes.create_string_buffer(size.value)
        result = get_addresses(socket.AF_INET, 0xE, None, buffer, ctypes.byref(size))
        if result != 111:  # ERROR_BUFFER_OVERFLOW asks for a larger buffer.
            break
    if result == 232:  # ERROR_NO_DATA
        return []
    if result:
        raise OSError(result, 'Cannot inspect local network adapters.')
    interfaces = []
    adapter = ctypes.cast(buffer, ctypes.POINTER(AdapterAddress))
    while adapter:
        values = adapter.contents
        names = ((values.name or b'').decode(errors='replace'),
                 values.description or '', values.friendly_name or '')
        if values.status == 1:  # IfOperStatusUp
            address = values.unicast
            while address:
                value = address.contents.socket_address
                if value.address and value.length >= 16:
                    raw = ctypes.string_at(value.address, 16)
                    if int.from_bytes(raw[:2], sys.byteorder) == socket.AF_INET:
                        interfaces.append((names, socket.inet_ntoa(raw[4:8])))
                address = address.contents.next
        adapter = values.next
    return interfaces


def _posix_interfaces():
    class InterfaceAddress(ctypes.Structure):
        pass

    InterfaceAddress._fields_ = [
        ('next', ctypes.POINTER(InterfaceAddress)), ('name', ctypes.c_char_p),
        ('flags', ctypes.c_uint), ('address', ctypes.c_void_p),
        ('netmask', ctypes.c_void_p), ('destination', ctypes.c_void_p),
        ('data', ctypes.c_void_p),
    ]
    library = ctypes.CDLL(None, use_errno=True)
    get_addresses = library.getifaddrs
    get_addresses.argtypes = [ctypes.POINTER(ctypes.POINTER(InterfaceAddress))]
    get_addresses.restype = ctypes.c_int
    library.freeifaddrs.argtypes = [ctypes.POINTER(InterfaceAddress)]
    library.freeifaddrs.restype = None
    first = ctypes.POINTER(InterfaceAddress)()
    if get_addresses(ctypes.byref(first)):
        raise OSError(ctypes.get_errno(), 'Cannot inspect local network adapters.')
    interfaces = []
    try:
        current = first
        while current:
            values = current.contents
            if values.address and values.flags & 1:  # IFF_UP
                header = ctypes.string_at(values.address, 2)
                family = header[1] if sys.platform == 'darwin' else int.from_bytes(header, sys.byteorder)
                if family == socket.AF_INET:
                    raw = ctypes.string_at(values.address, 16)
                    interfaces.append((((values.name or b'').decode(errors='replace'),),
                                       socket.inet_ntoa(raw[4:8])))
            current = values.next
    finally:
        library.freeifaddrs(first)
    return interfaces
