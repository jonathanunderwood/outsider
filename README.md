# Outsider

This software provides a GUI for controlling the Blackstar ID range of
amplifiers, and is an alternative to Blackstar's own Insider
software. It is primarily written for Linux, as the Blackstar Insider
software is not available for that platform, but since it is written
in Python it should work on any platform. Patches to support other
platforms would be gratefully received.

# Screenshot

![A screenshot to whet your apetite:](./outsider-screenshot.png?raw=true "Screenshot")

## Current status

This software is usable, but still under heavy development.

Currently implemented:
- Control of amplifier front panel controls
- Control of amplifier effects

To be implemented:
- Selection of amplifier presets/patches [Work in progress]
- Saving of amplifer presets/patches [Work in progress]
- Uploading of presets/patches to amplifier [Work in progress]
- Control for effects loop on/off [Not started yet]
- Control for super-wide stereo on/off [Not started yet]
- Control for noise gate setting [Not started yet]

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

# License

The software is made available under the GPLv3 license , which
includes this Disclaimer of Warranty:

THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY
APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT
HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM "AS IS" WITHOUT
WARRANTY OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND
PERFORMANCE OF THE PROGRAM IS WITH YOU.  SHOULD THE PROGRAM PROVE
DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING, REPAIR OR
CORRECTION.

Full details of the license can be found in the COPYING file.
