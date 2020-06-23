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
requirements: [lsblk]
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
            - Filter devices when they are 'blank' and is not used
              by any known subsytem (raid, parition, devce mapper, mount)
            - True means only used devices
            - False means only unused devices
            - no value (omit) accepts both used and unused devices

    is_blank:
        type: bool
        description:
            - Filter using additional checks by wipefs
            - True allow devices which has nothing wipefs can recognize
            - False allow devices which has something wipefs recoginize
            - no value (omit) is means 'no wipefs validation'
"""

missed = """
    max_devices:
        type: int
        description:
            - Maximum number of devices in output (may be smaller)
            - Set to 1 to return a single device or no devices
            -  int
        description:
            - Minimum amount of devices to find
            - Module fails if number of filtered devices is less
              than this number.
            - not implemented


    subsystems:
        type: list
        description:
            - List of subsystems to check against
            - values are per `lsblk -O` command (SUBSYS field)
            - not implemented

    is_sata:
        type: bool
        description:
            - Filter based on 'tran' (transport) field of output of lsblk.
            - True value accepts only sata devices
            - False value skips sata devices
            - no value (omit) accepts both sata and non-sata devices
            - not implemented

    ro:
        type: bool
        description:
            - Filter RO devices (True for RO, False for non-ro)
            - not implementedProbing
            - stops if max_devices found, the rest is untested
            - not implemented

    min_deivces:
        type: int
        description:
            - Minimum amount of devices to find
            - Module fails if number of filtered devices is less
              than this number.
            - not implemented


    subsystems:
        type: list
        description:
            - List of subsystems to check against
            - values are per `lsblk -O` command (SUBSYS field)
            - not implemented

    is_sata:
        type: bool
        description:
            - Filter based on 'tran' (transport) field of output of lsblk.
            - True value accepts only sata devices
            - False value skips sata devices
            - no value (omit) accepts both sata and non-sata devices
            - not implemented

    ro:
        type: bool
        description:
            - Filter RO devices (True for RO, False for non-ro)
            - not implemented
"""

EXAMPLES = """
- name: Filter empty and unused devices
  blk_filter:
    name: '{{ ansible_devices.keys() }}'
    is_used: false
    is_blank: false
  register: devices
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

    def _fiter(self, device):
        if 'is_used' in self.module.params:
            return device.children and self.module.params['is_used']

        if 'is_blank' in self.module.params:
            wipefs_output = self._check_with_wipefs(device.name)
            return wipefs_output and self.module.params['is_used']

        # no reasons to reject device, passed
        return True

    def _check_with_wipefs(self, device_name):
        raise NotImplementedError

    def _prep_dev_list(self, raw_devlist):
        raise NotImplementedError

    def run(self):
        cmd = ['lsblk', '-O', '--json']
        if 'devices' in self.module.params:
            cmd += self._prep_dev_list(self.module.params['devices'])

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
        filtered_output = filter(self._filter, blklist['blockdevices'])
        self.module.exit_json(devices=filtered_output)


def main():
    module = AnsibleModule(
        argument_spec={
            'name': {
                'aliases': ['device', 'devices'],
                'required': True,
                'type': 'list'
            },
            'is_used': {'type': 'bool'},
            'is_blank': {'type': 'bool'}
        },
        supports_check_mode=True
    )
    BlkFilter(module).run()


if __name__ == '__main__':
    main()
