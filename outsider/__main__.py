# This file is part of Outsider.
#
# Foobar is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Foobar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Outsider.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2015, Jonathan Underwood. All rights reserved.

import outsider
import sys
from PyQt5 import QtWidgets
import blackstarid
import logging

def main(args=None):
    # TODO use argparse to add various options for debugging etc
    if args is None:
        args = sys.argv[1:]

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('outsider')

    app = QtWidgets.QApplication(sys.argv)
    window = outsider.Ui()

    # try:
    #     amp = blackstarid.BlackstarIDAmp()
    # except:
    #     logger.error('No amplifier found')
        #sys.exit(1)

#    window.voice_changed_on_amp.emit(4)

    sys.exit(app.exec_())



    

if __name__ == "__main__":
    main()
