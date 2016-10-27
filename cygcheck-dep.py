#!/usr/bin/env python3

from collections import defaultdict
import argparse
import os
import re
import sys
import urllib.request
import glob

try:
    import tarjan.tc
except ImportError:
    print("This program requires the tarjan package.")
    print("Please install it and try again.")
    sys.exit(1)

def get_setup_ini(args):
    if args.inifile:
        if args.cached:
            print("Ignoring -c option.")
        return args.inifile
    if args.cached:
        files = glob.glob('/tmp/tmp*_setup.ini')
        if not files:
            print("No /tmp/tmp*_setup.ini file found.")
            sys.exit(1)
        if len(files) > 1:
            print("More than one /tmp/tmp*_setup.ini file found.")
            sys.exit(1)
        return files[0]
    
    arch = os.uname().machine
    if arch == 'i686':
        arch = 'x86'

    temp_fn, headers = urllib.request.urlretrieve('ftp://ftp.cygwin.com/pub/cygwin/' + arch + '/setup.xz')
    xz_fn = temp_fn + '_setup.ini.xz'
    os.rename(temp_fn, xz_fn)
    os.system('/usr/bin/xz -d ' + xz_fn)
    return temp_fn + '_setup.ini'

# Return dependency graph of all packages listed in INIFILE, plus a
# fictitious ’BASE’ package that requires all the packages in the Base
# category.
def parse_setup_ini(inifile):
    g = defaultdict(list)
    with open(inifile) as f:
        for line in f:
            match = re.match(r'^@\s+(\S+)', line)
            if match:
                # New package
                name = match.group(1)
                g[name] = []
                continue

            if(re.match(r'^category:.*\bBase\b', line)):
                g['BASE'].append(name)
                continue

            match = re.match(r'^requires:\s*(.*)$', line)
            if match:
                g[name] = match.group(1).split()
    return g

# Return a list of installed packages.
def get_installed_pkgs():
    inst = []
    with open("/etc/setup/installed.db") as f:
        next(f)                 # Skip header
        for line in f:
            match = re.search(r'^(\S*) ', line)
            inst.append(match.group(1))
    return inst

# Given a graph g, return a list of strongly-connected components of
# size > 1 that receive no arrows from any other SCC.
def find_islands(g):
    sccs = tarjan.tarjan(g)
    # For each vertex, record the index of its scc.  Also declare the
    # scc an island until we discover otherwise.
    scc_ind = {}
    is_island = []                # Index is index of scc.
    for i, c in enumerate(sccs):
        if len(c) > 1:
            is_island.append(True)
        else:
            is_island.append(False)
        for v in c:
            scc_ind[v] = i

    # For each component C, mark as non-island any earlier component
    # that receives an edge from something in C.
    for i, c in enumerate(sccs):
        for v in c:
            for w in g[v]:
                if scc_ind[w] < i:
                    is_island[scc_ind[w]] = False

    return [sccs[i] for i in range(len(sccs)) if is_island[i]]

# Reverse a graph g with vertex set V.
def reverse(g, V):
    h = defaultdict(list)
    for p, req in g.items():
        for q in req:
            h[q].append(p)
    return {p : h[p] for p in V}

# Given a dependency graph and a list of installed packages, return a
# dictionary {p : req} where req is a list of dependencies of p that
# are not in I.
def find_missing_deps(g, I):
    missing = defaultdict(list)
    for p in g:
        for q in g[p]:
            if not q in I:
                missing[p].append(q)
    return missing

# Return a list of unknown installed packages (not listed in setup.ini).
def find_unknown_pkgs(g, I):
    return [p for p in I if p not in g]

# Return True if warnings were issued.
def report_broken(g, I):
    ret = False
    missing = find_missing_deps(g, I)
    if missing:
        ret = True
        print("Missing dependencies:")
        for p in missing:
            print("%s: " % p, end='')
            comma_print(missing[p])
    unknown = find_unknown_pkgs(g, I)
    if unknown:
        ret = True
        print("Unknown packages:")
        comma_print(unknown)
    return ret

# Print list items separated by commas.
def comma_print(l):
    print(','.join(l))

def main():
    parser = argparse.ArgumentParser(description='Find dependency information for Cygwin installation')
    parser.add_argument('-c', '--cached', action='store_true', help='use cached setup.ini file', required=False)
    parser.add_argument('-p', '--inifile', action='store', help='path to setup.ini', required=False, metavar='FILE')
    parser.add_argument('-q', '--quiet', action='store_true', help='suppress warnings about broken dependencies')
    parser.add_argument('-a', '--all-packages', action='store_true', dest='all', help='report on all packages, not just those installed')
    parser.add_argument('package', help='package name', metavar='PACKAGE', nargs='?')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-r', '--requires', action='store_true', help='show dependencies of PACKAGE')
    group.add_argument('-R', '--recursively-requires', action='store_true', dest='Requires', help='show recursive dependencies of PACKAGE')
    group.add_argument('-n', '--needs', action='store_true', help='show packages that require PACKAGE')
    group.add_argument('-N', '--recursively-needs', action='store_true', dest='Needs', help='show packages that recursively require PACKAGE')
    group.add_argument('-l', '--leaves', action='store_true', help='show packages not required by any others')
    group.add_argument('-i', '--islands', action='store_true', help='show SCCs with more than one element, not required by any other SCC')
    group.add_argument('-I', '--all-sccs', action='store_true', dest='all_sccs', help='show all SCCs with more than one element')
    group.add_argument('-b', '--broken', action='store_true', help='show installed packages with broken or unknown dependencies')
    args = parser.parse_args()

    inifile = get_setup_ini(args)
    if not os.path.exists(inifile):
        print("%s doesn't exist" % inifile)
        sys.exit(1)

    all_pkgs_graph = parse_setup_ini(inifile)

    # Create working dependency graph g, which always includes 'BASE'.
    if not args.all:
        inst = get_installed_pkgs()
        inst_plus_base = inst[:]    # Copy by slicing.
        inst_plus_base.append('BASE')
        g = {p : all_pkgs_graph[p] for p in all_pkgs_graph if p in inst_plus_base}
    else:
        g = all_pkgs_graph
        inst_plus_base = list(g.keys())
        inst = inst_plus_base[:]
        inst.remove('BASE')

    if not args.quiet and not args.broken:
        if report_broken(g, inst):
            print("\nWarning: The results that follow might be unreliable.\n")

    if args.requires or args.Requires or args.needs or args.Needs:
        if not args.package:
            print("PACKAGE must be specified")
            sys.exit(1)
        if args.package not in inst:
            print("%s is not installed or not known." % args.package)
            sys.exit(1)

    if args.requires or args.Requires or args.needs or args.Needs or args.leaves:
        rev_g = reverse(g, inst_plus_base)

    if args.requires:
        comma_print(sorted(g[args.package]))
    elif args.Requires:
        comma_print(sorted(tarjan.tc.tc(g)[args.package]))
    elif args.needs:
        comma_print(sorted(rev_g[args.package]))
    elif args.Needs:
        comma_print(sorted(tarjan.tc.tc(rev_g)[args.package]))
    elif args.leaves:
        leaves = sorted([p for p in inst if not rev_g[p]])
        for p in leaves:
            print(p)
    elif args.islands:
        islands = find_islands(g)
        for i in islands:
            comma_print(sorted(i))
    elif args.all_sccs:
        sccs = tarjan.tarjan(g)
        for c in sccs:
            if len(c) > 1:
                comma_print(sorted(c))
    elif args.broken:
        report_broken(g, inst)

if __name__ == '__main__':
    main()
