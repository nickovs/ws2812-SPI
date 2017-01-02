# ws2812-SPI
An efficient micropython WS2812 (NeoPixel) driver

This library allows for easy access to a set of WS2812 RGB LEDs
attached to a microcontroller running
[MicroPython](https://micropython.org) using an SPI port. This (at
least in theory) allows for more efficient and reliable delivery of
the data compared to using "bit banging" of a regular IO line.

The NeoPixel object can be treated as a 2D array, `pixel_count` long
and 3 wide. Pixels can be accessed as a 3-tuple or through their
individual Green, Blue and Red components (in that order). It can also
be accessed with 1D slice operations to read or write a list of
3-tuples and a single 3-tuple can be written to a whole slice to set a
row of pixels to the same value.

```python
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
```

