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

from PyQt5 import uic
from PyQt5.QtCore import QObject, QThread
from PyQt5.QtCore import pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QApplication
from blackstarid import BlackstarIDAmp, NoDataAvailable
import logging

# Set up logging and create a null handler in case the application doesn't
# provide a log handler
logger = logging.getLogger('outsider.outsider')


class __NullHandler(logging.Handler):

    def emit(self, record):
        pass

__null_handler = __NullHandler()
logger.addHandler(__null_handler)

class Ui(QMainWindow):
    shutdown_threads = pyqtSignal(name='shutdown_threads')

    # These signals will be emitted when we detect a control is
    # changed from the amplifier rather than from the GUI, and will
    # allow us to update the GUI accordingly.
    voice_changed_on_amp = pyqtSignal(int, name='voice_changed_on_amp')
    volume_changed_on_amp = pyqtSignal(int, name='volume_changed_on_amp')

    def __init__(self):
        super(Ui, self).__init__()

        uic.loadUi('outsider.ui', self)

        self.amp = BlackstarIDAmp()
        self.amp.drain()
        
        self.show()
        self._start_amp_watcher_thread()
        
        self.amp.startup()


    def _start_amp_watcher_thread(self):
        # Set up thread to watch for manual changes of the amp
        # controls at the amp (rather than gui) so we can update the
        # gui controls as needed. The way this is done is inspired
        # by:
        # http://stackoverflow.com/questions/29243692/pyqt5-how-to-make-qthread-return-data-to-main-thread
        # https://mayaposch.wordpress.com/2011/11/01/how-to-really-truly-use-qthreads-the-full-explanation/
        self.thread = QThread()
        self.watcher = AmpControlWatcher(self.amp)
        self.watcher.have_data.connect(self._new_data_from_amp)
        self.shutdown_threads.connect(self.watcher.stop_watching)
        self.watcher.moveToThread(self.thread)
        self.thread.started.connect(self.watcher.work)

        self.thread.start()

    def closeEvent(self, event):
        logger.debug('Closing down amplifier watching thread')
        self.shutdown_threads.emit()
        self.thread.quit()
        self.thread.wait()
        logger.debug('Amplifier watching thread finished')
        super(Ui, self).close()
        logger.debug('Exiting')

    ##pyqtSlot(str, int)
    @pyqtSlot(dict)
    def _new_data_from_amp(self, controls):
        # This slot is called when a control has been changed on the amp
        for control, value in controls.iteritems():
            logger.debug('Data received:: control: {0} value: {1}'.format(control, value))

            if control == 'volume':
                self.volume_changed_on_amp.emit(value)
            elif control == 'all':
                self.voice_changed_on_amp.emit(value['volume'])
            else:
                logger.error('Unrecognized control {0}'.format(control))

    def vol_slider_changed(self, value):
        logger.debug('Volume: {0}'.format(value))
        self.amp.set_control('volume', value)

    def tvp_selection_changed(self, idx):
        logger.debug('TVP: {0}'.format(idx))

    def voice_selection_changed(self, idx):
        logger.debug('Voice: {0}'.format(idx))


    def emit_voice_changed_on_amp(self, value):
        #self.voice_changed_on_amp.connect(self.handle)
        self.voice_changed_on_amp.emit(value)


class AmpControlWatcher(QObject):
    have_data = pyqtSignal(dict, name='have_data')
    shutdown = False
    
    @pyqtSlot()
    def stop_watching(self):
        logger.debug('signal received in stop_watching slot')
        self.shutdown = True

    def __init__(self, amp):
        super(AmpControlWatcher, self).__init__()
        self.amp = amp
        logger.debug('AmpControlWatcher initialized')

    def work(self):
        
        logger.debug("AmpWatcher work function started")

        # Poll persistently until some data appears. If there's no
        # data, read_data() will raise an exception, so we just catch
        # that and carry on.
        while not self.shutdown:
            # We need to call this, otherwise in the thread the
            # shutdown signal is never processed
            QApplication.processEvents()
            try:
                settings = self.amp.read_data()
                #logger.debug('Amp adjustment detected:: control: {0} value: {1}'.format(control, value))
                self.have_data.emit(settings)
            except NoDataAvailable:
                logger.debug('No changes of amp controls reported')
                continue

        logger.debug('AmpWatcher watching loop exited')

