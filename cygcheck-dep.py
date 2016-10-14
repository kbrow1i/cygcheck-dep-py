#!/usr/bin/env python3

from collections import defaultdict
import argparse
import os
import re
import sys
import urllib.request

try:
    import tarjan.tc
except ImportError:
    print("This program requires the tarjan package.")
    print("Please install it and try again.")
    sys.exit(1)

def get_setup_ini(args):
    if args.inifile:
        return args.inifile
    
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
    with open("/var/log/setup.log.full") as f:
        c = f.read()
        match = re.search(r'^Dependency order of packages: (.*)$', c,
                          re.MULTILINE)
        if not match:
            print("Can't get list of installed packages from /var/log/setup.log.full.")
            sys.exit(1)
        return match.group(1).split()

# Reverse a dependency graph g with installed packages I
def reverse(g, I):
    h = defaultdict(list)
    warnings = defaultdict(list)
    for p, req in g.items():
        for q in req:
            h[q].append(p)
            if not q in I:
                warnings[p].append(q)
    if warnings:
        for p, req in warnings.items():
            print("Warning: %s requires the following uninstalled package(s):" % p)
            print(req)
        print("Warning: Any results that follow are unreliable.")
        print("")
    return {p : h[p] for p in I}

def main():
    parser = argparse.ArgumentParser(description='Find dependency information for Cygwin installation')
    parser.add_argument('-p', '--inifile', action='store', help='path to setup.ini', required=False, metavar='FILE')
    parser.add_argument('-a', '--all-packages', action='store_true', dest='all', help='report on all packages, not just those installed')
    parser.add_argument('package', help='package name', metavar='PACKAGE', nargs='?')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-r', '--requires', action='store_true', help='show dependencies of PACKAGE')
    group.add_argument('-R', '--recursively-requires', action='store_true', dest='Requires', help='show recursive dependencies of PACKAGE')
    group.add_argument('-n', '--needs', action='store_true', help='show packages that require PACKAGE')
    group.add_argument('-N', '--recursively-needs', action='store_true', dest='Needs', help='show packages that recursively require PACKAGE')
    group.add_argument('-l', '--leaves', action='store_true', help='show leaves of dependency graph')
    # group.add_argument('-i', '--islands', action='store_true', help='show strongly connected components not required by any others')
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
        g = {p : all_pkgs_graph[p] for p in inst_plus_base}
    else:
        g = all_pkgs_graph
        inst_plus_base = list(g.keys())
        inst = inst_plus_base[:]
        inst.remove('BASE')

    rev_g = reverse(g, inst_plus_base)

    if args.requires or args.Requires or args.needs or args.Needs:
        if not args.package:
            print("PACKAGE must be specified")
            sys.exit(1)
        if args.package not in inst:
            print("%s is not installed or not known." % args.package)
            sys.exit(1)
    if args.requires:
        print(sorted(g[args.package]))
    elif args.Requires:
        print(sorted(tarjan.tc.tc(g)[args.package]))
    elif args.needs:
        print(sorted(rev_g[args.package]))
    elif args.Needs:
        print(sorted(tarjan.tc.tc(rev_g)[args.package]))
    elif args.leaves:
        print(sorted([p for p in inst if not rev_g[p]]))


if __name__ == '__main__':
    main()
