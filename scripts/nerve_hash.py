#!/usr/bin/env python3
import argparse
import csv
from itertools import product
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

# hash function from https://gist.github.com/wey-gu/5543c33987c0a5e8f7474b9b80cd36aa

def bytes_to_long(bytes):
    assert len(bytes) == 8
    return sum((b << (k * 8) for k, b in enumerate(bytes)))

def murmur64(data):
    import ctypes
    m = ctypes.c_uint64(0xc6a4a7935bd1e995).value
    r = ctypes.c_uint32(47).value
    MASK = ctypes.c_uint64(2 ** 64 - 1).value
    data_as_bytes = bytearray(data)
    # seed = ctypes.c_uint64(seed).value
    seed = 0
    h = seed ^ ((m * len(data_as_bytes)) & MASK)

    off = int(len(data_as_bytes)/8)*8
    for ll in range(0, off, 8):
        k = bytes_to_long(data_as_bytes[ll:ll + 8])
        k = (k * m) & MASK
        k = k ^ ((k >> r) & MASK)
        k = (k * m) & MASK
        h = (h ^ k)
        h = (h * m) & MASK

    l = len(data_as_bytes) & 7

    if l >= 7:
        h = (h ^ (data_as_bytes[off+6] << 48))
    if l >= 6:
        h = (h ^ (data_as_bytes[off+5] << 40))
    if l >= 5:
        h = (h ^ (data_as_bytes[off+4] << 32))
    if l >= 4:
        h = (h ^ (data_as_bytes[off+3] << 24))
    if l >= 3:
        h = (h ^ (data_as_bytes[off+2] << 16))
    if l >= 2:
        h = (h ^ (data_as_bytes[off+1] << 8))
    if l >= 1:
        h = (h ^ data_as_bytes[off])
        h = (h * m) & MASK

    h = h ^ ((h >> r) & MASK)
    h = (h * m) & MASK
    h = h ^ ((h >> r) & MASK)

    return ctypes.c_uint64(h).value

def target_hash(value):
    try:
        result = int(value, 16)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a hexadecimal hash") from None
    if not 0 <= result < 1 << 64:
        raise argparse.ArgumentTypeError("not a proper hash")
    return result

def update_csv(name, hash_value):
    class_name, separator, nerve_name = name.partition("Nrv")
    if not separator or not class_name or not nerve_name:
        return
    path = Path(__file__).resolve().parents[1] / "data" / "nerves" / "nerves.csv"
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fields = reader.fieldnames
        rows = list(reader)
    matching = [row for row in rows if int(row["Hash"], 16) == hash_value]
    for row in matching:
        if ((row["Class"] and row["Class"] != class_name) or
                (row["NerveName"] and row["NerveName"] != nerve_name)):
            raise ValueError(f"Conflicting name for {hash_value:016X} at {row['Address']}")
    changed = 0
    for row in matching:
        if row["Class"] != class_name or row["NerveName"] != nerve_name:
            row.update({"Class": class_name, "NerveName": nerve_name})
            changed += 1
    if changed:
        with NamedTemporaryFile(mode="w", newline="", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
        print(f"Updated {changed} entries in {path.name}", file=sys.stderr)

def brute_force(class_name, target, wordlists):
    word_groups = []
    class_name = "".join(class_name.split()) if class_name else None
    
    for path in wordlists:
        seen = set()
        words = []
        with path.open(encoding="utf-8") as file:
            for line in file:
                word = "".join(line.split())

                if "Nrv" in word:
                    word = word.split("Nrv", 1)[1]
                
                word = word[:1].upper() + word[1:]
                
                if not word or word in seen:
                    continue
                
                seen.add(word)
                words.append(word)
        word_groups.append(words)

    if class_name:
        classes = [class_name]
    else:
        actor_file = Path(__file__).parent / "reference" / "actors" / "actor_names.txt"
        with actor_file.open(encoding="utf-8") as file:
            classes = list(dict.fromkeys("".join(line.split()) for line in file if line.strip()))
    classes = ["HostType"] + [name for name in classes if name != "HostType"]
    attempts = 0
    
    for candidate_class in classes:
        print(f"Checking {candidate_class}", file=sys.stderr, flush=True)
        
        for parts in product(*word_groups):
            name = f"{candidate_class}Nrv{''.join(parts)}"
            attempts += 1
            
            if murmur64(name.encode("utf-8")) == target:
                suffix = " (HostType)" if candidate_class == "HostType" else ""
                
                print(f"{name}: {target:016X}{suffix}")
                update_csv(name, target)
                return 0
    
    print(f"No match for {target:016X} after {attempts} candidates.", file=sys.stderr)
    return 1

def main():
    parser = argparse.ArgumentParser(
        description="Hash nerve class names.",
        epilog="Name format looks to be ClassNrvName.\nExample: %(prog)s AllDeadWatcherNrvWatch AllDeadWatcherNrvWait",
    )
    parser.add_argument("names", nargs="*", help="Nerve class names")
    parser.add_argument(
        "--file",
        type=argparse.FileType("r", encoding="utf-8"),
        help="Read names from a newline-separated file. Spaces are ignored so you can do like 'AllDeadWatcher Nrv Watch'.",
    )
    parser.add_argument("--brute", type=target_hash, metavar="HASH", help="Search for a hexadecimal hash (with or without 0x)")
    parser.add_argument("--class", dest="class_name", metavar="CLASS", help="Class name used to try ClassNrvWord; defaults to all classes in reference/actors/actor_names.txt")
    parser.add_argument(
        "--wordlist",
        nargs="+",
        type=Path,
        metavar="FILE",
        help="Combine one word from each file in order. Defaults to reference/nerve_names/nerve_names.txt",
    )
    args = parser.parse_args()
    if args.brute is not None:
        if args.names or args.file:
            parser.error("use --wordlist for --brute, not positional names or --file")
        wordlists = args.wordlist or [Path(__file__).parent / "reference" / "nerve_names" / "nerve_names.txt"]
        try:
            return brute_force(args.class_name, args.brute, wordlists)
        except (OSError, UnicodeError, ValueError) as error:
            parser.error(str(error))
    if args.class_name or args.wordlist:
        parser.error("--class and --wordlist require --brute")
    names = args.names
    if args.file:
        with args.file as file:
            names.extend(line.strip() for line in file if line.strip())
    if not names:
        parser.error("provide at least one name or a --file")

    for name in names:
        name = "".join(name.split())
        hash_value = murmur64(name.encode('utf-8'))
        print(f"{name}: {hash_value:016X}")
        try:
            update_csv(name, hash_value)
        except (OSError, UnicodeError, ValueError) as error:
            parser.error(str(error))


if __name__ == "__main__":
    sys.exit(main())
