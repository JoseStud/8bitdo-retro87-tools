"""Static vendor analysis only: never loads or executes vendor code.

Usage: inspect_vendor.py bundle APP.exe OUTPUT.dll
       inspect_vendor.py managed ASSEMBLY.dll REGEX
       inspect_vendor.py native DLL EXPORT_OR_ADDRESS
Requires dnfile, dncil, pefile, capstone in the research environment.
"""
import re
import struct
import sys
from pathlib import Path


def bundle(source, output):
    import io
    import zlib
    data = Path(source).read_bytes()
    position = data.find(bytes.fromhex("8b1202b9"))
    if position < 8:
        raise ValueError("Bundle signature not found")
    offset, = struct.unpack_from("<Q", data, position - 8)
    stream = io.BytesIO(data)
    stream.seek(offset)
    major, minor, count = struct.unpack("<III", stream.read(12))
    if major not in (2, 6) or minor != 0 or not 1 <= count <= 10000:
        raise ValueError("Unexpected bundle header")
    def string():
        length, shift = 0, 0
        while True:
            byte = stream.read(1)[0]
            length |= (byte & 127) << shift
            shift += 7
            if not byte & 128:
                break
            if shift > 28:
                raise ValueError("Invalid string length")
        return stream.read(length).decode("utf-8")
    string()
    stream.read(40)
    for _ in range(count):
        start, size = struct.unpack("<QQ", stream.read(16))
        compressed = struct.unpack("<Q", stream.read(8))[0] if major >= 6 else 0
        stream.read(1)
        name = string()
        if name == "8BitDo Ultimate Software V2.dll":
            payload = data[start:start + (compressed or size)]
            if compressed:
                payload = zlib.decompress(payload, -15)
            if len(payload) != size or not payload.startswith(b"MZ"):
                raise ValueError("Invalid embedded assembly")
            with Path(output).open("xb") as file:
                file.write(payload)
            print(name, size, "bytes ->", output)
            return
    raise ValueError("Vendor assembly not found")


def managed(source, pattern):
    import dnfile
    from dncil.cil.body import CilMethodBody
    from dncil.cil.body.reader import CilMethodBodyReaderBytes
    from dncil.clr.token import StringToken, Token
    pe = dnfile.dnPE(source)
    regex = re.compile(pattern, re.I)
    def resolve(value):
        if isinstance(value, StringToken):
            return repr(pe.net.user_strings.get(value.rid).value)
        if isinstance(value, Token):
            table = pe.net.mdtables.tables.get(value.table)
            if table:
                row = table.rows[value.rid-1]
                return str(getattr(row, "Name", getattr(row, "TypeName", value)))
        return str(value)
    for typ in pe.net.mdtables.TypeDef:
        name = str(typ.TypeNamespace) + "." + str(typ.TypeName)
        if regex.search(name):
            print("TYPE", name)
            for field in typ.FieldList:
                print(" FIELD", field.row.Name, field.row.Signature.value.hex())
        for item in typ.MethodList:
            method = item.row
            full = name + "." + str(method.Name)
            if regex.search(full):
                print("METHOD", full, hex(method.Rva))
                if method.Rva:
                    body = CilMethodBody(CilMethodBodyReaderBytes(pe.get_data(method.Rva, 100000)))
                    for ins in body.instructions:
                        print(f" {ins.offset:04x} {ins.opcode.name:14} {resolve(ins.operand)}")


def native(source, name):
    import pefile
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    pe = pefile.PE(source)
    base = pe.OPTIONAL_HEADER.ImageBase
    dis = Cs(CS_ARCH_X86, CS_MODE_32)
    if name.startswith("0x"):
        address = int(name, 16)
    else:
        match = next(s for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name and name in s.name.decode())
        address = base + match.address
    ins = next(dis.disasm(pe.get_data(address-base, 16), address))
    if ins.mnemonic == "jmp" and ins.op_str.startswith("0x"):
        address = int(ins.op_str, 16)
    print(name, hex(address))
    for ins in dis.disasm(pe.get_data(address-base, 16000), address):
        print(f"{ins.address:08x} {ins.mnemonic:8} {ins.op_str}")
        if ins.mnemonic.startswith("ret"):
            break


if __name__ == "__main__":
    import contextlib
    args = sys.argv[2:]
    if "--output" in args:
        index = args.index("--output")
        path = args[index + 1]
        args = args[:index] + args[index + 2:]
        with Path(path).open("w") as output, contextlib.redirect_stdout(output):
            {"bundle": bundle, "managed": managed, "native": native}[sys.argv[1]](*args)
    else:
        {"bundle": bundle, "managed": managed, "native": native}[sys.argv[1]](*args)
