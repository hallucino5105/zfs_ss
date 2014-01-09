#!/usr/bin/env python
# coding: utf-8


import sys
import os
import pwd
import locale
import datetime
import string
import random
from functools import wraps

sys.path.append(os.path.expanduser("~/my_lib/subcommand"))
from subcommand import subcommand


def set_locale_c(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loc = locale.setlocale(locale.LC_ALL)
        locale.setlocale(locale.LC_ALL, "C")
        result = f(*args, **kwargs)
        locale.setlocale(locale.LC_ALL, loc)

        return result

    return wrapper


def authority_check(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = pwd.getpwuid(os.getuid())[0]
        if user != "root":
            raise RuntimeError("this program only works on root")

        result = f(*args, **kwargs)
        return result

    return wrapper


def zfs_command_exist_check(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        data = subcommand("which zpool").print1()
        if not os.path.exists(data[0]):
            raise RuntimeError("zpool command not found")

        data = subcommand("which zfs").print1()
        if not os.path.exists(data[0]):
            raise RuntimeError("zfs command not found")

        result = f(*args, **kwargs)
        return result

    return wrapper


@authority_check
@zfs_command_exist_check
def prior_check(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        return result

    return wrapper


class ZfsTools:
    def __init__(self):
        pass


    def __random_string(self, str_range=5):
        return ''.join([random.choice(string.ascii_letters + string.digits) for i in range(str_range)])


    def __list_command_proc(self, command, modifier):
        data = subcommand("LANG=C %s" % command.rstrip()).print2()
        if len(data) < 2:
            return []

        header = [ c.lower() for c in data[0] ]
        state_zfs_list = []

        for row in data[1:]:
            state_zfs_list.append(modifier(header, row))

        return state_zfs_list


    @prior_check
    def list_zpool_summary(self, target=""):
        def modifier(header, row):
            e = dict(zip(header, row))

            if e["altroot"].lower() == "-":
                e["altroot"] = None

            return e

        return self.__list_command_proc("zpool list %s" % target, modifier)


    @prior_check
    def list_zfs_summary(self, target=""):
        def modifier(header, row):
            e = dict(zip(header, row))

            if e["avail"].lower() == "none":
                e["avail"] = None

            if e["mountpoint"].lower() == "none":
                e["mountpoint"] = None

            return e

        return self.__list_command_proc("zfs list -t filesystem,volume %s" % target, modifier)


    @prior_check
    def list_zfs_snapshot_summary(self, target=""):
        def modifier(header, row):
            e = dict(zip(header, row))

            if e["avail"].lower() == "none":
                e["avail"] = None

            if e["mountpoint"].lower() == "none":
                e["mountpoint"] = None

            return e

        return self.__list_command_proc("zfs list -t snapshot %s" % target, modifier)


    @prior_check
    def list_zpool_detail(self, prop=[], target=""):
        def modifier(header, row):
            e = dict(zip(header, row))

            if e["value"].lower() == "-":
                e["value"] = None

            if e["source"].lower() == "-":
                e["source"] = None

            return e

        if len(prop) == 0:
            prop_cmd = "all"
        else:
            prop_cmd = ",".join(prop)

        return self.__list_command_proc("zpool get %s %s" % (prop_cmd, target), modifier)


    @prior_check
    @set_locale_c
    def list_zfs_detail(self, prop=[], target=""):
        def modifier(header, row):
            if len(row) != 4:
                if row[1] == "clones":
                    row.insert(2, None)

                if row[1] == "creation":
                    date = datetime.datetime.strptime(" ".join(row[2:-1]), "%a %b %d %H:%M %Y")
                    del row[2:-1]
                    row.insert(2, date)

            e = dict(zip(header, row))

            try:
                if e["value"].lower() == "-":
                    e["value"] = None

                if e["source"].lower() == "-":
                    e["source"] = None

            except AttributeError:
                pass

            return e

        if len(prop) == 0:
            prop_cmd = "all"
        else:
            prop_cmd = ",".join(prop)

        return self.__list_command_proc("zfs get %s %s" % (prop_cmd, target), modifier)


    @prior_check
    def devnames_zpool(self):
        return [ d["name"] for d in self.list_zpool_summary() ]


    @prior_check
    def devnames_zfs(self):
        return [ d["name"] for d in self.list_zfs_summary() ]


    @prior_check
    def devnames_zfs_snapshot(self):
        return [ d["name"] for d in self.list_zfs_snapshot_summary() ]


    def __zfs_name_format_check(self, target):
        if not target:
            raise RuntimeError("target device unknown")

        if target not in self.devnames_zfs():
            raise RuntimeError("target device not found")

        target_type = self.list_zfs_detail(target=target, prop=["type"])[0]["value"]
        if target_type != "filesystem" and target_type != "volume":
            raise RuntimeError("target device illegal type")


    def __snapshot_name_format_check(self, target):
        if target.find("@") == -1:
            raise RuntimeError("target name illegal format")

        zfsname, sslabel = target.split("@")
        if zfsname == "" or sslabel == "":
            raise RuntimeError("target name illegal format")

        if target not in self.devnames_zfs_snapshot():
            raise RuntimeError("target not found")

        target_type = self.list_zfs_detail(target=target, prop=["type"])[0]["value"]
        if target_type != "snapshot" and target_type != "snap":
            raise RuntimeError("target illegal type")


    @prior_check
    def target_snapshot_create(self, dev_target, label=""):
        self.__zfs_name_format_check(dev_target)

        if not label:
            label = "%s_%s" % (datetime.datetime.now().strftime("%Y%m%d%H%M%S"), self.__random_string(5))
        snapshot_name = "%s@%s" % (dev_target, label)

        ret, _, errmsg = subcommand("zfs snapshot %s" % snapshot_name).print0()
        if ret != 0:
            raise RuntimeError("snapshot creation failed: %d\n  reason = \"%s\"" % (ret, errmsg))

        return snapshot_name


    @prior_check
    def target_snapshot_destroy(self, ss_target):
        self.__snapshot_name_format_check(ss_target)

        ret, _, errmsg = subcommand("zfs destroy %s" % ss_target).print0()
        if ret != 0:
            raise RuntimeError("snapshot destroy failed: %d\n  reason = \"%s\"" % (ret, errmsg))


    @prior_check
    def target_snapshot_creation_date(self, ss_target):
        self.__snapshot_name_format_check(ss_target)

        return self.list_zfs_detail(target=ss_target, prop=["creation"])[0]["value"]


    @prior_check
    def target_snapshot_list(self, dev_target):
        self.__zfs_name_format_check(dev_target)

        return [ l for l in self.devnames_zfs_snapshot() if l.find(dev_target) != -1 ]

