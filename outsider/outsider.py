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
    # allow us to update the GUI accordingly. These signals are bound
    # in the .ui file, so don't need a connect call to bind them.
    voice_changed_on_amp = pyqtSignal(int)
    gain_changed_on_amp = pyqtSignal(int)
    volume_changed_on_amp = pyqtSignal(int)
    bass_changed_on_amp = pyqtSignal(int)
    middle_changed_on_amp = pyqtSignal(int)
    treble_changed_on_amp = pyqtSignal(int)
    isf_changed_on_amp = pyqtSignal(int)
    tvp_valve_changed_on_amp = pyqtSignal(int)
    mod_switch_changed_on_amp = pyqtSignal(int)
    delay_switch_changed_on_amp = pyqtSignal(int)
    reverb_switch_changed_on_amp = pyqtSignal(int)
    mod_type_changed_on_amp = pyqtSignal(int)
    mod_segval_changed_on_amp = pyqtSignal(int)
    mod_level_changed_on_amp = pyqtSignal(int)
    mod_speed_changed_on_amp = pyqtSignal(int)
    delay_type_changed_on_amp = pyqtSignal(int)
    delay_feedback_changed_on_amp = pyqtSignal(int)
    delay_level_changed_on_amp = pyqtSignal(int)
    delay_time_changed_on_amp = pyqtSignal(int)
    reverb_type_changed_on_amp = pyqtSignal(int)
    reverb_size_changed_on_amp = pyqtSignal(int)
    reverb_level_changed_on_amp = pyqtSignal(int)
    fx_focus_changed_on_amp = pyqtSignal(int)

    def __init__(self):
        super(Ui, self).__init__()

        uic.loadUi('outsider.ui', self)

        # Dictionary of signals to emit in response to changes to
        # controls made directly on the amplifier. This dict has to be
        # created here *after* the UI is created and the signals
        # connected - creating this dict as a class attribute would
        # mean all the values in the dict correspond to unbound
        # signals.
        self.control_signals = {
            'voice': self.voice_changed_on_amp,
            'gain': self.gain_changed_on_amp,
            'volume': self.volume_changed_on_amp,
            'bass': self.bass_changed_on_amp,
            'middle': self.middle_changed_on_amp,
            'treble': self.treble_changed_on_amp,
            'isf': self.isf_changed_on_amp,
            'tvp_valve': self.tvp_valve_changed_on_amp,
            'mod_switch': self.mod_switch_changed_on_amp,
            'delay_switch': self.delay_switch_changed_on_amp,
            'reverb_switch': self.reverb_switch_changed_on_amp,
            'mod_type': self.mod_type_changed_on_amp,
            'mod_segval': self.mod_segval_changed_on_amp,
            'mod_level': self.mod_level_changed_on_amp,
            'mod_speed': self.mod_speed_changed_on_amp,
            'delay_type': self.delay_type_changed_on_amp,
            'delay_feedback': self.delay_feedback_changed_on_amp,
            'delay_level': self.delay_level_changed_on_amp,
            'delay_time': self.delay_time_changed_on_amp,
            'reverb_type': self.reverb_type_changed_on_amp,
            'reverb_size': self.reverb_size_changed_on_amp,
            'reverb_level': self.reverb_level_changed_on_amp,
            'fx_focus': self.fx_focus_changed_on_amp,
        }

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

    @pyqtSlot(dict)
    def _new_data_from_amp(self, controls):
        # This slot is called when a control has been changed on the
        # amp. In response we emit all signals corresponding to the
        # keys in the controls dict
        for control, value in controls.iteritems():
            logger.debug('Data received:: control: {0} value: {1}'.format(control, value))
            try:
                self.control_signals[control].emit(value)
            except KeyError:
                logger.error('Unrecognized control {0}'.format(control))

    ##################################################################
    # The following methods are the slots for changes made on the gui
    ##################################################################
    def vol_slider_changed(self, value):
        logger.debug('Volume slider: {0}'.format(value))
        self.amp.set_control('volume', value)

    def tvp_selection_changed(self, idx):
        logger.debug('TVP selection: {0}'.format(idx))
        if idx == 0:
            self.amp.set_control('tvp_switch', 0)
        else:
            self.amp.set_control('tvp_switch', 1)
            self.amp.set_control('tvp_valve', idx - 1)

    def voice_selection_changed(self, idx):
        logger.debug('Voice selection: {0}'.format(idx))
        self.amp.set_control('voice', idx)

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
                logger.debug('Amp adjustment detected:: control: {0} value: {1}'.format(control, value))
                self.have_data.emit(settings)
            except NoDataAvailable:
                logger.debug('No changes of amp controls reported')
                continue

        logger.debug('AmpWatcher watching loop exited')

