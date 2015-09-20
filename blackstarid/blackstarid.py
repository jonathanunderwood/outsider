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

import usb.core
import usb.util
import logging

# Set up logging and create a null handler in case the application doesn't
# provide a log handler
logger = logging.getLogger('outsider.blackstarid')


class __NullHandler(logging.Handler):

    def emit(self, record):
        pass

__null_handler = __NullHandler()
logger.addHandler(__null_handler)


class NotConnectedError(Exception):

    '''Raised when an operation requiring an amp is called when no amp is
    connected.

    '''
    pass


class WriteToAmpError(Exception):

    '''Raised when a write operation to the amplifier fails or is incomplete.

    '''
    pass


class NoDataAvailable(Exception):

    '''Raised when a read operation is called but no data is available
    from the amplifer.

    '''
    pass


class BlackstarIDAmpPreset(object):

    def __init__(self):
        pass

    def from_packet(self, packet):
        # Check that the packet passed is actually a packet containing
        # preset settings.
        if packet[0] != 0x02 or packet[1] != 0x05 or packet[3] != 0x2A:
            raise ValueError('Packet is not a preset settings packet')

        self.preset_number = packet[2]

        self.voice = packet[4]  # 00-05
        self.gain = packet[5]  # 00-7F
        self.volume = packet[6]  # 00-7F
        self.bass = packet[7]  # 00-7F
        self.middle = packet[8]  # 00-7F
        self.treble = packet[9]  # 00-7F
        self.isf = packet[10]  # 00-7F
        self.tvp = packet[17]  # 00 or 01
        self.tvp_valve = packet[11]  # 00-05
        self.modulation = packet[18]  # 00 or 01
        self.delay = packet[19]  # 00 or 01

        self.reverb = packet[20]  # 00 or 01
        self.reverb_type = packet[32]  # 00-03
        self.reverb_segval = packet[33]  # 00-1F

        # There is a point of confusion here. Adjusting reverb level
        # alters packet[35], but also packet[12]. However, adjusting
        # modulation level changes only packet[12]. So we assume that
        # packet[35] is reverb level, packet[12] is modulation level,
        # and that a firmware bug is changing packet[12] when reverb
        # level is changed. Will be interesting to see if this changes
        # with a later firmware.
        self.reverb_level = packet[35]  # 00-7F

        self.delay_type = packet[26]  # 00-03
        self.delay_segval = packet[27]  # 00-1F
        self.delay_level = packet[29]  # 00-7F

        # The delay time setting is specifed with two bytes,
        # packet[30] and packet[31]. With the delay set to the minimum
        # value, packet[30,31]=[0x64, 0x00], and with the delay time
        # set to maximum packet[30,31]=[0xD0, 0x07]. Somewhere in the
        # middle, packet[30,31]=[0xF4, 0x03]. So, it seems packet[31]
        # is some course multiplier, and packet[31] is a finer
        # delineation. According to blackstar the minimum delay is 100
        # ms, and the maximum delay is 2s. So, [0x64, 0x00] = 100ms
        # makes sense. So, the actual delay in ms is:
        # delay = (packet[31] * 256 + packet[30])
        self.delay_time_1 = packet[30]  # 00-FF
        self.delay_time_2 = packet[31]  # 00-07

        self.modulation_type = packet[21]  # 00-03
        self.modulation_segval = packet[22]  # 00-1F
        self.modulation_level = packet[12]  # 00-7F
        self.modulation_rate = packet[25]  # 00-7F

        # This next setting is weird, it seems to reflect the absolute
        # position of the segmented selection knowb when selection
        # modulation type and segment value. It takes values between
        # 00-1F in the "1" segment, 20-3F in the "2" segment, 30-4F
        # when in the "3" segment and 40-5F when in the "4" segment.
        self.modulation_abspos = packet[13]

        # This denotes which efect has "focus" (to use the term in the
        # blackstar manual) i.e. is being controlled by the level,
        # type and tap controls. This is the effect which has the
        # green LED lit on the front panel. 01 is Mod, 02 is delay, 03
        # is reverb.
        self.effect_focus = packet[39]

# Implementation note regarding reading delay time info from the amp
# when controls are changed on the amp:
#
# 1. Ff the tap button is used, then a single packet is returned with
#    two bytes specifying the delay time. This packet will have the
#    form [0x03, 0x1b, 0x00, 0x02, A, B,...] and the delay time is
#    (256*B)+A.
#
# 2. If the user holds down the tap button and uses the level knob to
#    set the delay time, then two packets come back from the amp for
#    each adjustment. The first packet specifies the fine adjustment,
#    and the second specifies the coarse adjustment. The first packet
#    has the form [0x03, 0x1b, 0x00, 0x01, A, ...] and the second has
#    the form [0x03, 0x1c, 0x00, 0x02, B,...] and the delay time is
#    (256*B)+A.


class BlackstarIDAmp(object):

    vendor = 0x27d4

    amp_models = {
        0x0001: 'id-tvp',
        0x0010: 'id-core',
    }

    controls = {
        'voice': 0x01,
        'gain': 0x02,
        'volume': 0x03,
        'bass': 0x04,
        'middle': 0x05,
        'treble': 0x06,
        'isf': 0x07,
        'tvp_valve': 0x08,
        'tvp_switch': 0x0e,
        'mod_switch': 0x0f,
        'delay_switch': 0x10,
        'reverb_switch': 0x11,
        'mod_type': 0x12,
        'mod_segval': 0x13,
        'mod_level': 0x15,
        'mod_speed': 0x16,
        'delay_type': 0x17,
        'delay_feedback': 0x18,  # Segment value
        'delay_level': 0x1a,
        'delay_time': 0x1b,
        'delay_time_coarse': 0x1c,
        'reverb_type': 0x1d,
        'reverb_size': 0x1e,  # Segment value
        'reverb_level': 0x20,
        'fx_focus': 0x24,
    }

    # Construct a reversed dictionary so we can look up the control
    # changed from USB packet data
    control_ids = dict([(val, key) for key, val in controls.iteritems()])

    control_limits = {
        'voice': [0, 5],
        'gain': [0, 127],
        'volume': [0, 127],
        'bass': [0, 127],
        'middle': [0, 127],
        'treble': [0, 127],
        'isf': [0, 127],
        'tvp_valve': [0, 5],
        'tvp_switch': [0, 1],
        'mod_switch': [0, 1],
        'delay_switch': [0, 1],
        'reverb_switch': [0, 1],
        'mod_type': [0, 3],
        'mod_segval': [0, 31],
        'mod_level': [0, 127],
        'mod_speed': [0, 127],
        'delay_type': [0, 3],
        'delay_feedback': [0, 31],  # Segment value
        'delay_level': [0, 127],
        'delay_time': [100, 2000],
        'delay_time_coarse': [0, 7],  # For documentation only, never used
        'reverb_type': [0, 3],
        'reverb_size': [0, 31],  # Segment value
        'reverb_level': [0, 127],
        'fx_focus': [1, 3],
    }

    def __init__(self):
        self.connected = False
        self.reattach_kernel = []
        self.device = None
        self.model = None
        self.interrupt_in = None
        self.interrupt_out = None

    def connect(self):

        # Find device. Note usb.core.find returns an iterator if
        # find_all is True
        devices = list(usb.core.find(idVendor=self.vendor, find_all=True))

        ndev = len(devices)
        if ndev < 1:
            logger.error('Amplifier device not found')
            raise NotConnectedError('Amplifier device not found')
        elif ndev > 1:
            # In future we shouldn't bail here but change the API to
            # deal with the possibility of multiple amps and provide
            # mechanism for an application to allow the user to select
            # which amp they want to connect to. For now, we'll just
            # bail.
            logger.error('More than one amplifier found')
            raise NotConnectedError('More than one amplifier found')

        dev = devices[0]
        logger.debug('Device:\n' + str(dev))

        dev.reset()

        # We know for this device there's only one configuration, so
        # no need to iterate through configurations below.
        cfg = dev.get_active_configuration()

        self.reattach_kernel = [False] * cfg.bNumInterfaces

        # for intf in range(cfg.bNumInterfaces):
        for intf in cfg:
            if dev.is_kernel_driver_active(intf.bInterfaceNumber):
                try:
                    dev.detach_kernel_driver(intf.bInterfaceNumber)
                except usb.core.USBError as e:
                    raise usb.core.USBError(
                        "Could not detach kernel driver from interface({0}): {1}".format(intf.bInterfaceNumber, str(e)))
                # Note that for interfaces with more than one setting
                # we'll iterate more than once through that
                # interface. The second and later times it won't be
                # attached to the kernel so we won't reach here, but
                # it's ok, as on the first time we set this to be
                # True. Be careful with alternative strategies - it
                # would be very easy to overwrite the True below with
                # False on the second pass!
                self.reattach_kernel[intf.bInterfaceNumber] = True

        # Set the device to use the default (and only) configuration
        dev.set_configuration()

        # Interface 0 seems always to be the interrupt endpoint
        # interface
        interrupt_intf = cfg[0, 0] # same as cfg.interfaces()[0]
        intf_out = usb.util.find_descriptor \
                   (interrupt_intf,
                    custom_match=lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        intf_in = usb.util.find_descriptor \
                  (interrupt_intf,
                   custom_match=lambda e: \
                   usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
        # Now get their addresses
        self.interrupt_in = intf_in.bEndpointAddress
        self.interrupt_out = intf_out.bEndpointAddress

        self.connected = True
        self.device = dev
        self.model = self.amp_models[dev.idProduct]

    def __del__(self):
        if self.connected:
            self.disconnect()

    def disconnect(self):
        '''Disconnect from the amplifer and release all resources. If we're
        already disconnected, this method is a no-op

        '''
        if self.connected is False:
            return

        # http://stackoverflow.com/questions/12542799/communication-with-the-usb-device-in-python
        # This returns all resources to the state they were in after
        # usb.core.find() returned (according to the PyUSB tutorial
        # that is) ...
        usb.util.dispose_resources(self.device)

        # ... so we still need to reattach interfaces to kernel driver
        # if they were were originally attached to a kernel driver.
        cfg = self.device.get_active_configuration()

        for intf in cfg:
            if self.reattach_kernel[intf.bInterfaceNumber] is True:
                # Note that for interfaces with more than one setting,
                # we'll iterate more than once through that
                # interface. So, on the second or more visits, the
                # interface will have already been re-attached to the
                # kernel - attempting to reattach it again will raise
                # a Resource Busy exception.
                if not self.device.is_kernel_driver_active(intf.bInterfaceNumber):
                    try:
                        self.device.attach_kernel_driver(intf.bInterfaceNumber)
                    except usb.core.USBError as e:
                        raise usb.core.USBError(
                            "Could not attach kernel driver to interface({0}): {1}".format(intf.bInterfaceNumber, str(e)))

        self.connected = False
        self.device = None
        self.reattach_kernel = []
        self.model = None
        self.interrupt_in = None
        self.interrupt_out = None

    def _send_data(self, data):
        '''Take a list of bytes and send it to endpoint as a correctly
        encoded string.'''
        # Form a string of hex bytes from the list
        string = ''.join(chr(n) for n in data)

        data_length = len(data)

        if data_length != 64:
            logger.warning(
                'data length is {0} which is not 64'.format(data_length))

        # Write to endpoint, returning the number of bytes written
        bytes_written = self.device.write(self.interrupt_out, string)
        if bytes_written != data_length:
            raise WriteToAmpError(
                'Failed to write {0} bytes to amplifier.'.format(data_length - bytes_written))

        return bytes_written

    def _format_data(self, packet):
        '''Format a data packet for printing with 16 columns for easy 
        comparison with tools such as wireshark.'''

        # Turn the entries into hex strings
        # strings = ['%0.2X' % i for i in packet]
        strings = ['{0:02X}'.format(i) for i in packet]

        # Now break up into lines, each with 16 entries
        length = len(strings)

        lines = (length / 16) + (length % 16 > 16)

        string = ''
        for line in xrange(lines):
            start = line * 16
            end = start + 16
            string += ' '.join(strings[start:end])
            string += '\n'

        return string[0:-1]  # remove last \n

    def set_control(self, control, value):
        try:
            ctrl_byte = self.controls[control]
        except KeyError:
            msg = 'Control key {0} not a valid identifier'.format(control)
            logger.error(msg)
            raise ValueError(msg)

        limits = self.control_limits[control]

        if value not in range(limits[0], limits[1] + 1):
            msg = 'Value {0} is not valid for control {1}'.format(
                value, control)
            logger.error(msg)
            raise ValueError(msg)

        data = [0x00] * 64

        if control is 'delay_time':
            data[0:4] = [0x03, ctrl_byte, 0x00, 0x02]
            data[4] = value % 256
            data[5] = value / 256
        else:
            data[0:5] = [0x03, ctrl_byte, 0x00, 0x01, value]

        ret = self._send_data(data)

        logger.debug('Set control: {0} to value {1}'.format(control, value))

        return ret

    def startup(self):
        '''This method sends a packet to the amplifier which results in a
        reply of 3 packets. For Insider this is the first packet
        sent. The 2nd of the reply packets specifies the current
        settings of the amp.

        This function doesn't deal with the response packet - use the
        read_data method for that, once for each packet.

        It is adviseable to call the drain method prior to this
        function to ensure no pending packets are present.

        '''

        if self.connected is False:
            raise NotConnectedError

        logger.debug('Sending startup packet')

        data = [0x00] * 64
        data[0] = 0x81
        data[3:8] = [0x04, 0x03, 0x06, 0x02, 0x7a]

        self._send_data(data)

        logger.debug('Startup packet sent')

    def get_preset_names(self):
        '''Returns a list of strings, each of which is a preset name.  Note
        that this method interprets response packets itself, and does
        not rely on read_data_packet. This may change in the future,
        and this function may simply send the request packet. The
        design is in process.

        '''
        names = []
        for i in xrange(1, 128):
            data = [0x00] * 64

            data[0:4] = [0x02, 0x04, i, 0x00]

            self._send_data(data)

            ret = self.device.read(self.interrupt_in, 64)

            namel = filter(lambda n: n > 0, ret[4:25])
            namec = [str(unichr(i)) for i in namel]
            names += [''.join(namec)]

        return names

    def read_data_packet(self):
        '''Attempts to read a data packet from the amplifier. If no data is
        available a usb.core.USBError exception will be raised.

        This returns a dictionary of values for the various amp
        settings, and will return info from a single packet. The
        possible dictionary keys are the same as for the class
        attribute 'controls' dictionary and should be
        self-explanatory.

        At present this function also deals with the 3 response
        packets from the initialization packet that is sent to the
        amplifier, but this may change in the future.

        '''
        try:
            packet = self.device.read(self.interrupt_in, 64)
        except usb.core.USBError:
            raise NoDataAvailable

        # The 4th byte (packet[3]) specifies the subsequent number of
        # bytes specifying a value.
        if packet[0] == 0x03:
            if packet[3] == 0x01 or packet[3] == 0x02:
                # Identify which control was changed
                id = packet[1]
                try:
                    control = self.control_ids[id]
                except KeyError:
                    errstr = ('Unrecognized control ID: {0:02X}\n'.format(
                        packet[1]) + self._format_data(packet))
                    logger.error(errstr)
                    raise KeyError(errstr)
            if packet[3] == 0x01:
                value = packet[4]
                logger.debug(
                    'Data from amp:: control: {0} value: {1}'.format(control, value))
                if control == 'delay_time':
                    return {'delay_time_fine': value}
                else:
                    return {control: value}
            elif packet[3] == 0x02:
                if control == 'delay_time':
                    value = packet[4] + 256 * packet[5]
                    logger.debug(
                        'Data from amp:: control: {0} value: {1}'.format(control, value))
                    return {control: value}
                elif control == 'delay_type':
                    delay_type = packet[4]
                    delay_feedback = packet[5]
                    logger.debug('Data from amp:: delay_type: {0} delay_feedback: {1}\n'.format(
                        delay_type, delay_feedback))
                    return {'delay_type': packet[4], 'delay_feedback': packet[5]}
                elif control == 'reverb_type':
                    reverb_type = packet[4]
                    reverb_size = packet[5]
                    logger.debug('Data from amp:: reverb_type: {0} reverb_size: {1}\n'.format(
                        reverb_type, reverb_size))
                    return {'reverb_type': packet[4], 'reverb_size': packet[5]}
                elif control == 'mod_type':
                    mod_type = packet[4]
                    mod_segval = packet[5]
                    logger.debug(
                        'Data from amp:: mod_type: {0} mod_segval: {1}\n'.format(mod_type, mod_segval))
                    return {'mod_type': packet[4], 'mod_segval': packet[5]}
            elif packet[3] == 0x2a:
                # Then packet is a packet describing all current control
                # settings - note that the 4th byte being 42 (0x2a)
                # distinguishes this from a packet specifying the voice
                # setting for which the 4th byte would be 0x01. This is
                # the 2nd of 3 response packets to the startup packet.
                # Conveniently the byte address for each control setting
                # corresponds to the ID number of the control plus
                # 3. Weird, but handy.
                logger.debug('All controls info packet received\n')
                settings = {'all_settings': True}
                for control, id in self.controls.iteritems():
                    if control == 'delay_time':
                        settings[control] = (
                            packet[id + 4] * 256) + packet[id + 3]
                        logger.debug('All controls data:: control: {0} value: {1}'.format(
                            control, settings[control]))
                    elif control == 'delay_time_coarse':
                        # Skip this one, as we already deal with it
                        # for the delay_time entry
                        pass
                    else:
                        settings[control] = packet[id + 3]

                return settings

        elif packet[0] == 0x07:
            # This is the first of the three response packets to the
            # startup packet. At this point, I don't know what this
            # packet describes. Firmware version? For TVP60h it is:
            # 07 00 00 03 04 00 01 01 40 00 00 00 00 3D 00 00
            # 10 00 01 00 00 00 00 00 00 00 00 02 00 01 01 03
            # 00 15 00 00 00 00 00 00 00 00 00 00 00 00 00 00
            # 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
            logger.debug(
                'Unhandled startup packet 1\n' + self._format_data(packet))

            return {}

        elif packet[0] == 0x08:
            # This is the third of the three response packets to the
            # startup packet. This packet seems to indicate what
            # preset is selected (or manual).
            # 08 01 00 1B F0 00 01 01 40 00 00 00 00 3D 00 00
            # 10 00 01 00 00 00 00 00 00 00 00 02 00 01 01 03
            # 00 15 00 00 00 00 00 00 00 00 00 00 00 00 00 00
            # 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
            logger.debug(
                'Unhandled startup packet 3\n' + self._format_data(packet))

            return {}

        # We'll only reach here if we haven't handled the packet and returned
        # earlier
        logger.debug(
            'Unhandled data packet in read_data\n' + self._format_data(packet))
        return {}

    def read_data(self):
        settings = self.read_data_packet()
        if 'delay_time_fine' in settings:
            # We received the least significant part of the delay_time
            # only, so we need to store it and wait for the next
            # packet for the most significant part of the delay_time
            # before we can emit a signal to update the
            # delay_time. This is stupidly stateful, but it's a quirk
            # of the amp design. So, we need to read more packets
            # until we find delay_time_course, being careful not to
            # lose any other data we may receive in the meantime. In
            # practive the two packets are probably guaranteed by the
            # amp firmware to be sequential, but we don't know that
            # for sure.
            delay_time_fine = settings.pop('delay_time_fine')
            while True:
                s = self.read_data_packet()
                if 'delay_time_coarse' in s:
                    delay_time_coarse = s.pop('delay_time_coarse')
                    settings.update(s)
                    settings['delay_time'] = (
                        delay_time_coarse * 256) + delay_time_fine
                    return settings
                else:
                    settings.update(s)
        else:
            return settings

    def poll_and_log(self):
        '''Test function which continuously queries the amp for data and
        logs the returned packets at the debug level.

        '''
        while True:
            try:
                ret = self.device.read(self.interrupt_in, 64)
                logger.debug('Polled packet\n' + self._format_data(ret))
            except usb.core.USBError:  # Ignore timeouts
                pass

    def drain(self):
        '''Read data until no more is available and then return. Packets are
        discarded.

        '''
        while True:
            try:
                ret = self.device.read(self.interrupt_in, 64)
                #logger.debug('Drained packet\n' + self._format_data(ret))
            except usb.core.USBError:  # No more data available
                return

    def get_preset_settings(self, preset):
        # This is an unfinished test function, will be removed.
        data = [0x00] * 64

        data[0:4] = [0x02, 0x05, preset, 0x00]

        self._send_data(data)

        ret = self.device.read(0x81, 64)
        logger.debug('Preset settings for preset {0}\n'.format(preset)
                     + self._format_data(ret))

if __name__ == '__main__':
    import logging
    import sys

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('outsider.blackstarid')

    try:
        amp = BlackstarIDAmp()
    except:
        sys.exit(1)

    try:
        amp.poll_and_log()
    except KeyboardInterrupt:
        sys.exit(0)
