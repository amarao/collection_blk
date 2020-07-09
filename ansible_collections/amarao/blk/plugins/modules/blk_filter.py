#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2019-2020, George Shuklin <george.shuklin@gmail.com>

# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = """
---
module: blk_filter
version_added: "2.10"
author: "George Shuklin (@amarao)"
short_description: Filter block devices based on their content
requirements: [lsblk, wipefs, lsof]
description: >
    Allows to filter list of block devices based on specific criteria
options:
    name:
        type: list
        aliases: [device, devices]
        description:
            - List of device names to filter
            - Use output of lsblk is not specified

    is_used:
        type: bool
        description:
            - Filter devices based on been used by any known subsystem
              (raid, parition, devce mapper, fs mount).
            - True means only used devices
            - False means only unused devices
            - no value (omit) accepts both used and unused devices (skip test)
            - Tests are based on lsblk (children and mountpoint attirbutes)

    is_open:
        type: bool
        description:
            - Filter devices based on output of lsof (if device is open by
              a userspace process)
            - True means only open devices
            - False means only not-opened devices
            - no value (omit) accepts both open and non-open devices
              (skip test)

    is_blank:
        type: bool
        description:
            - Filter using additional checks by wipefs
            - True allow devices which has nothing wipefs can recognize
            - False allow devices which has something wipefs recoginize
            - no value (omit) means 'no wipefs validation'

    is_rom:
        type: bool
        description:
            - Filter devices based on type==rom
            - True allow CD-ROM, DVD-ROM, etc (including virtual)
            - False skip/reject CD/DVD-ROM
            - no value (omit) means 'no filter for rom devices'
"""

EXAMPLES = """
- name: Find all empty, unused unopened devices
  blk_filter:
    is_used: false
    is_blank: true
    is_open: false
    is_rom: false
  register: devices
- name: Print full path to each found device
  debug: var=item
  loop: devices.by_path
- name: Check if /dev/sdb is used
  blk_filter:
    device: /dev/sdb
    is_used: false
"""


from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
import json


__metaclass__ = type


class BlkFilter(object):
    def __init__(self, module):
        self.module = module
        self.filters = {}
        self.filters['is_used'] = self.module.params.get('is_used', None)
        self.filters['is_blank'] = self.module.params.get('is_blank', None)

    def _is_open(self, device):
        cmd = ['lsof', '/dev/' + device["name"]]
        rc, out, err = self.module.run_command(cmd)
        if err:
            self.module.fail_json(
                msg="Unable to run lsof. Error:" + err
            )
        if rc == 0 and not out:
            return True
        return False

    def _is_used(self, device):
        have_children = bool(device.get("children"))
        have_mountpoint = bool(device.get("mountpoint"))
        return have_children or have_mountpoint

    def _is_blank(self, device):
        # wipefs without '-a' key is just returning list of found
        # inspected device is not modified
        cmd = ['wipefs', '/dev/' + device["name"]]
        rc, out, err = self.module.run_command(cmd)
        if rc:
            self.module.fail_json(
                msg="Unable to run wipeof utility. Error:" + err
            )
        return not bool(out)

    def _is_rom(self, device):
        return device.type == 'rom'

    def _filter(self, device):
        passed = True
        if self.module.params['is_used'] is not None:
            passed &= self._is_used(device) == self.module.params['is_used']

        if self.module.params['is_blank'] is not None:
            passed &= self._is_blank(device) == self.module.params['is_blank']

        if self.module.params['is_open'] is not None:
            passed &= self._is_open(device) == self.module.params['is_open']

        if self.module.params['is_rom'] is not None:
            passed &= self._is_rom(device) == self.module.params['is_rom']
        return passed

    def _prep_dev_list(self, raw_devlist):
        if type(raw_devlist) == str:
            raw_devlist = [raw_devlist]
        for dev in raw_devlist:
            if not dev.startswith('/dev/'):
                yield '/dev/' + dev
            else:
                yield dev

    def _by_path(self, devlist):
        for dev in devlist:
            yield('/dev/' + dev['name'])

    def _by_name(self, devlist):
        for dev in devlist:
            yield(dev['name'])

    def run(self):
        cmd = ['lsblk', '-O', '--json']
        if 'devices' in self.module.params:
            cmd += list(
                self. _prep_dev_list(self.module.params.get('devices', []))
            )
        rc, out, err = self.module.run_command(cmd, check_rc=True)
        if rc != 0:
            self.module.fail_json(
                msg=to_text("Unable to run blkid. rc=%s. Error: %s" %
                            (rc, err))
            )
        try:
            blklist = json.loads(out)
        except json.decoder.JSONDecodeError as e:
            self.module.fail_json(
                msg=to_text(
                    "Unable to parse lsblk output. Output: %s, error: %s" %
                    (out, e)
                )
            )
        filtered_output = list(filter(self._filter, blklist['blockdevices']))
        self.module.exit_json(
            devices=filtered_output,
            by_path=list(self._by_path(filtered_output)),
            by_name=list(self._by_name(filtered_output))
        )


def main():
    module = AnsibleModule(
        argument_spec={
            'name': {
                'aliases': ['device', 'devices'],
                'type': 'list'
            },
            'is_used': {'type': 'bool'},
            'is_blank': {'type': 'bool'},
            'is_open': {'type': 'bool'},
            'is_rom': {'type': 'bool'}
        },
        supports_check_mode=True
    )
    BlkFilter(module).run()


if __name__ == '__main__':
    main()
