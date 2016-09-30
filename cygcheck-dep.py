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

# Return dependency graph of all packages listed in INIFILE.
def parse_setup_ini(inifile):
    g = defaultdict(list)

    with open(inifile) as f:
        for line in f:
            match = re.match(r'^@\s+(\S+)', line)
            if match:
                # New package
                name = match.group(1)
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

# Reverse a directed graph.
def reverse(g):
    h = defaultdict(list)
    for v, e in g.items():
        for w in e:
            h[w].append(v)
    return h

def main():
    parser = argparse.ArgumentParser(description='Find dependency information for Cygwin installation')
    parser.add_argument('-i', '--inifile', action='store', help='path to setup.ini', required=False, metavar='FILE')
    parser.add_argument('package', help='package name', metavar='PACKAGE')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-r', '--requires', action='store_true', help='print dependencies')
    group.add_argument('-R', '--recursively-requires', action='store_true', dest='Requires', help='print recursive dependencies')
    group.add_argument('-n', '--needs', action='store_true', help='print packages that require PACKAGE')
    group.add_argument('-N', '--recursively-needs', action='store_true', dest='Needs', help='print packages that recursively require PACKAGE')
    args = parser.parse_args()

    inifile = get_setup_ini(args)
    if not os.path.exists(inifile):
        print("%s doesn't exist" % inifile)
        sys.exit(1)

    all_pkgs_graph = parse_setup_ini(inifile)

    inst = get_installed_pkgs()

    inst_pkgs_graph = {p: all_pkgs_graph[p] for p in inst}

    if args.requires:
        print(sorted(inst_pkgs_graph[args.package]))
    elif args.Requires:
        print(sorted(tarjan.tc.tc(inst_pkgs_graph)[args.package]))
    elif args.needs:
        print(sorted(reverse(inst_pkgs_graph)[args.package]))
    elif args.Needs:
        print(sorted(tarjan.tc.tc(reverse(inst_pkgs_graph))[args.package]))


if __name__ == '__main__':
    main()
