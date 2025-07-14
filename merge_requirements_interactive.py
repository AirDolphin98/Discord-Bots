#!/usr/bin/env python3
# Created by Microsoft Copilot
# Script to help combine two requirements txt files
# Assumes two files, requirements1.txt and requirements2.txt
# Easier to use if your preferred versions mostly in requirements1.txt

import sys
from packaging.requirements import Requirement
from packaging.version import Version, InvalidVersion
from collections import defaultdict

def load_reqs(path):
    """Yield Requirement objects from a file, skipping comments/blanks."""
    for line in open(path, 'r').read().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            yield Requirement(line)
        except Exception:
            print(f"  [warn] Skipping invalid line: {line}")

def choose_version(pkg, versions):
    """Prompt the user to choose one version from a list."""
    print(f"\nMultiple versions found for {pkg}:")
    for i, v in enumerate(versions, start=1):
        print(f"  {i}. {pkg}=={v}")
    while True:
        choice = input(f"Select version [1-{len(versions)}] (default 1): ").strip()
        if not choice:
            return versions[0]
        if choice.isdigit() and 1 <= int(choice) <= len(versions):
            return versions[int(choice) - 1]
        print("Invalid choice, try again.")

def main():
    input_files = ['requirements1.txt', 'requirements2.txt']
    out_path = 'requirements.txt'

    # Group requirements by package name (lowercased)
    groups = defaultdict(list)
    for fname in input_files:
        for req in load_reqs(fname):
            groups[req.name.lower()].append(req)

    merged = {}
    for pkg, reqs in groups.items():
        # Collect all exact pins (==)
        pins = []
        for r in reqs:
            for spec in r.specifier:
                if spec.operator == '==':
                    try:
                        pins.append(spec.version)
                    except InvalidVersion:
                        pass
        pins = sorted(set(pins), key=lambda v: Version(v))

        if len(pins) > 1:
            chosen = choose_version(pkg, pins)
            merged[pkg] = f"{pkg}=={chosen}"
        elif len(pins) == 1:
            merged[pkg] = f"{pkg}=={pins[0]}"
        else:
            # No exact pins: take the first requirement’s specifiers (could be >=,< etc.)
            spec_str = ''.join(str(s) for s in reqs[0].specifier)
            merged[pkg] = f"{pkg}{spec_str}"

    # Write out sorted merged file
    with open(out_path, 'w') as out:
        for line in sorted(merged.values()):
            out.write(line + '\n')

    print(f"\n✅ Merged requirements written to {out_path}")

if __name__ == '__main__':
    main()