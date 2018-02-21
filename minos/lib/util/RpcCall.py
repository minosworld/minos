import numpy as np


class RpcCall:
    """ Super basic RPC Call """
    def __init__(self, sio, rpcid, logger):
        self.sio = sio
        self.id = rpcid
        self.logger = logger
        self.name = None
        self.response = None
        self.result = None
        self.callback = None

    def call(self, name, data=None, callback=None, seconds=None, check_wait=None):
        self.name = name
        self.callback = callback
        #self.logger.info('Call %s emit' % name)
        self.sio.emit(name, data, self._handle_response)
        #self.logger.info('Call %s waiting...' % name)
        if check_wait is not None and seconds is not None:
            # loop and wait until check is true or response is received
            #self.logger.info('Call %s checked waiting %d ...' % (name, seconds))
            while self.response is None and check_wait() and self.sio.connected:
                self.sio.wait_for_callbacks(seconds=seconds)    # wait for response
        else:
            #self.logger.info('Call %s waiting %d ...' % (name, seconds))
            self.sio.wait_for_callbacks(seconds=seconds)    # wait for response

        #self.logger.info('Call %s done' % name)
        return self.result

    def _parse_array(self, array):
        # TODO: Handle endianness correctly
        datatype = array.get('datatype')
        data = array.get('data')
        if datatype == 'int8':
            dt = np.dtype('i1')
            return np.frombuffer(data, dtype=dt)
        elif datatype == 'uint8':
            dt = np.dtype('u1')
            return np.frombuffer(data, dtype=dt)
        elif datatype == 'int16':
            dt = np.dtype('i2')
            return np.frombuffer(data, dtype=dt)
        elif datatype == 'uint16':
            dt = np.dtype('u2')
            return np.frombuffer(data, dtype=dt)
        elif datatype == 'int32':
            dt = np.dtype('i4')
            return np.frombuffer(data, dtype=dt)
        elif datatype == 'uint32':
            dt = np.dtype('u4')
            return np.frombuffer(data, dtype=dt)
        elif datatype == 'float32':
            dt = np.dtype('f4')
            return np.frombuffer(data, dtype=dt)
        elif datatype == 'float64':
            dt = np.dtype('f8')
            return np.frombuffer(data, dtype=dt)
        else:
            if self.logger:
                self.logger.error('Unknown datatype %s when processing %s' % (datatype, self.name))
            return array

    def _parse_data(self, value, key=None, parent=None, path=[]):
        #if len(path) > 0:
        #    ('parse_data %s' % path)
        if type(value) is dict:
            if value.get('type') == 'array' and 'datatype' in value:
                # Special array buffer - let's process it!
                value = self._parse_array(value)
                if parent is not None:
                    parent[key] = value
            else:
                for k, v in value.items():
                    if type(v) is dict or type(v) is list:
                        self._parse_data(v, key=k, parent=value, path=path + [k])
        elif type(value) is list and len(value) > 0:
            for k, v in enumerate(value):
                if type(v) is dict or type(v) is list:
                    self._parse_data(v, key=k, parent=value, path=path + [k])
        return value

    def _handle_response(self, data):
        # process things that proclaim themselves to be array with data
        self.response = self._parse_data(data)
        if self.logger:
            if self.response is not None and self.response.get('status') == 'error':
                self.logger.error('Error calling %s: %s' % (self.name, self.response.get('message')))
        if self.callback is not None:
            self.result = self.callback(self.response)
        else:
            self.result = self.response
