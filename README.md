# outsider
This is not yet ready for public consumption, but if you can work out what it does (or will do), you're welcome to try it and tell me where it breaks.


## Install udev rules

The file blackstar-id.rules contains udev rules to allow the user at
the active seat to access the blackstar hardware. This file needs to
be copied to the directory /etc/udev/rules.d/ eg.

    cp -a blackstar-id.rules /etc/udev/rules.d/69-blackstar-id.rules

and then the rules need to be reloaded:

    udevadm control --reload-rules
