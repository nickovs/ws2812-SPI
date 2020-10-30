# Implement the neopixel protocol on an SPI bus

# The data is stored expanded into the format that will be sent
# directly to the SPI bus. This is efficient if there are realtively
# few changes to the buffer between refreshes but can be slower if you
# are likely to change each pixel more than once between refreshes.

import gc

# User bytes are spread across four buffer bytes, encoded into bits 6
# and 2 of each byte with the top bits of each nibble set and the
# bottom bits of each nibble all clear.

# 0b00011011 -> 0b10001000 0b10001100 0b11001000 0b11001100

_expanded_bits = [0x88, 0x8C, 0xC8, 0xCC]

def _expand_byte(b, mv):
    # Spread a byte across four bytes of a memoryview
    mv[0] = _expanded_bits[(b >> 6) & 0x3]
    mv[1] = _expanded_bits[(b >> 4) & 0x3]
    mv[2] = _expanded_bits[(b >> 2) & 0x3]
    mv[3] = _expanded_bits[(b) & 0x3]

def _compress_byte(mv):
    # Pack four bytes in a memoryview into a single byte
    b1, b2, b3, b4 = mv
    T, B = 0x40, 0x04
    v = (((b1 & T) << 1) | ((b1 & B) << 4) |
         ((b2 & T) >> 1) | ((b2 & B) << 2) |
         ((b3 & T) >> 3) | ((b3 & B)     ) |
         ((b4 & T) >> 5) | ((b4 & B) >> 2) )
    return v

class NeoPixel:
    """The NeoPixel object can be treated as a 2D array, pixel_count long and 3
    wide. Pixels can be accessed as a 3-tuple or through their individual Green,
    Blue and Red components (in that order). It can also be accessed with 1D
    slice operations to read or write a list of 3-tuples and a single
    3-tuple can be written to a whole slice to set a row of pixels to the same
    value.

    sp = machine.SPI(1)
    sp.init(baudrate=3200000)
    np = NeoPixel(sp, 100)

    # Blank the whole set
    np[:] = (0,0,0)
    # Set the first 10 pixels to dark blue
    np[0:10] = (0,0,40)
    # Set the second pixel to green
    np[1] = (128,0,0)
    # Set the third pixel's red value to full brightness
    np[2,2] = 255
    # Copy the 2nd pixel to the 5th
    np[4] = np[1]
    # Copy the first 16 pixels to the last 16 pixels
    np[-16:] = np[:16]
    """

    
    def __init__(self, spi_device, pixel_count):
        self._n = pixel_count
        self._data = memoryview(bytearray(pixel_count * 12))
        self._spi = spi_device
        self[:] = (0,0,0)

    def _unpack_slice(self, s):
        start, stop, step = s.start, s.stop, s.step
        if step is not None and step != 1:
            raise NotImplementedError("Slices must have step of 1")
        step = 1
        if start == None:
            start = 0
        elif start < 0:
            start += self._n
        if stop == None:
            stop = self._n
        elif stop < 0:
            stop += self._n
        return (start, stop, step)
            
    def __getitem__(self, index):
        data = self._data
        n = self._n
        if isinstance(index, int):
            if index < -n or index >= n:
                raise IndexError("Pixel index out of range")
            index *= 12
            return (_compress_byte(data[index:index+4]),
                    _compress_byte(data[index+4:index+8]),
                    _compress_byte(data[index+8:index+12]))
        elif isinstance(index, tuple):
            if len(index) != 2:
                raise IndexError("Pixel array has only two dimensions (index and colour)")
            ind1, ind2 = index
            if isinstance(ind1, slice):
                raise NotImplementedError("2D slicing not supported")
            if (not isinstance(ind1, int)) or (not isinstance(ind2, int)):
                raise IndexError("Indecies must be integers")
            if ind1 < -n or ind1 >= n or ind2 < 0 or ind2 >= 3:
                raise IndexError("Pixel index out of range")
            ind1 *= 12
            ind1 += ind2 * 4
            return _compress_byte(data[ind1:ind1+4])
        elif isinstance(index, slice):
            start, stop, step = self._unpack_slice(index)
            dd = data[start*12:stop*12]
            return [(_compress_byte(dd[i:i+4]),
                     _compress_byte(dd[i+4:i+8]),
                     _compress_byte(dd[i+8:i+12])) for i in range(0, len(dd), 12)]
        else:
            raise IndexError("Can not index on type {}".format(type(index)))

    def __setitem__(self, index, value):
        data = self._data
        n = self._n
        if isinstance(index, int):
            if index < -n or index >= n:
                raise IndexError("Pixel index out of range")
            if not isinstance(value, tuple) or len(value) != 3:
                raise ValueError("Pixel value must be a 3-tuple")
            index *= 12
            _expand_byte(value[0], data[index  :index+ 4])
            _expand_byte(value[1], data[index+4:index+ 8])
            _expand_byte(value[2], data[index+8:index+12])
        elif isinstance(index, tuple):
            if len(index) != 2:
                raise IndexError("Pixel array has only two dimensions (index and colour)")
            ind1, ind2 = index
            if isinstance(ind1, slice):
                raise NotImplementedError("2D slice assignment not supported")
            if (not isinstance(ind1, int)) or (not isinstance(ind2, int)):
                raise IndexError("Indecies must be integers")
            if ind1 < -n or ind1 >= n or ind2 < 0 or ind2 >= 3:
                raise IndexError("Pixel index out of range")
            if not isinstance(value, int) or value<0 or value>255:
                raise ValueError("Pixel value must be an integer in range 0 to 255")
            ind1 *= 12
            ind1 += ind2 * 4
            _expand_byte(value, data[ind1:ind1+4])
        elif isinstance(index, slice):
            start, stop, step = self._unpack_slice(index)
            dd = memoryview(data)[start*12:stop*12]
            if len(dd) == 0:
                return
            if isinstance(value, tuple) and len(value) == 3:
                _expand_byte(value[0], dd[0: 4])
                _expand_byte(value[1], dd[4: 8])
                _expand_byte(value[2], dd[8:12])
                for i in range(12, len(dd), 12):
                    dd[i:i+12] = dd[0:12]
            elif isinstance(value, list) and all((isinstance(i, tuple) and len(i) == 3) for i in value):
                for i in range(0, len(dd), 12):
                    v0, v1, v2 = value[i//3]
                    _expand_byte(v0, dd[i+0:i +4])
                    _expand_byte(v1, dd[i+4:i +8])
                    _expand_byte(v2, dd[i+8:i+12])
            else:
                raise ValueError("Assigned value must be a list of 3-tuples or a single 3-tuple")

    def write(self):
        """Write the buffer value out to the pixels"""
        self._spi.write(self._data)

    def rotate(self, count):
        """Rotate the whole buffer content by 'count' pixels"""
        count = count % self._n
        count *= 12
        tail = bytearray(self._data[-count:])
        head = bytearray(self._data[:-count])
        self._data[count:] = head
        self._data[:count] = tail
        del head, tail
        gc.collect()

    @property
    def n(self):
        return self._n
