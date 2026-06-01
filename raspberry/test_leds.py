import board
import neopixel

pixels = neopixel.NeoPixel(
    board.D18,
    160,
    brightness=1.0,
    auto_write=False
)

pixels.fill((255, 0, 0))
pixels.show()
