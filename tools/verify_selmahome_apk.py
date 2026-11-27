#!/usr/bin/env python3
"""Verify Selma Home APK structure, signing, manifest, DEX, and source assets."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def read_uleb128(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 35, 7):
        require(offset < len(data), "truncated ULEB128")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
    raise VerificationError("oversized ULEB128")


@dataclass
class XmlNode:
    name: str
    attrs: dict[str, object]
    children: list["XmlNode"] = field(default_factory=list)


class StringPool:
    def __init__(self, chunk: bytes):
        require(u16(chunk, 0) == 0x0001, "invalid Android string pool")
        header_size = u16(chunk, 2)
        count = u32(chunk, 8)
        flags = u32(chunk, 16)
        strings_start = u32(chunk, 20)
        utf8 = bool(flags & 0x100)
        offsets = [u32(chunk, header_size + i * 4) for i in range(count)]
        self.values = [self._decode(chunk, strings_start + offset, utf8) for offset in offsets]

    @staticmethod
    def _length8(data: bytes, offset: int) -> tuple[int, int]:
        first = data[offset]
        offset += 1
        if first & 0x80:
            return ((first & 0x7F) << 8) | data[offset], offset + 1
        return first, offset

    @staticmethod
    def _length16(data: bytes, offset: int) -> tuple[int, int]:
        first = u16(data, offset)
        offset += 2
        if first & 0x8000:
            return ((first & 0x7FFF) << 16) | u16(data, offset), offset + 2
        return first, offset

    def _decode(self, data: bytes, offset: int, utf8: bool) -> str:
        if utf8:
            _, offset = self._length8(data, offset)
            length, offset = self._length8(data, offset)
            return data[offset : offset + length].decode("utf-8", errors="strict")
        length, offset = self._length16(data, offset)
        return data[offset : offset + length * 2].decode("utf-16le", errors="strict")

    def get(self, index: int) -> str | None:
        if index == 0xFFFFFFFF:
            return None
        require(0 <= index < len(self.values), f"invalid string pool index {index}")
        return self.values[index]


def typed_value(pool: StringPool, raw_index: int, value_type: int, value: int) -> object:
    raw = pool.get(raw_index)
    if raw is not None:
        return raw
    if value_type == 0x03:
        result = pool.get(value)
        require(result is not None, "null typed string")
        return result
    if value_type in (0x10, 0x11):
        return value
    if value_type == 0x12:
        return bool(value)
    return value


def parse_binary_xml(data: bytes) -> XmlNode:
    require(len(data) >= 8 and u16(data, 0) == 0x0003, "manifest is not Android binary XML")
    require(u32(data, 4) == len(data), "binary XML size mismatch")
    pool: StringPool | None = None
    roots: list[XmlNode] = []
    stack: list[XmlNode] = []
    offset = u16(data, 2)
    while offset < len(data):
        require(offset + 8 <= len(data), "truncated binary XML chunk")
        kind = u16(data, offset)
        header_size = u16(data, offset + 2)
        chunk_size = u32(data, offset + 4)
        require(chunk_size >= header_size >= 8 and offset + chunk_size <= len(data), "invalid binary XML chunk size")
        chunk = data[offset : offset + chunk_size]
        if kind == 0x0001:
            pool = StringPool(chunk)
        elif kind == 0x0102:
            require(pool is not None and header_size >= 16 and chunk_size >= 36, "start element before string pool")
            name = pool.get(u32(chunk, 20))
            require(name is not None, "start element missing name")
            attribute_start = u16(chunk, 24)
            attribute_size = u16(chunk, 26)
            attribute_count = u16(chunk, 28)
            require(attribute_size >= 20, "invalid binary XML attribute size")
            attrs: dict[str, object] = {}
            at = 16 + attribute_start
            for index in range(attribute_count):
                item = at + index * attribute_size
                require(item + 20 <= len(chunk), "truncated binary XML attribute")
                attr_name = pool.get(u32(chunk, item + 4))
                require(attr_name is not None, "attribute missing name")
                attrs[attr_name] = typed_value(pool, u32(chunk, item + 8), chunk[item + 15], u32(chunk, item + 16))
            node = XmlNode(name, attrs)
            if stack:
                stack[-1].children.append(node)
            else:
                roots.append(node)
            stack.append(node)
        elif kind == 0x0103:
            require(stack, "unbalanced binary XML end element")
            stack.pop()
        offset += chunk_size
    require(pool is not None and len(roots) == 1 and not stack, "invalid binary XML tree")
    return roots[0]


def walk(node: XmlNode):
    yield node
    for child in node.children:
        yield from walk(child)


def manifest_summary(data: bytes) -> dict[str, object]:
    root = parse_binary_xml(data)
    require(root.name == "manifest", "manifest root element missing")
    uses_sdk = next((node for node in walk(root) if node.name == "uses-sdk"), None)
    permissions = [str(node.attrs.get("name")) for node in walk(root) if node.name == "uses-permission"]
    activities = []
    categories: set[str] = set()
    actions: set[str] = set()
    for node in walk(root):
        if node.name in ("activity", "activity-alias"):
            activities.append(str(node.attrs.get("name")))
        elif node.name == "category":
            categories.add(str(node.attrs.get("name")))
        elif node.name == "action":
            actions.add(str(node.attrs.get("name")))
    return {
        "package": root.attrs.get("package"),
        "version_code": root.attrs.get("versionCode"),
        "version_name": root.attrs.get("versionName"),
        "compile_sdk": root.attrs.get("compileSdkVersion"),
        "min_sdk": uses_sdk.attrs.get("minSdkVersion") if uses_sdk else None,
        "target_sdk": uses_sdk.attrs.get("targetSdkVersion") if uses_sdk else None,
        "permissions": sorted(permissions),
        "activities": sorted(activities),
        "categories": sorted(categories),
        "actions": sorted(actions),
    }


def split_manifest_sections(data: bytes) -> list[bytes]:
    sections: list[bytes] = []
    start = 0
    while start < len(data):
        candidates = [(data.find(token, start), token) for token in (b"\r\n\r\n", b"\n\n")]
        candidates = [(index, token) for index, token in candidates if index >= 0]
        if not candidates:
            sections.append(data[start:])
            break
        index, token = min(candidates, key=lambda item: item[0])
        end = index + len(token)
        sections.append(data[start:end])
        start = end
    return [section for section in sections if section]


def section_headers(section: bytes) -> dict[str, str]:
    lines = section.replace(b"\r\n", b"\n").split(b"\n")
    unfolded: list[bytes] = []
    for line in lines:
        if line.startswith(b" ") and unfolded:
            unfolded[-1] += line[1:]
        elif line:
            unfolded.append(line)
    headers: dict[str, str] = {}
    for line in unfolded:
        require(b":" in line, "invalid JAR manifest header")
        name, value = line.split(b":", 1)
        headers[name.decode("ascii")] = value.lstrip().decode("utf-8")
    return headers


def verify_jar_digests(archive: zipfile.ZipFile) -> dict[str, object]:
    names = set(archive.namelist())
    require("META-INF/MANIFEST.MF" in names, "JAR manifest missing")
    manifest = archive.read("META-INF/MANIFEST.MF")
    signature_files = sorted(name for name in names if name.upper().startswith("META-INF/") and name.upper().endswith(".SF"))
    require(len(signature_files) == 1, "expected one JAR signature file")
    sf = archive.read(signature_files[0])
    manifest_sections = split_manifest_sections(manifest)
    sf_sections = split_manifest_sections(sf)
    require(manifest_sections and sf_sections, "empty JAR signing metadata")
    sf_main = section_headers(sf_sections[0])
    expected_manifest = base64.b64decode(sf_main["SHA-256-Digest-Manifest"], validate=True)
    require(hashlib.sha256(manifest).digest() == expected_manifest, "signature-file manifest digest mismatch")

    covered: set[str] = set()
    raw_by_name: dict[str, bytes] = {}
    for section in manifest_sections[1:]:
        headers = section_headers(section)
        name = headers.get("Name")
        require(name and name in names, f"manifest references missing entry {name!r}")
        expected = base64.b64decode(headers["SHA-256-Digest"], validate=True)
        require(hashlib.sha256(archive.read(name)).digest() == expected, f"payload digest mismatch: {name}")
        require(name not in covered, f"duplicate manifest section: {name}")
        covered.add(name)
        raw_by_name[name] = section

    payload = {name for name in names if not name.endswith("/") and not name.upper().startswith("META-INF/")}
    require(covered == payload, f"JAR manifest coverage mismatch: missing={sorted(payload-covered)}, extra={sorted(covered-payload)}")
    sf_covered: set[str] = set()
    for section in sf_sections[1:]:
        headers = section_headers(section)
        name = headers.get("Name")
        require(name in raw_by_name, f"signature file references unknown section {name!r}")
        expected = base64.b64decode(headers["SHA-256-Digest"], validate=True)
        require(hashlib.sha256(raw_by_name[name]).digest() == expected, f"manifest-section digest mismatch: {name}")
        sf_covered.add(name)
    require(sf_covered == covered, "signature file does not cover every manifest section")
    return {"payload_entries": len(payload), "signature_file": signature_files[0]}


SIGNATURE_SCHEMES = {
    0x7109871A: "v2",
    0xF05368C0: "v3",
    0x1B93AD61: "v3.1",
}


def apk_signing_block(data: bytes) -> dict[str, object]:
    eocd = -1
    for offset in range(max(0, len(data) - 65557), len(data) - 21):
        if data[offset : offset + 4] == b"PK\x05\x06" and offset + 22 + u16(data, offset + 20) == len(data):
            eocd = offset
    require(eocd >= 0, "ZIP end record missing")
    central_offset = u32(data, eocd + 16)
    require(central_offset >= 24 and data[central_offset - 16 : central_offset] == b"APK Sig Block 42", "APK signing block missing")
    size = u64(data, central_offset - 24)
    start = central_offset - size - 8
    require(start >= 0 and u64(data, start) == size, "APK signing block size mismatch")
    cursor = start + 8
    end = central_offset - 24
    ids: list[int] = []
    while cursor < end:
        pair_size = u64(data, cursor)
        cursor += 8
        require(pair_size >= 4 and cursor + pair_size <= end, "invalid APK signing pair")
        ids.append(u32(data, cursor))
        cursor += pair_size
    require(cursor == end, "APK signing block trailing data")
    schemes = sorted(SIGNATURE_SCHEMES[item] for item in ids if item in SIGNATURE_SCHEMES)
    require(schemes, "APK signing block has no recognized signature scheme")
    return {"schemes_present": schemes, "pair_ids": [f"0x{item:08x}" for item in ids]}


def dex_strings(data: bytes) -> list[str]:
    count = u32(data, 56)
    offset = u32(data, 60)
    require(offset + count * 4 <= len(data), "DEX string table is truncated")
    values: list[str] = []
    for index in range(count):
        at = u32(data, offset + index * 4)
        _, at = read_uleb128(data, at)
        end = data.find(b"\0", at)
        require(end >= 0, "unterminated DEX string")
        values.append(data[at:end].replace(b"\xc0\x80", b"\0").decode("utf-8", errors="replace"))
    return values


def verify_dex(data: bytes) -> dict[str, object]:
    require(len(data) >= 112 and re.fullmatch(rb"dex\n0(3[5-9]|4[0-1])\x00", data[:8]), "invalid DEX magic")
    require(u32(data, 32) == len(data), "DEX declared size mismatch")
    require(data[12:32] == hashlib.sha1(data[32:]).digest(), "DEX SHA-1 signature mismatch")
    require(u32(data, 8) == zlib.adler32(data[12:]) & 0xFFFFFFFF, "DEX Adler-32 checksum mismatch")
    strings = dex_strings(data)
    required = {
        "Lorg/selma/home/Desktop;",
        "Lorg/selma/home/StoryModel;",
        "Lorg/selma/home/ToolServer;",
    }
    require(required.issubset(strings), f"DEX missing Selma classes: {sorted(required-set(strings))}")
    urls = sorted({url for value in strings for url in re.findall(r"https?://[^\s\"']+", value)})
    external = [url for url in urls if not re.match(r"https?://(127\.0\.0\.1|localhost)(?::|/|$)", url)]
    require(not external, f"DEX contains external URL(s): {external}")
    return {
        "version": data[4:7].decode("ascii"),
        "size": len(data),
        "sha256": sha256(data),
        "string_count": len(strings),
        "urls": urls,
    }


def verify_source_assets(archive: zipfile.ZipFile, source: Path) -> dict[str, object]:
    require((source / "AndroidManifest.xml").is_file(), "source manifest missing")
    compared: list[str] = []
    for base in (source / "assets", source / "res" / "raw"):
        if not base.exists():
            continue
        for path in sorted(
            item for item in base.rglob("*")
            if item.is_file()
            and "__pycache__" not in item.parts
            and item.suffix not in {".pyc", ".pyo"}
        ):
            name = path.relative_to(source).as_posix()
            require(name in archive.namelist(), f"APK missing source payload {name}")
            require(archive.read(name) == path.read_bytes(), f"APK payload differs from source: {name}")
            compared.append(name)
    hashes = source / "assets.sha256"
    if hashes.is_file():
        for line in hashes.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            expected, name = line.split(maxsplit=1)
            path = source / name
            if path.is_file():
                payload = path.read_bytes()
            elif name == "assets/model.bin":
                parts = sorted((source / "model").glob("model.bin.part*"))
                require(parts, "source model chunks missing")
                payload = b"".join(part.read_bytes() for part in parts)
            else:
                raise VerificationError(f"source asset missing: {name}")
            require(sha256(payload) == expected, f"source asset digest mismatch: {name}")
            require(name in archive.namelist() and archive.read(name) == payload, f"APK payload differs from source: {name}")
    manifest = ET.parse(source / "AndroidManifest.xml").getroot()
    android = "{http://schemas.android.com/apk/res/android}"
    source_summary = {
        "package": manifest.get("package"),
        "version_code": int(manifest.get(android + "versionCode", "0")),
        "version_name": manifest.get(android + "versionName"),
    }
    return {"files_compared": len(compared), "source_manifest": source_summary}


def verify_with_apksigner(apksigner: str, apk: Path) -> dict[str, object]:
    result = subprocess.run(
        [apksigner, "verify", "--verbose", "--print-certs", str(apk)],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout + result.stderr
    require(result.returncode == 0 and output.startswith("Verifies"), f"apksigner verification failed: {output.strip()}")
    verified = {
        match.group(1): match.group(2) == "true"
        for match in re.finditer(r"Verified using (v[0-9.]+) scheme[^:]*: (true|false)", output)
    }
    require(any(verified.values()), "apksigner reported no valid signature scheme")
    cert = re.search(r"Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]+)", output)
    require(cert is not None, "apksigner certificate digest missing")
    return {"schemes_verified": sorted(name for name, ok in verified.items() if ok), "certificate_sha256": cert.group(1).lower()}


def run(args: argparse.Namespace) -> dict[str, object]:
    apk = args.apk.resolve()
    require(apk.is_file(), f"APK not found: {apk}")
    raw = apk.read_bytes()
    result: dict[str, object] = {
        "schema_version": 1,
        "status": "passed",
        "apk": str(apk),
        "apk_size": len(raw),
        "apk_sha256": sha256(raw),
    }
    with zipfile.ZipFile(apk) as archive:
        require(archive.testzip() is None, "APK ZIP CRC validation failed")
        names = archive.namelist()
        require(len(names) == len(set(names)), "APK contains duplicate entry names")
        require(all(not name.startswith("/") and ".." not in Path(name).parts for name in names), "APK contains unsafe entry path")
        required = {"AndroidManifest.xml", "classes.dex", "resources.arsc", "assets/model.bin", "assets/tok.bin"}
        require(required.issubset(names), f"APK missing required entries: {sorted(required-set(names))}")
        result["zip_entries"] = len(names)
        result["jar_digests"] = verify_jar_digests(archive)
        manifest = manifest_summary(archive.read("AndroidManifest.xml"))
        result["manifest"] = manifest
        require(manifest["version_code"] == 5 and manifest["version_name"] == "0.4.0", "unexpected Selma Home version")
        require(manifest["min_sdk"] == 29 and manifest["target_sdk"] == 35, "unexpected SDK range")
        if args.expected_package:
            require(manifest["package"] == args.expected_package, f"unexpected package: {manifest['package']}")
        require(
            manifest["permissions"] == ["android.permission.INTERNET", "android.permission.RECEIVE_BOOT_COMPLETED"],
            f"unexpected permissions: {manifest['permissions']}",
        )
        for category in ("android.intent.category.DEFAULT", "android.intent.category.HOME", "android.intent.category.LAUNCHER"):
            require(category in manifest["categories"], f"manifest missing {category}")
        result["dex"] = verify_dex(archive.read("classes.dex"))
        if args.source:
            result["source_assets"] = verify_source_assets(archive, args.source.resolve())
        if args.rebuilt_dex:
            rebuilt = args.rebuilt_dex.resolve().read_bytes()
            require(rebuilt == archive.read("classes.dex"), "APK DEX differs from current source rebuild")
            result["rebuilt_dex_match"] = True
    result["signing_block"] = apk_signing_block(raw)
    apksigner = args.apksigner or shutil.which("apksigner")
    if apksigner:
        result["signature"] = verify_with_apksigner(apksigner, apk)
    else:
        result["signature"] = {"cryptographic_verification": "not_run"}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--rebuilt-dex", type=Path)
    parser.add_argument("--apksigner")
    parser.add_argument("--expected-package")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    try:
        result = run(args)
        code = 0
    except Exception as exc:
        result = {"schema_version": 1, "status": "failed", "error": str(exc)}
        code = 1
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
