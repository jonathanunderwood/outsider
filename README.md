# outsider

This software provides a GUI for controlling the Blackstar ID range of
amplifiers. It is primarily written for Linux, as the Blackstar
Outsider software is not available for that platform, but since it is
written in Python it should work on any platform. Patches to support
other platforms would be gratefully received.

## Current status

This software is usable, but still under heavy development.

Currently implemented:
- Control of amplifier front panel controls
- Control of amplifier effects

To be implemented:
- Selection of amplifier presets/patches
- Saving of amplifer presets/patches
- Uploading of presets/patches to amplifier
- Control for effects loop on/off
- Control for super-wide stereo on/off
- Control for noise gate setting

Out of scope:
- Firmware updating

## Pre-requisites

This software is written using Python 2.7, and should also work with
Python 3, though that is currently untested. It requires PyQt5 and
PyUSB.

### Fedora 22
The following command should install all necessary pre-requisites:

    dnf install python-qt5 pyusb

### Other distributions

Please help me to add instructions for other distributions here -
please send patches against this file.

## Installation

The following command, ran from the root directory of the sources,
will install the software:

    python setup.py install

If you prefer to install the software only for your current user,
rather than system wide, the following command will do that:

    python setup.py install --user

The following command will display more options:

    python setup.py --help

### Installation of udev rules

The file blackstar-id.rules contains udev rules to allow the user at
the active seat to access the blackstar hardware. This file needs to
be copied to the directory /etc/udev/rules.d/ eg.

    cp -a blackstar-id.rules /etc/udev/rules.d/69-blackstar-id.rules

and then the rules need to be reloaded:

    udevadm control --reload-rules
