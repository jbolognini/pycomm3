# -*- coding: utf-8 -*-
#
# clx.py - Ethernet/IP Client for Rockwell PLCs
#
#
# Copyright (c) 2014 Agostino Ruscito <ruscito@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
from pycomm.cip.cip_base import *
from pycomm.common import setup_logger
import re
import logging


def parse_tag(tag):
    t = re.search(r"(?P<file_type>[SBCTRNFAIO])(?P<file_number>\d{1,3})"
                  r"(:)(?P<element_number>\d{1,3})"
                  r"(/(?P<sub_element>\d{1,4}))?", tag, flags=re.IGNORECASE)
    if t:
        if t.group('sub_element') is not None:
            address_field = 3
        else:
            address_field = 2
        return True, t.group(0), {'file_type': t.group('file_type'),
                                  'file_number': t.group('file_number'),
                                  'element_number': t.group('element_number'),
                                  'sub_element': t.group('sub_element'),
                                  'address_field': address_field}

    t = re.search(r"(?P<file_type>[BN])(?P<file_number>\d{1,3})"
                  r"(/)(?P<sub_element>\d{1,4})",  tag, flags=re.IGNORECASE)
    if t:
        return True, t.group(0), {'file_type': t.group('file_type'),
                                  'file_number': t.group('file_number'),
                                  'sub_element': t.group('sub_element'),
                                  'address_field': 2}

    t = re.search(r"(?P<file_type>[CT])(?P<file_number>\d{1,3})"
                  r"(:)(?P<element_number>\d{1,3})"
                  r"(.)(?P<sub_element>)(ACC|PRE|EN|DN|TT|CU|CD|DN|OV|UN|UA)", tag, flags=re.IGNORECASE)
    if t:
        return True, t.group(0), {'file_type': t.group('file_type'),
                                  'file_number': t.group('file_number'),
                                  'element_number': t.group('element_number'),
                                  'sub_element': t.group('sub_element'),
                                  'address_field': 3}

    t = re.search(r"(?P<file_type>[IOS])(:)(?P<element_number>\d{1,3})"
                  r"(/)(?P<sub_element>\d{1,4})", tag, flags=re.IGNORECASE)
    if t:
        return True, t.group(0), {'file_type': t.group('file_type'),
                                  'element_number': t.group('element_number'),
                                  'sub_element': t.group('sub_element'),
                                  'address_field': 2}

    t = re.search(r"(?P<file_type>[IOS])(:)(?P<element_number>\d{1,3})"
                  r"(.)(?P<sub_element>[0-7])", tag, flags=re.IGNORECASE)
    if t:
        return True, t.group(0), {'file_type': t.group('file_type'),
                                  'element_number': t.group('element_number'),
                                  'sub_element': t.group('sub_element'),
                                  'address_field': 2}

    t = re.search(r"(?P<file_type>[IOS])(:)(?P<element_number>\d{1,3})"
                  r"(/)(?P<sub_element>\d{1,4})", tag, flags=re.IGNORECASE)
    if t:
        return True, t.group(0), {'file_type': t.group('file_type'),
                                  'element_number': t.group('element_number'),
                                  'sub_element': t.group('sub_element'),
                                  'address_field': 2}

    """
    t = re.search(r"(?P<file_type>[IOS])(:)(?P<element_number>\d{1,3})", tag, flags=re.IGNORECASE)
    if t:
        return True, t.group(0), {'file_type': t.group('file_type'),'element_number': t.group('element_number')}
    """
    return False, tag


class Driver(Base):
    """
    SLC/PLC_5 Implementation
    """
    def __init__(self, debug=False, filename=None):
        if debug:
            super(Driver, self).__init__(setup_logger('ab_comm.slc', logging.DEBUG, filename))
        else:
            super(Driver, self).__init__(setup_logger('ab_comm.slc', logging.INFO, filename))

        self.__version__ = '0.1'

    def _check_reply(self):
        """
        check the replayed message for error
        """
        self._more_packets_available = False
        try:
            if self._reply is None:
                self._status = (3, '%s without reply' % REPLAY_INFO[unpack_dint(self._message[:2])])
                return False
            # Get the type of command
            typ = unpack_uint(self._reply[:2])

            # Encapsulation status check
            if unpack_dint(self._reply[8:12]) != SUCCESS:
                self._status = (3, "{0} reply status:{1}".format(REPLAY_INFO[typ],
                                                                 SERVICE_STATUS[unpack_dint(self._reply[8:12])]))
                return False

            # Command Specific Status check
            if typ == unpack_uint(ENCAPSULATION_COMMAND["send_rr_data"]):
                status = unpack_sint(self._reply[42:43])
                if status != SUCCESS:
                    self._status = (3, "send_rr_data reply:{0} - Extend status:{1}".format(
                        SERVICE_STATUS[status], get_extended_status(self._reply, 42)))
                    return False
                else:
                    return True

            elif typ == unpack_uint(ENCAPSULATION_COMMAND["send_unit_data"]):
                status = unpack_sint(self._reply[48:49])
                if unpack_sint(self._reply[46:47]) == I_TAG_SERVICES_REPLY["Read Tag Fragmented"]:
                    self._parse_fragment(50, status)
                    return True
                if unpack_sint(self._reply[46:47]) == I_TAG_SERVICES_REPLY["Get Instance Attributes List"]:
                    self._parse_tag_list(50, status)
                    return True
                if status == 0x06:
                    self._status = (3, "Insufficient Packet Space")
                    self._more_packets_available = True
                elif status != SUCCESS:
                    self._status = (3, "send_unit_data reply:{0} - Extend status:{1}".format(
                        SERVICE_STATUS[status], get_extended_status(self._reply, 48)))
                    return False
                else:
                    return True

        except LookupError:
            self._status = (3, "LookupError inside _check_replay")
            return False

        return True

    def read_tag(self, tag, n):
        res = parse_tag(tag)
        if res[0]:
            print ('good')
            print res[2]['file_type']
        else:
            print ('bad')
        if self._session == 0:
            self._status = (6, "A session need to be registered before to call read_tag.")
            self.logger.warning(self._status)
            return None

        if not self._target_is_connected:
            if not self.forward_open():
                self._status = (5, "Target did not connected. read_tag will not be executed.")
                self.logger.warning(self._status)
                return None

        # Creating the Message Request Packet
        seq = pack_uint(Base._get_sequence())
        message_request = [
            seq,
            '\x4b',
            '\x02',
            CLASS_ID["8-bit"],
            PATH["PCCC"],
            '\x07',
            self.attribs['vid'],
            self.attribs['vsn'],
            '\x0f',
            '\x00',
            seq[1],
            seq[0],
            '\xa2',
            pack_sint(PCCC_DATA_SIZE[res[2]['file_type']]*n),
            pack_sint(int(res[2]['file_number'])),
            PCCC_DATA_TYPE[res[2]['file_type']],
            pack_sint(int(res[2]['element_number'])),
        ]
        subelement_number = '\x00'
        if res[2]['bit_number'] is not None:
            subelement_number = pack_sint(int(res[2]['bit_number']))

        message_request.append(subelement_number)

        if self.send_unit_data(
            build_common_packet_format(
                DATA_ITEM['Connected'],
                ''.join(message_request),
                ADDRESS_ITEM['Connection Based'],
                addr_data=self._target_cid,)):

            return unpack_real(self._reply[61:])

        else:
            return None

    def write_tag(self, tag, value):
        if self._session == 0:
            self._status = (8, "A session need to be registered before to call write_tag.")
            self.logger.warning(self._status)
            return None

        if not self._target_is_connected:
            if not self.forward_open():
                self._status = (8, "Target did not connected. write_tag will not be executed.")
                self.logger.warning(self._status)
                return None

        # Creating the Message Request Packet
        seq = pack_uint(Base._get_sequence())
        message_request = [
            seq,
            '\x4b',
            '\x02',
            CLASS_ID["8-bit"],
            PATH["PCCC"],
            '\x07',
            self.attribs['vid'],
            self.attribs['vsn'],
            '\x0f',
            '\x00',
            seq[1],
            seq[0],
            '\xaa',
            '\x06',  # pack_sint(n),  # \x02
            '\x07',
            '\x89',
            '\x00\x00',
            pack_uint(3),
            pack_uint(3),
            pack_uint(3),
            ]

        ret_val = self.send_unit_data(
            build_common_packet_format(
                DATA_ITEM['Connected'],
                ''.join(message_request),
                ADDRESS_ITEM['Connection Based'],
                addr_data=self._target_cid,
            )
        )

        return ret_val