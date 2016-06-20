# This file is part of Outsider.
#
# Outsider is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Outsider is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Outsider.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2015, Jonathan Underwood. All rights reserved.

from PyQt5 import uic
from PyQt5.QtCore import QObject, QThread, QMutex
from PyQt5.QtCore import pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QGroupBox, QSlider, QLCDNumber, QRadioButton, QListWidgetItem, QInputDialog
from PyQt5.QtWidgets import QApplication
from blackstarid import BlackstarIDAmp, NoDataAvailable, NotConnectedError
import logging
import os

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

    def __init__(self):
        super(Ui, self).__init__()

        # Dictionary of methods to call in response to changes to
        # controls made directly on the amplifier.
        self.response_funcs = {
            'voice': self.voice_changed_on_amp,
            'gain': self.gain_changed_on_amp,
            'volume': self.volume_changed_on_amp,
            'bass': self.bass_changed_on_amp,
            'middle': self.middle_changed_on_amp,
            'treble': self.treble_changed_on_amp,
            'isf': self.isf_changed_on_amp,
            'tvp_switch': self.tvp_switch_changed_on_amp,
            'tvp_valve': self.tvp_valve_changed_on_amp,
            'mod_switch': self.mod_switch_changed_on_amp,
            'delay_switch': self.delay_switch_changed_on_amp,
            'reverb_switch': self.reverb_switch_changed_on_amp,
            'mod_type': self.mod_type_changed_on_amp,
            'mod_segval': self.mod_segval_changed_on_amp,
            'mod_level': self.mod_level_changed_on_amp,
            'mod_speed': self.mod_speed_changed_on_amp,
            'mod_manual': self.mod_manual_changed_on_amp,
            'delay_type': self.delay_type_changed_on_amp,
            'delay_feedback': self.delay_feedback_changed_on_amp,
            'delay_level': self.delay_level_changed_on_amp,
            'delay_time': self.delay_time_changed_on_amp,
            'reverb_type': self.reverb_type_changed_on_amp,
            'reverb_size': self.reverb_size_changed_on_amp,
            'reverb_level': self.reverb_level_changed_on_amp,
            'fx_focus': self.fx_focus_changed_on_amp,
            'preset': self.preset_changed_on_amp,
            'manual_mode': self.manual_mode_changed_on_amp,
            'tuner_mode': self.tuner_mode_changed_on_amp,
            'tuner_note': self.tuner_note_changed_on_amp,
            'tuner_delta': self.tuner_delta_changed_on_amp,
            'resonance': self.resonance_changed_on_amp,
            'presence': self.presence_changed_on_amp,
            'master_volume': self.master_volume_changed_on_amp,
            'preset_name': self.preset_name_from_amp,
            'preset_settings': self.preset_settings_from_amp,
        }

        uif = os.path.join(os.path.split(__file__)[0], 'outsider.ui')
        logger.debug('loading GUI file: {0}'.format(uif))
        uic.loadUi(uif, self)

        self.amp_mutex = None
        self.amp = BlackstarIDAmp()
        self.watcher_thread = None

        # For now we don't do anything with preset settings
        # information other than store them in this list
        self.preset_settings = [None] * 128

        self.controls_enabled(False)
        self.show()

    def controls_enabled(self, bool):
        # Disable/Enable all widgets except the connect button (always enabled) and the master controls (always disabled)
        if bool is True:
            widgets = self.findChildren(QGroupBox)#(QObject)
            for w in widgets:
                if w == self.masterGroupBox:
                   pass
                elif w.objectName() == 'TVPGroupBox' and self.amp.model == 'id-core':
                    # self.TVPComboBox.setCurrentText('6L6')
                    # self.TVPRadioButton.setChecked(False)
                    # Don't enable as Core has  fixed TVP, probably with type 6L6
                    pass
                else:
                    w.setEnabled(bool)

        elif bool is False:
            widgets = self.findChildren(QGroupBox)#(QObject)
            for w in widgets:
                w.setEnabled(bool)

            widgets = self.findChildren(QSlider)
            for w in widgets:
                w.blockSignals(True)
                w.setValue(0)
                w.blockSignals(False)

            widgets = self.findChildren(QLCDNumber)
            for w in widgets:
                w.blockSignals(True) # Not nescessary
                w.display(0)
                w.blockSignals(False) # Not nescessary

            widgets = self.findChildren(QRadioButton)
            for w in widgets:
                w.blockSignals(True)
                w.setChecked(False)
                w.blockSignals(False)

    def connect(self):
        try:
            self.amp.connect()
            self.amp.drain()
            self.start_amp_watcher_thread()
            self.amp.startup()
            self.amp.get_all_preset_names()
        except NotConnectedError:
            raise

    def disconnect(self):
        if self.watcher_thread is not None:
            logger.debug('Closing down amplifier watching thread')
            self.shutdown_threads.emit()
            self.watcher_thread.quit()
            self.watcher_thread.wait()
            logger.debug('Amplifier watching thread finished')

        if self.amp.connected is True:
            self.amp.disconnect()

    def start_amp_watcher_thread(self):
        # Set up thread to watch for manual changes of the amp
        # controls at the amp (rather than gui) so we can update the
        # gui controls as needed. The way this is done is inspired
        # by:
        # http://stackoverflow.com/questions/29243692/pyqt5-how-to-make-qthread-return-data-to-main-thread
        # https://mayaposch.wordpress.com/2011/11/01/how-to-really-truly-use-qthreads-the-full-explanation/
        self.watcher_thread = QThread()
        self.amp_mutex = QMutex()
        self.watcher = AmpControlWatcher(self.amp, self.amp_mutex)
        self.watcher.have_data.connect(self.new_data_from_amp)
        self.shutdown_threads.connect(self.watcher.stop_watching)
        self.watcher.moveToThread(self.watcher_thread)
        self.watcher_thread.started.connect(self.watcher.work)

        self.watcher_thread.start()

    def closeEvent(self, event):
        # Ran when the application is closed.
        self.disconnect()
        super(Ui, self).close()
        logger.debug('Exiting')

    @pyqtSlot(dict)
    def new_data_from_amp(self, settings):
        for control, value in settings.items():
            try:
                self.response_funcs[control](value)
            except KeyError:
                logger.error('Unrecognized control {0}'.format(control))

    ######################################################################
    # The following methods are called when data is received from the amp
    ######################################################################
    def voice_changed_on_amp(self, value):
        self.voiceComboBox.blockSignals(True)
        self.voiceComboBox.setCurrentIndex(value)
        self.voiceComboBox.blockSignals(False)

    def gain_changed_on_amp(self, value):
        self.gainSlider.blockSignals(True)
        self.gainSlider.setValue(value)
        self.gainLcdNumber.display(value)
        self.gainSlider.blockSignals(False)

    def volume_changed_on_amp(self, value):
        self.volumeSlider.blockSignals(True)
        self.volumeSlider.setValue(value)
        self.volumeLcdNumber.display(value)
        self.volumeSlider.blockSignals(False)

    def bass_changed_on_amp(self, value):
        self.bassSlider.blockSignals(True)
        self.bassSlider.setValue(value)
        self.bassLcdNumber.display(value)
        self.bassSlider.blockSignals(False)

    def middle_changed_on_amp(self, value):
        self.middleSlider.blockSignals(True)
        self.middleSlider.setValue(value)
        self.middleLcdNumber.display(value)
        self.middleSlider.blockSignals(False)

    def treble_changed_on_amp(self, value):
        self.trebleSlider.blockSignals(True)
        self.trebleSlider.setValue(value)
        self.trebleLcdNumber.display(value)
        self.trebleSlider.blockSignals(False)

    def isf_changed_on_amp(self, value):
        self.isfSlider.blockSignals(True)
        self.isfSlider.setValue(value)
        self.isfLcdNumber.display(value)
        self.isfSlider.blockSignals(False)

    def tvp_switch_changed_on_amp(self, value):
        value = bool(value)
        self.TVPRadioButton.blockSignals(True)
        self.TVPRadioButton.setChecked(value)
        self.TVPComboBox.setEnabled(value)
        self.TVPRadioButton.blockSignals(False)

    def tvp_valve_changed_on_amp(self, value):
        self.TVPComboBox.blockSignals(True)
        self.TVPComboBox.setCurrentIndex(value)
        self.TVPComboBox.blockSignals(False)

    def mod_switch_changed_on_amp(self, value):
        value = bool(value)
        self.modRadioButton.blockSignals(True)
        self.modRadioButton.setChecked(value)
        self.modComboBox.setEnabled(value)
        self.modSegValSlider.setEnabled(value)
        self.modSegValLabel.setEnabled(value)
        self.modSegValLcdNumber.setEnabled(value)
        self.modSpeedSlider.setEnabled(value)
        self.modSpeedLabel.setEnabled(value)
        self.modSpeedLcdNumber.setEnabled(value)
        self.modLevelSlider.setEnabled(value)
        self.modLevelLabel.setEnabled(value)
        self.modLevelLcdNumber.setEnabled(value)
        self.modRadioButton.blockSignals(False)
        self.assess_manual_enabled()

    def delay_switch_changed_on_amp(self, value):
        value = bool(value)
        self.delayRadioButton.blockSignals(True)
        self.delayRadioButton.setChecked(value)
        self.delayComboBox.setEnabled(value)
        self.delayFeedbackSlider.setEnabled(value)
        self.delayFeedbackLabel.setEnabled(value)
        self.delayFeedbackLcdNumber.setEnabled(value)
        self.delayTimeSlider.setEnabled(value)
        self.delayTimeLabel.setEnabled(value)
        self.delayTimeLcdNumber.setEnabled(value)
        self.delayLevelSlider.setEnabled(value)
        self.delayLevelLabel.setEnabled(value)
        self.delayLevelLcdNumber.setEnabled(value)
        self.delayRadioButton.blockSignals(False)

    def reverb_switch_changed_on_amp(self, value):
        value = bool(value)
        self.reverbRadioButton.blockSignals(True)
        self.reverbRadioButton.setChecked(value)
        self.reverbComboBox.setEnabled(value)
        self.reverbSizeSlider.setEnabled(value)
        self.reverbSizeLabel.setEnabled(value)
        self.reverbSizeLcdNumber.setEnabled(value)
        self.reverbLevelSlider.setEnabled(value)
        self.reverbLevelLabel.setEnabled(value)
        self.reverbLevelLcdNumber.setEnabled(value)
        self.reverbRadioButton.blockSignals(False)

    def mod_type_changed_on_amp(self, value):
        self.modComboBox.blockSignals(True)
        self.modComboBox.setCurrentIndex(value)
        self.modComboBox.blockSignals(False)
        self.mod_type_changed(value)

    def mod_segval_changed_on_amp(self, value):
        self.modSegValSlider.blockSignals(True)
        self.modSegValSlider.setValue(value)
        self.modSegValLcdNumber.display(value)
        self.modSegValSlider.blockSignals(False)

    def mod_level_changed_on_amp(self, value):
        self.modLevelSlider.blockSignals(True)
        self.modLevelSlider.setValue(value)
        self.modLevelLcdNumber.display(value)
        self.modLevelSlider.blockSignals(False)

    def mod_speed_changed_on_amp(self, value):
        self.modSpeedSlider.blockSignals(True)
        self.modSpeedSlider.setValue(value)
        self.modSpeedLcdNumber.display(value)
        self.modSpeedSlider.blockSignals(False)

    def mod_manual_changed_on_amp(self, value):
        self.modManualSlider.blockSignals(True)
        self.modManualSlider.setValue(value)
        self.modManualLcdNumber.display(value)
        self.modManualSlider.blockSignals(False)
        
    def delay_type_changed_on_amp(self, value):
        self.delayComboBox.blockSignals(True)
        self.delayComboBox.setCurrentIndex(value)
        self.delayComboBox.blockSignals(False)

    def delay_feedback_changed_on_amp(self, value):
        self.delayFeedbackSlider.blockSignals(True)
        self.delayFeedbackSlider.setValue(value)
        self.delayFeedbackLcdNumber.display(value)
        self.delayFeedbackSlider.blockSignals(False)

    def delay_level_changed_on_amp(self, value):
        self.delayLevelSlider.blockSignals(True)
        self.delayLevelSlider.setValue(value)
        self.delayLevelLcdNumber.display(value)
        self.delayLevelSlider.blockSignals(False)

    def delay_time_changed_on_amp(self, value):
        self.delayTimeSlider.blockSignals(True)
        self.delayTimeSlider.setValue(value)
        self.delayTimeLcdNumber.display(value)
        self.delayTimeSlider.blockSignals(False)

    def reverb_type_changed_on_amp(self, value):
        self.reverbComboBox.blockSignals(True)
        self.reverbComboBox.setCurrentIndex(value)
        self.reverbComboBox.blockSignals(False)

    def reverb_size_changed_on_amp(self, value):
        self.reverbSizeSlider.blockSignals(True)
        self.reverbSizeSlider.setValue(value)
        self.reverbSizeLcdNumber.display(value)
        self.reverbSizeSlider.blockSignals(False)

    def reverb_level_changed_on_amp(self, value):
        self.reverbLevelSlider.blockSignals(True)
        self.reverbLevelSlider.setValue(value)
        self.reverbLevelLcdNumber.display(value)
        self.reverbLevelSlider.blockSignals(False)

    def fx_focus_changed_on_amp(self, value):
        # This is a bit of a misnomer, as the amp doesn't emit data if
        # the user changes the effect focus on the amp. However, when
        # the user disables an effect in the GUI, if that effect had
        # focus, we want to move the focus to another effect, if one
        # is enabled. The way we do that, is in the slots associated
        # with toggling an effect (see below), if the effect is
        # disabled we issue a packet to query the state of all
        # controls, which gives us an opportunity to react in this
        # function here.
        if value == 1 and not self.modRadioButton.isChecked():
            if self.delayRadioButton.isChecked():
                self.amp.set_control('fx_focus', 2)
            elif self.reverbRadioButton.isChecked():
                self.amp.set_control('fx_focus', 3)

        elif value == 2 and not self.delayRadioButton.isChecked():
            if self.reverbRadioButton.isChecked():
                self.amp.set_control('fx_focus', 3)
            elif self.modRadioButton.isChecked():
                self.amp.set_control('fx_focus', 1)

        if value == 3 and not self.reverbRadioButton.isChecked():
            if self.modRadioButton.isChecked():
                self.amp.set_control('fx_focus', 1)
            elif self.delayRadioButton.isChecked():
                self.amp.set_control('fx_focus', 2)

    def preset_name_from_amp(self, namelist):
        idx = namelist[0] - 1 # Presets are numbered from 1
        name = str(namelist[0]) + '. ' + namelist[1]
        item = self.presetNamesList.item(idx)
        if item is None:
            self.presetNamesList.insertItem(idx, name)
        else:
            item.setText(name)

    def preset_settings_from_amp(self, settings):
        self.preset_settings[settings.preset_number] = settings

    def preset_changed_on_amp(self, value):
        # TODO: This function is a stub for now, but will need hooking
        # up to a combo box widget in the gui for selecting/indicating
        # preset
        logger.debug('preset changed on amp: {0}'.format(value))
        self.presetNamesList.setCurrentRow(value - 1)

    def manual_mode_changed_on_amp(self, value):
        # TODO: This also needs hooking up to the preset combo box in
        # the GUI
        if value == 1:
            # Here we'd need to set the combo box to "Manual"
            pass
        else:
            # We're no longer in manual mode, but since in this case
            # another packet will indicate the preset selected,
            # there's no need to do anything here.
            pass
        logger.debug('manual_mode changed on amp: {0}'.format(value))

    def tuner_mode_changed_on_amp(self, value):
        # TODO: Stub for now - needs hooking into a suitable tuner widget
        logger.debug('tuner_mode changed on amp: {0}'.format(value))

    def tuner_note_changed_on_amp(self, value):
        # TODO: Stub for now - needs hooking into a suitable tuner widget
        logger.debug('tuner_note changed on amp: {0}'.format(value))

    def tuner_delta_changed_on_amp(self, value):
        # TODO: Stub for now - needs hooking into a suitable tuner widget
        logger.debug('tuner_delta changed on amp: {0}'.format(value))

    def resonance_changed_on_amp(self, value):
        self.resonanceSlider.blockSignals(True)
        self.resonanceSlider.setValue(value)
        self.resonanceLcdNumber.display(value)
        self.resonanceSlider.blockSignals(False)
        logger.debug('resonance changed on amp: {0}'.format(value))

    def presence_changed_on_amp(self, value):
        self.presenceSlider.blockSignals(True)
        self.presenceSlider.setValue(value)
        self.presenceLcdNumber.display(value)
        self.presenceSlider.blockSignals(False)
        logger.debug('presence changed on amp: {0}'.format(value))

    def master_volume_changed_on_amp(self, value):
        self.masterVolumeSlider.blockSignals(True)
        self.masterVolumeSlider.setValue(value)
        self.masterVolumeLcdNumber.display(value)
        self.masterVolumeSlider.blockSignals(False)
        logger.debug('master_volume changed on amp: {0}'.format(value))

    ##################################################################
    # The following methods are the slots for changes made on the gui
    ##################################################################
    @pyqtSlot()
    def on_connectToAmpButton_clicked(self):
        if self.amp.connected is False:
            try:
                self.connect()
                # Enable widgets
                self.controls_enabled(True)
                self.connectToAmpButton.setText('Disconnect Amp')

            except NotConnectedError:
                QMessageBox.information(self,'Outsider', 'No amplifier found')
        else:
            self.disconnect()
            self.controls_enabled(False)
            self.connectToAmpButton.setText('Connect to Amp')

    @pyqtSlot(int)
    def on_volumeSlider_valueChanged(self, value):
        logger.debug('Volume slider: {0}'.format(value))
        self.amp.set_control('volume', value)

    @pyqtSlot(int)
    def on_gainSlider_valueChanged(self, value):
        logger.debug('Gain slider: {0}'.format(value))
        self.amp.set_control('gain', value)

    @pyqtSlot(int)
    def on_bassSlider_valueChanged(self, value):
        logger.debug('Bass slider: {0}'.format(value))
        self.amp.set_control('bass', value)

    @pyqtSlot(int)
    def on_middleSlider_valueChanged(self, value):
        logger.debug('Middle slider: {0}'.format(value))
        self.amp.set_control('middle', value)

    @pyqtSlot(int)
    def on_trebleSlider_valueChanged(self, value):
        logger.debug('Treble slider: {0}'.format(value))
        self.amp.set_control('treble', value)

    @pyqtSlot(int)
    def on_isfSlider_valueChanged(self, value):
        logger.debug('ISF slider: {0}'.format(value))
        self.amp.set_control('isf', value)

    @pyqtSlot(int)
    def on_TVPComboBox_currentIndexChanged(self, idx):
        logger.debug('TVP selection: {0}'.format(idx))
        self.amp.set_control('tvp_valve', idx)

    @pyqtSlot(bool)
    def on_TVPRadioButton_toggled(self, state):
        logger.debug('TVP switch: {0}'.format(state))
        if state == True:
            self.amp.set_control('tvp_switch', 1)
        else:
            self.amp.set_control('tvp_switch', 0)

    @pyqtSlot(int)
    def on_voiceComboBox_currentIndexChanged(self, idx):
        logger.debug('Voice selection: {0}'.format(idx))
        self.amp.set_control('voice', idx)

    @pyqtSlot(bool)
    def on_modRadioButton_toggled(self, state):
        logger.debug('Mod switch: {0}'.format(state))
        self.amp.set_control('mod_switch', state)
        if state == 1:
            self.amp.set_control('fx_focus', 1)
        else:
            # Find out if the mod effect had focus before being
            # deactivated and shift focus to another effect if
            # possible. The only mechanism we have available to do
            # this is to get the status of all controls, sadly.
            self.amp.startup()
        self.assess_manual_enabled()

    @pyqtSlot(int)
    def on_modComboBox_currentIndexChanged(self, value):
        logger.debug('Mod Combo Box: {0}'.format(value))
        self.amp.set_control('mod_type', value)
        self.amp.set_control('fx_focus', 1)

    @pyqtSlot(int)
    def on_modSegValSlider_valueChanged(self, value):
        logger.debug('Mod SegVal slider: {0}'.format(value))
        self.amp.set_control('mod_segval', value)
        self.amp.set_control('fx_focus', 1)

    @pyqtSlot(int)
    def on_modLevelSlider_valueChanged(self, value):
        logger.debug('Mod Level slider: {0}'.format(value))
        self.amp.set_control('mod_level', value)
        self.amp.set_control('fx_focus', 1)

    @pyqtSlot(int)
    def on_modSpeedSlider_valueChanged(self, value):
        logger.debug('Mod Speed slider: {0}'.format(value))
        self.amp.set_control('mod_speed', value)
        self.amp.set_control('fx_focus', 1)

    @pyqtSlot(int)
    def on_modManualSlider_valueChanged(self, value):
        logger.debug('Mod Manual slider: {0}'.format(value))
        self.amp.set_control('mod_manual', value)
        self.amp.set_control('fx_focus', 1)

    @pyqtSlot(bool)
    def on_delayRadioButton_toggled(self, state):
        logger.debug('Delay switch: {0}'.format(state))
        self.amp.set_control('delay_switch', state)
        if state == 1:
            self.amp.set_control('fx_focus', 2)
        else:
            # Find out if the mod effect had focus before being
            # deactivated and shift focus to another effect if
            # possible. The only mechanism we have available to do
            # this is to get the status of all controls, sadly.
            self.amp.startup()

    @pyqtSlot(int)
    def on_delayComboBox_currentIndexChanged(self, value):
        logger.debug('Delay Combo Box: {0}'.format(value))
        self.amp.set_control('delay_type', value)
        self.amp.set_control('fx_focus', 2)

    @pyqtSlot(int)
    def on_delayFeedbackSlider_valueChanged(self, value):
        logger.debug('Delay feedback slider: {0}'.format(value))
        self.amp.set_control('delay_feedback', value)
        self.amp.set_control('fx_focus', 2)

    @pyqtSlot(int)
    def on_delayLevelSlider_valueChanged(self, value):
        logger.debug('Delay Level slider: {0}'.format(value))
        self.amp.set_control('delay_level', value)
        self.amp.set_control('fx_focus', 2)

    @pyqtSlot(int)
    def on_delayTimeSlider_valueChanged(self, value):
        logger.debug('Delay Time slider: {0}'.format(value))
        self.amp.set_control('delay_time', value)
        self.amp.set_control('fx_focus', 2)

    @pyqtSlot(bool)
    def on_reverbRadioButton_toggled(self, state):
        logger.debug('Reverb switch: {0}'.format(state))
        self.amp.set_control('reverb_switch', state)
        if state == 1:
            self.amp.set_control('fx_focus', 3)
        else:
            # Find out if the mod effect had focus before being
            # deactivated and shift focus to another effect if
            # possible. The only mechanism we have available to do
            # this is to get the status of all controls, sadly.
            self.amp.startup()

    @pyqtSlot(int)
    def on_reverbComboBox_currentIndexChanged(self, value):
        logger.debug('Reverb Combo Box: {0}'.format(value))
        self.amp.set_control('reverb_type', value)
        self.amp.set_control('fx_focus', 3)

    @pyqtSlot(int)
    def on_reverbSizeSlider_valueChanged(self, value):
        logger.debug('Reverb Size slider: {0}'.format(value))
        self.amp.set_control('reverb_size', value)
        self.amp.set_control('fx_focus', 3)

    @pyqtSlot(int)
    def on_reverbLevelSlider_valueChanged(self, value):
        logger.debug('Reverb Level slider: {0}'.format(value))
        self.amp.set_control('reverb_level', value)
        self.amp.set_control('fx_focus', 3)

    @pyqtSlot(QListWidgetItem)
    def on_presetNamesList_itemDoubleClicked(self, item):
        idx = self.presetNamesList.currentRow()
        preset = idx + 1 # Presets are numbered from 1
        self.amp.select_preset(preset)

    @pyqtSlot()
    def on_renamePresetPushButton_clicked(self):
        idx = self.presetNamesList.currentRow()
        preset = idx + 1 # Presets are numbered from 1

        name, ok = QInputDialog.getText(
            self, 'Input Dialog',
            'Enter new name for preset {0}:'.format(preset)
        )
        if ok == True:
            # We need to grab the amp mutex to stop the amp watcher
            # thread from consuming the packets emitted by the amp in
            # the preset rename process
            self.amp_mutex.lock()
            self.amp.set_preset_name(preset, name)
            self.amp_mutex.unlock()

    # When the modulation type is changed, we want to change the label
    # associated with the segment value control. So, we need to define
    # a slot to trigger when the modulation type is changed, and a
    # signal to raise to communicate back to the UI what the label
    # should be changed to. The signal has argument type str, which is
    # automatically converted to type QString.
    mod_segval_label_update = pyqtSignal(str)

    @pyqtSlot(int)
    def mod_type_changed(self, value):
        if value == 0:
            self.mod_segval_label_update.emit('Mix')
        elif value == 1:
            self.mod_segval_label_update.emit('Feedback')
        elif value == 2:
            self.mod_segval_label_update.emit('Mix')
        elif value == 3:
            self.mod_segval_label_update.emit('FreqMod')
        self.assess_manual_enabled()

    @pyqtSlot(int)
    def on_resonanceSlider_valueChanged(self, value):
        logger.debug('Resonance slider: {0}'.format(value))
        self.amp.set_control('resonance', value)

    @pyqtSlot(int)
    def on_presenceSlider_valueChanged(self, value):
        logger.debug('Presence slider: {0}'.format(value))
        self.amp.set_control('presence', value)

    @pyqtSlot(int)
    def on_masterVolumeSlider_valueChanged(self, value):
        logger.debug('Master volume slider: {0}'.format(value))
        self.amp.set_control('master_volume', value)


    # When the modulation is enabled and the modution type is flanger, enable
    # the manual control.
    def assess_manual_enabled(self):
        value = self.modRadioButton.isChecked() and self.modComboBox.currentIndex() == 1
        self.modManualSlider.blockSignals(True)
        self.modManualSlider.setEnabled(value)
        self.modManualSlider.blockSignals(False)


class AmpControlWatcher(QObject):
    have_data = pyqtSignal(dict, name='have_data')
    shutdown = False

    @pyqtSlot()
    def stop_watching(self):
        logger.debug('signal received in stop_watching slot')
        self.shutdown = True

    def __init__(self, amp, mutex):
        super(AmpControlWatcher, self).__init__()
        self.amp = amp
        self.amp_mutex = mutex
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
            if self.amp_mutex.tryLock():
                try:
                    settings = self.amp.read_data()
                except NoDataAvailable:
                    self.amp_mutex.unlock()
                    logger.debug('No changes of amp controls reported')
                else:
                    self.amp_mutex.unlock()
                    for control, value in settings.items():
                        if control == 'preset_settings':
                            logger.debug(
                                'Amp preset settings:: preset: {0} settings: {1}'.format(
                                    value.preset_number, value)
                            )
                        elif control == 'preset_name':
                            logger.debug(
                                'Amp preset name:: preset: {0} name: {1}'.format(
                                    value[0], value[1])
                            )
                        else:
                            logger.debug(
                                'Amp adjustment detected:: control: {0} value: {1}'.format(
                                    control, value)
                            )

                        self.have_data.emit(settings)

        logger.debug('AmpWatcher watching loop exited')
