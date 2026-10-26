import csv
from collections import defaultdict
from pathlib import Path
import re

import ida_bytes
import ida_funcs
import ida_name
import ida_segment
import idautils

# Only tested on IDA 9.4! -GRAnimated

def generated_symbol(name):
    if name.startswith(("Nerve_", "sub_", "off_", "qword_", "unk_", "nullsub_")):
        return True
    if re.fullmatch(r"UnknownHost_[0-9A-F]+_exe[A-Za-z_0-9]+", name):
        return True
    scope = r"12_GLOBAL__N_1\d+[A-Za-z_0-9]+Nrv[A-Za-z_0-9]+"
    return bool(re.fullmatch(
        rf"(?:[A-Za-z_][A-Za-z_0-9]*)?_Z(?:TVN{scope}E|N{scope}9sInstanceE|"
        rf"NK{scope}(?:(?:7execute|12executeOnEnd)EPN2al11NerveKeeperE|11getNameHashEv))(?:_[0-9A-F]+)?",
        name,
    ))


def nerve_symbols(row):
    address = int(row["Address"], 16)
    class_name, nerve_name = row["Class"], row["NerveName"]
    if bool(class_name) != bool(nerve_name):
        raise ValueError(f"Incomplete name at {row['Address']}")
    if not class_name:
        return None
    label = f"{class_name}Nrv{nerve_name}"
    host_class = row.get("HostClass", "")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", label):
        raise ValueError(f"Invalid nerve name: {label}")
    if host_class and not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*(?:::[A-Za-z_][A-Za-z_0-9]*)*", host_class):
        raise ValueError(f"Invalid host class: {host_class}")
    prefix = ""
    if class_name == "HostType":
        prefix = f"{host_class.replace('::', '_')}_" if host_class else f"UnknownHost_{address:X}_"
    scope = f"12_GLOBAL__N_1{len(label)}{label}"
    return {
        "instance": f"{prefix}_ZN{scope}9sInstanceE",
        "vtable": f"{prefix}_ZTVN{scope}E",
        "execute": f"{prefix}_ZNK{scope}7executeEPN2al11NerveKeeperE",
        "executeOnEnd": f"{prefix}_ZNK{scope}12executeOnEndEPN2al11NerveKeeperE",
        "getNameHash": f"{prefix}_ZNK{scope}11getNameHashEv",
    }


def execute_target(address):
    instructions = list(idautils.FuncItems(address))
    if len(instructions) not in (2, 3):
        return None
    load, branch = instructions[0], instructions[-1]
    load_opcode = ida_bytes.get_dword(load)
    if load_opcode & 0xFFFFFFE0 != 0xF9400420:
        return None
    host_register = load_opcode & 31
    if len(instructions) == 3:
        adjustment = ida_bytes.get_dword(instructions[1])
        if (adjustment & 0xFF80001F not in (0x91000000, 0xD1000000) or
                (adjustment >> 5) & 31 != host_register):
            return None
    elif host_register != 0:
        return None
    opcode = ida_bytes.get_dword(branch)
    if opcode & 0xFC000000 != 0x14000000:
        return None
    displacement = opcode & 0x03FFFFFF
    if displacement & 0x02000000:
        displacement -= 0x04000000
    target = branch + displacement * 4
    function = ida_funcs.get_func(target)
    return target if function and function.start_ea == target else None


def exe_symbol(row):
    method = f"exe{row['NerveName']}"
    host = row.get("HostClass") or row["Class"]
    if host == "HostType":
        return f"UnknownHost_{int(row['Address'], 16):X}_{method}"
    scope = "".join(f"{len(part)}{part}" for part in host.split("::"))
    return f"_ZN{scope}{len(method)}{method}Ev"


def propagate_execute(rows, targets):
    comments = defaultdict(set)
    candidates = defaultdict(set)
    execute_addresses = {ida_bytes.get_qword(int(row["Vtable"], 16)) for row in rows}
    for row in rows:
        if not row["Class"]:
            continue
        execute = ida_bytes.get_qword(int(row["Vtable"], 16))
        target = execute_target(execute)
        if target is not None:
            if target not in execute_addresses:
                candidates[target].add(exe_symbol(row))
        else:
            host = row.get("HostClass") or row["Class"]
            qualifier = " (host class unknown)" if host == "HostType" else ""
            comments[execute].add(f"{host}::exe{row['NerveName']}() inlined into execute{qualifier}.")
    ambiguous = 0
    for address, names in candidates.items():
        if len(names) == 1:
            targets[address].update(names)
        else:
            ambiguous += 1
    return comments, len(candidates) - ambiguous, ambiguous


def main():
    path = Path(__file__).resolve().parents[2] / "data" / "nerves" / "nerves.csv"
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    targets = defaultdict(set)
    function_owners = defaultdict(list)
    old_address_points = set()
    for row in rows:
        address = int(row["Address"], 16)
        vtable = int(row["Vtable"], 16)
        if ida_segment.getseg(address) is None or not ida_bytes.is_loaded(vtable):
            raise ValueError(f"Address not loaded: {row['Address']} / {row['Vtable']}")
        pointer = ida_bytes.get_qword(address)
        if pointer not in (vtable, 0, 0xFFFFFFFFFFFFFFFF):
            raise ValueError(f"Vtable mismatch at {row['Address']}")
        symbols = nerve_symbols(row)
        if symbols:
            header = vtable - 0x10
            if ida_bytes.get_qword(header) != 0 or ida_bytes.get_qword(header + 8) != 0:
                raise ValueError(f"Unexpected vtable header at {header:X}")
            targets[address].add(symbols["instance"])
            targets[header].add(symbols["vtable"])
            old_address_points.add(vtable)
        for offset, role in ((0, "execute"), (8, "executeOnEnd"), (16, "getNameHash")):
            function = ida_bytes.get_qword(vtable + offset)
            if not ida_bytes.is_loaded(function):
                raise ValueError(f"Invalid vtable slot at {vtable + offset:X}")
            function_owners[function].append(symbols[role] if symbols else None)

    for address, owners in function_owners.items():
        if len(owners) == 1 and owners[0]:
            targets[address].add(owners[0])

    inline_comments, exe_targets, ambiguous_exe = propagate_execute(rows, targets)

    plan = {}
    duplicates = defaultdict(list)
    for address, names in targets.items():
        if len(names) != 1:
            raise ValueError(f"Conflicting names at {address:X}: {names}")
        name = next(iter(names))
        plan[address] = name
        duplicates[name].append(address)
    for name, addresses in duplicates.items():
        if len(addresses) > 1:
            for address in addresses:
                plan[address] = f"{name}_{address:X}"

    changed = unchanged = preserved = cleared = 0
    failed = []
    for address, name in sorted(plan.items()):
        current = ida_name.get_name(address)
        if current == name:
            unchanged += 1
            continue
        if current and not generated_symbol(current):
            preserved += 1
            continue
        if ida_name.set_name(address, name, ida_name.SN_CHECK | ida_name.SN_NOWARN):
            changed += 1
        else:
            failed.append(f"{address:X}: {name}")
    for address in sorted(old_address_points):
        current = ida_name.get_name(address)
        if current.startswith("Nerve_") and "_vtable_" in current:
            if ida_name.set_name(address, "", ida_name.SN_NOWARN):
                cleared += 1
            else:
                failed.append(f"{address:X}: clear old address-point label")
    commented = 0
    for address, lines in sorted(inline_comments.items()):
        current = ida_funcs.get_func_cmt_ea(address, False) or ""
        additions = sorted(lines - set(current.splitlines()))
        if additions:
            comment = "\n".join(([current] if current else []) + additions)
            if ida_funcs.set_func_cmt_ea(address, comment, False):
                commented += 1
            else:
                failed.append(f"{address:X}: inline comment")
    print(f"Nerves: {len(rows)} instances, {sum(bool(row['Class']) for row in rows)} named")
    print(f"Renamed {changed}; unchanged {unchanged}; preserved {preserved}; cleared {cleared}; failed {len(failed)}")
    print(f"exe targets {exe_targets}; ambiguous targets skipped {ambiguous_exe}; inline comments added {commented}")
    if failed:
        raise RuntimeError("\n".join(failed))


if __name__ == "__main__":
    main()
