#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cst_parser.py — CST Studio Suite 项目文件 (.cst) 逆向解析器

格式背景（逆向分析结论）：
    .cst 是 CST 定制的 ZIP 变体容器（"DE-ZIP"），与标准 ZIP 的差异：
      1. 本地文件头签名   PK\x03\x04 (30字节)  ->  DE\x03\x04 (34字节)
      2. 中央目录条目签名 PK\x01\x02 (46字节)  ->  DE\x01\x02 (50字节)
      3. 结束记录 EOCD 保持标准 PK\x05\x06，注释区存储 CST 版本/license 信息
    两种头部均在标准 ZIP 布局的 "DOS date" 与 "CRC32" 之间插入了 4 字节
    额外字段 X（疑似 DOS date+time 打包的修改时间），后续字段整体后移。
    压缩方法沿用标准值：8=deflate（raw，无 zlib 头），0=store。

用法：
    python cst_parser.py phone.cst                 # 查看容器信息 + 条目清单
    python cst_parser.py phone.cst -o extracted/   # 全量提取并生成 manifest.json

仅依赖 Python 标准库。
"""

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path

# ---------------- 容器格式常量 ----------------
LOCAL_SIG = b"DE\x03\x04"      # 本地文件头签名（ZIP 为 PK\x03\x04）
CENTRAL_SIG = b"DE\x01\x02"    # 中央目录条目签名（ZIP 为 PK\x01\x02）
EOCD_SIG = b"PK\x05\x06"       # 结束记录保持标准 ZIP 签名

LOCAL_HEADER_SIZE = 34         # sig4 ver2 flags2 method2 t2 d2 X4 crc4 csize4 usize4 fnlen2 exlen2
CENTRAL_HEADER_SIZE = 50       # 本地头字段 + made-by2 + cmtlen2 disk2 iattr2 eattr4 lhoff4
EOCD_SIZE = 22

LOCAL_FMT = "<IHHHHHIIIIHH"
CENTRAL_FMT = "<IHHHHHHIIIIHHHHHII"

METHOD_STORE = 0
METHOD_DEFLATE = 8


class CstParseError(Exception):
    """容器解析致命错误"""


# ---------------- EOCD ----------------
def find_eocd(data_tail: bytes, file_size: int):
    """在文件尾部窗口内定位 EOCD，返回 (eocd_off, cd_off, cd_size, entry_count, comment)。"""
    pos = data_tail.rfind(EOCD_SIG)
    while pos >= 0:
        if pos + EOCD_SIZE <= len(data_tail):
            (_sig, _disk, _cddisk, n_disk, n_total, cd_size, cd_off,
             cmlen) = struct.unpack("<4sHHHHIIH", data_tail[pos:pos + EOCD_SIZE])
            # 有效候选：注释长度恰好填满到文件末尾
            if pos + EOCD_SIZE + cmlen == len(data_tail) and n_disk == n_total:
                comment = data_tail[pos + EOCD_SIZE:pos + EOCD_SIZE + cmlen]
                return pos, cd_off, cd_size, n_total, comment
        pos = data_tail.rfind(EOCD_SIG, 0, pos)
    raise CstParseError("未找到有效的 EOCD 记录（PK\\x05\\x06），不是可识别的 .cst 容器")


def parse_eocd_comment(comment: bytes) -> dict:
    """解析 EOCD 注释中的 CST 元信息，如:
    -cst-version:2024:0:20230801-license:In-house License DSDEU073-..."""
    text = comment.decode("utf-8", "replace")
    info = {"comment_raw": text}
    if "-cst-version:" in text:
        rest = text.split("-cst-version:", 1)[1]
        version, _, license_part = rest.partition("-license:")
        info["cst_version"] = version
        if license_part:
            info["license"] = license_part
    return info


# ---------------- 中央目录 ----------------
def parse_central_directory(cd_data: bytes, expected_count: int):
    """解析中央目录，返回条目 dict 列表。"""
    entries = []
    off = 0
    while off < len(cd_data):
        if off + CENTRAL_HEADER_SIZE > len(cd_data):
            raise CstParseError("中央目录截断：条目头不完整")
        (sig, vmade, vneed, flags, method, t, d, x, crc, csize, usize,
         fnlen, exlen, cmlen, disk, iattr, eattr, lhoff) = struct.unpack(
            CENTRAL_FMT, cd_data[off:off + CENTRAL_HEADER_SIZE])
        if sig != struct.unpack("<I", CENTRAL_SIG)[0]:
            raise CstParseError(f"中央目录条目签名错误 @+{off}: {sig:#010x}")
        end = off + CENTRAL_HEADER_SIZE + fnlen + exlen + cmlen
        if end > len(cd_data):
            raise CstParseError("中央目录截断：文件名/附加数据越界")
        name_bytes = cd_data[off + CENTRAL_HEADER_SIZE:off + CENTRAL_HEADER_SIZE + fnlen]
        if flags & 0x800:  # bit11: UTF-8 文件名
            name = name_bytes.decode("utf-8", "replace")
        else:
            name = name_bytes.decode("cp437", "replace")
        entries.append({
            "index": len(entries),
            "name": name,
            "version_made_by": vmade,
            "version_needed": vneed,
            "flags": flags,
            "method": method,
            "time_field_t": t,
            "time_field_d": d,
            "time_field_x": x,
            "crc32": crc,
            "compressed_size": csize,
            "uncompressed_size": usize,
            "external_attrs": eattr,
            "local_header_offset": lhoff,
            "_cd_entry_size": CENTRAL_HEADER_SIZE + fnlen + exlen + cmlen,
        })
        off = end
    if expected_count is not None and len(entries) != expected_count:
        raise CstParseError(
            f"条目数不匹配：EOCD 声明 {expected_count}，实际解析 {len(entries)}")
    return entries


# ---------------- 本地头与数据 ----------------
def read_entry(f, entry):
    """按本地头定位并读出条目数据，返回 (content, crc_ok, local_fields)。"""
    lhoff = entry["local_header_offset"]
    f.seek(lhoff)
    header = f.read(LOCAL_HEADER_SIZE)
    if len(header) < LOCAL_HEADER_SIZE:
        raise CstParseError(f"本地头读取失败（文件越界）@{lhoff}: {entry['name']}")
    (sig, _ver, _flags, method, t, d, x, crc, csize, usize,
     fnlen, exlen) = struct.unpack(LOCAL_FMT, header)
    if sig != struct.unpack("<I", LOCAL_SIG)[0]:
        raise CstParseError(
            f"本地头签名错误 @{lhoff}（{sig:#010x}）: {entry['name']}")
    data_start = lhoff + LOCAL_HEADER_SIZE + fnlen + exlen
    f.seek(data_start)
    raw = f.read(csize)
    if len(raw) != csize:
        raise CstParseError(f"数据读取不完整: {entry['name']}")

    if method == METHOD_DEFLATE:
        content = zlib.decompress(raw, -15)  # raw deflate
    elif method == METHOD_STORE:
        content = raw
    else:
        raise CstParseError(f"不支持的压缩方法 {method}: {entry['name']}")

    local = {"method": method, "crc32": crc, "compressed_size": csize,
             "uncompressed_size": usize, "time_field_t": t,
             "time_field_d": d, "time_field_x": x}
    # 本地头与中央目录一致性检查
    for key in ("crc32", "compressed_size", "uncompressed_size", "method"):
        if local[key] != entry[key]:
            raise CstParseError(
                f"本地头与中央目录字段不一致 ({key}): {entry['name']}")
    crc_ok = (zlib.crc32(content) & 0xFFFFFFFF) == crc
    if len(content) != usize:
        raise CstParseError(
            f"解压后大小不符（声明 {usize}，实际 {len(content)}）: {entry['name']}")
    return content, crc_ok, local


# ---------------- 时间字段解释（假说） ----------------
def decode_dos_date(v):
    year = 1980 + ((v >> 9) & 0x7F)
    month = (v >> 5) & 0xF
    day = v & 0x1F
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def decode_dos_time(v):
    hour = (v >> 11) & 0x1F
    minute = (v >> 5) & 0x3F
    second = (v & 0x1F) * 2
    if hour > 23 or minute > 59 or second > 59:
        return None
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def interpret_time_fields(entry):
    """X 字段（本地头 0x0E, 4字节）假说：低16位=DOS日期，高16位=DOS时间。"""
    x = entry["time_field_x"]
    out = {
        "t_raw": f"{entry['time_field_t']:#06x}",
        "d_raw": f"{entry['time_field_d']:#06x}",
        "x_raw": f"{x:#010x}",
    }
    date = decode_dos_date(x & 0xFFFF)
    time = decode_dos_time((x >> 16) & 0xFFFF)
    if date:
        out["x_as_datetime"] = f"{date} {time or '00:00:00'}"
    t_time = decode_dos_time(entry["time_field_t"])
    if t_time:
        out["t_as_time"] = t_time
    return out


# ---------------- 文件类型嗅探 ----------------
def sniff_type(content: bytes, name: str) -> str:
    if not content:
        return "empty"
    head = content[:512].lstrip()
    if content.startswith(b"ACIS BinaryFile"):
        return "ACIS binary geometry (SAB/SAT)"
    if content.startswith(b"BM"):
        return "BMP image"
    if name.lower().endswith(".dib") and len(content) >= 4:
        dib_hdr_size = struct.unpack("<I", content[:4])[0]
        if dib_hdr_size in (12, 40, 52, 56, 64, 108, 124):
            return "DIB bitmap (BITMAPINFOHEADER)"
    if head[:1] in (b"{", b"["):
        return "JSON text"
    if head[:5] == b"<?xml" or head[:1] == b"<":
        return "XML text"
    sample = content[:1024]
    try:
        sample.decode("utf-8")
        if sum(b < 0x20 and b not in (0x09, 0x0A, 0x0D) for b in sample) == 0:
            return "text"
    except UnicodeDecodeError:
        pass
    return "binary"


# ---------------- 输出路径安全 ----------------
def safe_out_path(root: Path, name: str) -> Path:
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise CstParseError(f"不安全的条目名称: {name!r}")
    if any(len(p) > 255 for p in parts):
        raise CstParseError(f"路径分量过长: {name!r}")
    return root.joinpath(*parts)


# ---------------- 读入 / 写出 ----------------
DEFAULT_EOCD_COMMENT = b"-cst-version:2024:0:cstdecoding\n"

_NEW_PROJECT_MOD = (
    "'@ new project\n"
    "With Units\n"
    '     .SetUnit "Length", "mm"\n'
    '     .SetUnit "Frequency", "GHz"\n'
    '     .SetUnit "Time", "ns"\n'
    "End With\n"
    'Component.New "component1"\n'
)

_NEW_PROJECT_PARAMS = (
    '{\n  "parameters": [],\n  "version": 1\n}\n'
)


def _dos_now() -> tuple[int, int, int]:
    """Return (t, d, x) DOS time fields used in DE-ZIP headers."""
    import datetime
    now = datetime.datetime.now()
    t = (now.hour << 11) | (now.minute << 5) | (now.second // 2)
    d = ((now.year - 1980) << 9) | (now.month << 5) | now.day
    x = ((t & 0xFFFF) << 16) | (d & 0xFFFF)
    return t & 0xFFFF, d & 0xFFFF, x & 0xFFFFFFFF


def _filename_bytes(name: str) -> tuple[bytes, int]:
    name = name.replace("\\", "/")
    try:
        return name.encode("cp437"), 0
    except UnicodeEncodeError:
        return name.encode("utf-8"), 0x800


def _deflate_raw(data: bytes) -> bytes:
    co = zlib.compressobj(6, zlib.DEFLATED, -15)
    return co.compress(data) + co.flush()


def open_cst(path) -> tuple[dict, list]:
    """Load a .cst into memory. Each entry dict includes ``content`` bytes."""
    cst_path = Path(path)
    if not cst_path.is_file():
        raise CstParseError(f"文件不存在: {cst_path}")
    file_size = cst_path.stat().st_size
    with open(cst_path, "rb") as f:
        window = min(file_size, 65535 + EOCD_SIZE)
        f.seek(file_size - window)
        tail = f.read(window)
        eocd_off_in_tail, cd_off, cd_size, count, comment = find_eocd(tail, file_size)
        eocd_off = file_size - window + eocd_off_in_tail
        f.seek(cd_off)
        cd_data = f.read(cd_size)
        if len(cd_data) != cd_size:
            raise CstParseError("中央目录读取不完整")
        entries = parse_central_directory(cd_data, count)
        for e in entries:
            content, crc_ok, _local = read_entry(f, e)
            e["content"] = content
            e["crc_ok"] = crc_ok
    meta = parse_eocd_comment(comment)
    meta.update({
        "file_name": cst_path.name,
        "file_size": file_size,
        "eocd_offset": eocd_off,
        "cd_offset": cd_off,
        "cd_size": cd_size,
        "comment_bytes": comment,
    })
    return meta, entries


def write_cst(path, files, comment: bytes = DEFAULT_EOCD_COMMENT) -> None:
    """Write a DE-ZIP .cst from ``(name, content_bytes)`` pairs."""
    if not comment:
        comment = DEFAULT_EOCD_COMMENT
    if isinstance(comment, str):
        comment = comment.encode("utf-8")
    items = []
    for item in files:
        if isinstance(item, dict):
            name, content = item["name"], item["content"]
        else:
            name, content = item
        if isinstance(content, str):
            content = content.encode("utf-8")
        items.append((str(name).replace("\\", "/"), bytes(content)))
    if not items:
        raise CstParseError("不能写出空的 .cst 容器")
    t, d, x = _dos_now()
    local_parts = []
    central_parts = []
    offset = 0
    sig_local = struct.unpack("<I", LOCAL_SIG)[0]
    sig_central = struct.unpack("<I", CENTRAL_SIG)[0]
    for name, content in items:
        fn, flags = _filename_bytes(name)
        crc = zlib.crc32(content) & 0xFFFFFFFF
        usize = len(content)
        compressed = _deflate_raw(content)
        if len(compressed) >= usize:
            method, payload = METHOD_STORE, content
        else:
            method, payload = METHOD_DEFLATE, compressed
        csize = len(payload)
        local = struct.pack(
            LOCAL_FMT, sig_local, 20, flags, method, t, d, x,
            crc, csize, usize, len(fn), 0)
        blob = local + fn + payload
        central = struct.pack(
            CENTRAL_FMT, sig_central, 20, 20, flags, method, t, d, x,
            crc, csize, usize, len(fn), 0, 0, 0, 0, 0, offset)
        local_parts.append(blob)
        central_parts.append(central + fn)
        offset += len(blob)
    body = b"".join(local_parts)
    cd = b"".join(central_parts)
    n = len(items)
    if n > 0xFFFF:
        raise CstParseError("条目数超过 DE-ZIP 16 位上限")
    eocd = struct.pack(
        "<4sHHHHIIH", EOCD_SIG, 0, 0, n, n, len(cd), len(body), len(comment))
    Path(path).write_bytes(body + cd + eocd + comment)


def new_project_files() -> list[tuple[str, bytes]]:
    """Minimal CST project payload for File → New."""
    return [
        ("Model/3D/Model.mod", _NEW_PROJECT_MOD.encode("latin-1")),
        ("Model/Parameters.json", _NEW_PROJECT_PARAMS.encode("utf-8")),
    ]


# ---------------- 主流程 ----------------
def print_summary(meta, entries, results):
    print("=" * 78)
    print(f"文件: {meta['file_name']}  ({meta['file_size']:,} bytes)")
    print(f"容器: CST DE-ZIP 变体  |  条目数: {len(entries)}")
    print(f"CST 版本: {meta.get('cst_version', '?')}  |  License: {meta.get('license', '?')}")
    print(f"中央目录: @{meta['cd_offset']:,} (size {meta['cd_size']:,})  "
          f"EOCD: @{meta['eocd_offset']:,}")
    print("=" * 78)
    hdr = f"{'idx':>3} {'method':<8} {'csize':>9} {'usize':>9}  {'crc':<6} {'type':<28} name"
    print(hdr)
    print("-" * 78)
    for e in entries:
        r = results[e["index"]]
        method = "deflate" if e["method"] == METHOD_DEFLATE else (
            "store" if e["method"] == METHOD_STORE else str(e["method"]))
        crc = "OK" if r["crc_ok"] else "FAIL"
        print(f"{e['index']:>3} {method:<8} {e['compressed_size']:>9,} "
              f"{e['uncompressed_size']:>9,}  {crc:<6} {r['type']:<28} {e['name']}")
    print("-" * 78)
    tc = sum(e["compressed_size"] for e in entries)
    tu = sum(e["uncompressed_size"] for e in entries)
    bad = sum(1 for r in results if not r["crc_ok"])
    print(f"合计: 压缩 {tc:,} B -> 解压 {tu:,} B | CRC 校验: "
          f"{len(entries) - bad}/{len(entries)} 通过" + ("  [存在校验失败!]" if bad else ""))


def main():
    ap = argparse.ArgumentParser(
        description="CST Studio .cst 项目文件逆向解析/提取工具")
    ap.add_argument("cst_file", help="输入 .cst 文件路径")
    ap.add_argument("-o", "--output", metavar="DIR",
                    help="提取到指定目录（默认仅列出清单不提取）")
    ap.add_argument("--manifest", metavar="FILE",
                    help="manifest.json 输出路径（默认随提取目录）")
    args = ap.parse_args()

    cst_path = Path(args.cst_file)
    if not cst_path.is_file():
        print(f"错误: 文件不存在: {cst_path}", file=sys.stderr)
        return 1

    file_size = cst_path.stat().st_size
    with open(cst_path, "rb") as f:
        # 1) 定位 EOCD（标准 PK\x05\x06）
        window = min(file_size, 65535 + EOCD_SIZE)
        f.seek(file_size - window)
        tail = f.read(window)
        eocd_off_in_tail, cd_off, cd_size, count, comment = find_eocd(tail, file_size)
        eocd_off = file_size - window + eocd_off_in_tail

        # 2) 解析中央目录
        f.seek(cd_off)
        cd_data = f.read(cd_size)
        if len(cd_data) != cd_size:
            raise CstParseError("中央目录读取不完整")
        if cd_off + cd_size > eocd_off:
            raise CstParseError("中央目录与 EOCD 位置冲突")
        entries = parse_central_directory(cd_data, count)

        # 3) 逐条读取数据（seek 方式，内存占用与单条数据量相当）
        results = []
        for e in entries:
            try:
                content, crc_ok, _local = read_entry(f, e)
                results.append({"crc_ok": crc_ok, "content": content,
                                "error": None})
            except (CstParseError, zlib.error) as exc:
                results.append({"crc_ok": False, "content": None,
                                "error": str(exc)})

        # 4) 提取
        out_root = Path(args.output) if args.output else None
        if out_root is not None:
            out_root.mkdir(parents=True, exist_ok=True)
            for e in entries:
                r = results[e["index"]]
                if r["content"] is None:
                    continue
                out_path = safe_out_path(out_root, e["name"])
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(r["content"])
                r["extracted_path"] = str(out_path)

        # 5) 类型嗅探 + manifest
        for e in entries:
            r = results[e["index"]]
            r["type"] = sniff_type(r["content"], e["name"]) if r["content"] is not None else "N/A"

        meta = parse_eocd_comment(comment)
        meta.update({
            "file_name": cst_path.name,
            "file_size": file_size,
            "eocd_offset": eocd_off,
            "cd_offset": cd_off,
            "cd_size": cd_size,
        })

        print_summary(meta, entries, results)

        # 6) manifest.json
        manifest_path = Path(args.manifest) if args.manifest else (
            out_root / "manifest.json" if out_root else None)
        if manifest_path is not None:
            manifest = {
                "source_file": str(cst_path),
                "file_size": file_size,
                "container": {
                    "format": "CST DE-ZIP (ZIP variant: DE\\x03\\04 / DE\\x01\\02 local & central signatures, standard PK\\x05\\06 EOCD)",
                    "entry_count": len(entries),
                    "eocd_offset": eocd_off,
                    "central_directory_offset": cd_off,
                    "central_directory_size": cd_size,
                    "cst_version": meta.get("cst_version"),
                    "license": meta.get("license"),
                    "eocd_comment": meta.get("comment_raw"),
                },
                "summary": {
                    "total_compressed": sum(e["compressed_size"] for e in entries),
                    "total_uncompressed": sum(e["uncompressed_size"] for e in entries),
                    "crc_ok": sum(1 for r in results if r["crc_ok"]),
                    "crc_failed": sum(1 for r in results if not r["crc_ok"]),
                    "read_errors": sum(1 for r in results if r["error"]),
                },
                "entries": [
                    {
                        "index": e["index"],
                        "name": e["name"],
                        "compression": ("deflate" if e["method"] == METHOD_DEFLATE
                                        else "store" if e["method"] == METHOD_STORE
                                        else str(e["method"])),
                        "compressed_size": e["compressed_size"],
                        "uncompressed_size": e["uncompressed_size"],
                        "crc32_declared": f"{e['crc32']:#010x}",
                        "crc_ok": results[e["index"]]["crc_ok"],
                        "error": results[e["index"]]["error"],
                        "local_header_offset": e["local_header_offset"],
                        "flags": f"{e['flags']:#06x}",
                        "external_attrs": f"{e['external_attrs']:#010x}",
                        "time_fields": interpret_time_fields(e),
                        "type_guess": results[e["index"]]["type"],
                        "extracted_path": results[e["index"]].get("extracted_path"),
                    }
                    for e in entries
                ],
            }
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nmanifest 已写入: {manifest_path}")

        if out_root is not None:
            n_ok = sum(1 for r in results if r.get("extracted_path"))
            print(f"已提取 {n_ok}/{len(entries)} 个文件到: {out_root}")

        if any(r["error"] or not r["crc_ok"] for r in results):
            return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CstParseError as exc:
        print(f"解析错误: {exc}", file=sys.stderr)
        sys.exit(1)
