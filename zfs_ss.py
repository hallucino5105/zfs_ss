#!/usr/bin/env python
# coding: utf-8


import sys
import optparse
import datetime
from zfs_tools import ZfsTools


snapshot_root_identifier = "zfsss"


def merr(message, newline=True, flush=False):
    sys.stderr.write(message)
    if newline:
        sys.stderr.write("\n")
    if flush:
        sys.stderr.flush()


def mout(message, newline=True, flush=False):
    sys.stdout.write(message)
    if newline:
        sys.stdout.write("\n")
    if flush:
        sys.stdout.flush()


def now():
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def snapshot_create(zt, devname, label):
    try:
        zt.target_snapshot_create(devname, label)
    except RuntimeError, e:
        merr("error: %s", e)
        return False

    return True


def snapshot_feature_list(zt, devname, feature):
    sslist = []

    for name in zt.target_snapshot_list(devname):
        dev, ss = name.split("@")
        if ss.find(feature) != 0:
            continue

        date = zt.target_snapshot_creation_date(name)
        sslist.append({
            "name": name,
            "date": date })

    # 新しい順
    return sorted(sslist, key=lambda x: x["date"], reverse=True)


def snapshot_manage_lifetime(zt, devname, border, prefix):
    mout("zfs snapshot management by lifetime.")
    mout("searching...")

    sslist = snapshot_feature_list(zt, devname, prefix)

    del_sslist = []
    for ss in sslist:
        #print ss["date"], "|", border, "|", ss["date"] - border
        if ss["date"] < border:
            del_sslist.append(ss)

    if len(del_sslist) > 0:
        for ds in del_sslist:
            mout("snapshot garbage collection. target: name='%s' date='%s'" % (ds["name"], ds["date"]))
            zt.target_snapshot_destroy(ds["name"])

        mout("complete.")
        return 0
    else:
        mout("not found.")
        return 4


def snapshot_manage_generation(zt, devname, generation, feature):
    mout("zfs snapshot management by generation.")
    mout("searching...")

    sslist = snapshot_feature_list(zt, devname, feature)

    if len(sslist) > generation:
        del_sslist = sslist[generation:]
        for ds in del_sslist:
            mout("snapshot garbage collection. target: name='%s' date='%s'" % (ds["name"], ds["date"]))
            zt.target_snapshot_destroy(ds["name"])

        mout("complete.")
        return 0
    else:
        mout("not found.")
        return 3


def execute(options):
    def generate_prefix(label):
        return "%s_%s" % (snapshot_root_identifier, label)

    zt = ZfsTools()

    if options.devname not in zt.devnames_zfs():
        merr("error: device name not found")
        return 1

    prefix = generate_prefix(options.label)
    label = "%s_%s" % (prefix, now())
    if not snapshot_create(zt, options.devname, label):
        merr("error: create snapshot failed")
        return 2

    if options.lifetime:
        border_del_date = datetime.datetime.now() - datetime.timedelta(seconds=options.lifetime)
        return snapshot_manage_lifetime(zt, options.devname, border_del_date, prefix)
    elif options.generation:
        return snapshot_manage_generation(zt, options.devname, options.generation, prefix)
    else:
        raise RuntimeError("program error 1")


def parse_options():
    parser = optparse.OptionParser("usage: %prog [options]")

    parser.add_option(
            "-d", "--devname",
            action="store",
            type="string",
            help="device name")

    parser.add_option(
            "-l", "--label",
            action="store",
            type="string",
            help="snapshot label string")

    parser.add_option(
            "-g", "--generation",
            action="store",
            type="int",
            help="seconds to save snapshot generation")

    # second, minute, hour, dayね
    parser.add_option(
            "-t", "--lifetime",
            action="store",
            type="string",
            help="seconds to save snapshot lifetime (postfix: s,m,h,d)")

    options, args = parser.parse_args()

    if not options.devname:
        mout("error: require option 'devname'")
        parser.print_help()
        return None

    if not options.label:
        mout("error: require option 'label'")
        parser.print_help()
        return None

    # generation,lifetimeどちらかが有効な場合だけ許容
    if (not options.generation and not options.lifetime) or (options.generation and options.lifetime):
        mout("error: require option 'generation' or 'lifetime'")
        parser.print_help()
        return None

    if options.generation and not options.generation > 0:
        mout("error: options 'generation' greater than 0")
        parser.print_help()
        return None

    lifetime_postfix = options.lifetime[-1]

    # s,m,h,dがついてる場合 ついてなければそのまま
    if not lifetime_postfix.isdigit():
        lifetime = int(options.lifetime[0:-1])

        if lifetime_postfix == "s":
            options.lifetime = lifetime
        elif lifetime_postfix == "m":
            options.lifetime = lifetime * 60
        elif lifetime_postfix == "h":
            options.lifetime = lifetime * 60 * 60
        elif lifetime_postfix == "d":
            options.lifetime = lifetime * 24 * 60 * 60
        else:
            raise RuntimeError("lifetime postfix unknown format")

    else:
        options.lifetime = int(options.lifetime)

    if options.lifetime and not options.lifetime > 0:
        mout("error: options 'lifetime' greater than 0")
        parser.print_help()
        return None

    return options


def main():
    options = parse_options()
    if not options:
        sys.exit(-1)

    ret = execute(options)
    sys.exit(ret)


if __name__ == "__main__":
    main()

