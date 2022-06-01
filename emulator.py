#!/usr/bin/env python3

# References:
# https://en.wikipedia.org/wiki/CHIP-8
# http://devernay.free.fr/hacks/chip8/C8TECH10.HTM#0.1
# https://storage.googleapis.com/wzukusers/user-34724694/documents/9265a537ce884412b347ffb476a0f929/CHIP-8%20Classic%20Manual%20Rev%201.7.pdf
# https://pyglet.readthedocs.io/en/latest/
# https://chip-8.github.io/links/
# https://www.zophar.net/pdroms/chip8/chip-8-games-pack.html for the ROMs

import random
import pyglet
import sys

KEY_MAP = {pyglet.window.key._1: 0x1,
           pyglet.window.key._2: 0x2,
           pyglet.window.key._3: 0x3,
           pyglet.window.key._4: 0xc,
           pyglet.window.key.Q: 0x4,
           pyglet.window.key.W: 0x5,
           pyglet.window.key.E: 0x6,
           pyglet.window.key.R: 0xd,
           pyglet.window.key.A: 0x7,
           pyglet.window.key.S: 0x8,
           pyglet.window.key.D: 0x9,
           pyglet.window.key.F: 0xe,
           pyglet.window.key.Z: 0xa,
           pyglet.window.key.X: 0x0,
           pyglet.window.key.C: 0xb,
           pyglet.window.key.V: 0xf
          }


FONTS = [0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
         0x20, 0x60, 0x20, 0x20, 0x70, # 1
         0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
         0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
         0x90, 0x90, 0xF0, 0x10, 0x10, # 4
         0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
         0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
         0xF0, 0x10, 0x20, 0x40, 0x40, # 7
         0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
         0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
         0xF0, 0x90, 0xF0, 0x90, 0x90, # A
         0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
         0xF0, 0x80, 0x80, 0x80, 0xF0, # C
         0xE0, 0x90, 0x90, 0x90, 0xE0, # D
         0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
         0xF0, 0x80, 0xF0, 0x80, 0x80  # F
         ]

class Logger:
    def __init__(self, should_log = True):
        self.should_log = should_log 

    def info(self, string):
        if(self.should_log):
            print(f"[INFO] {string}")

    def warn(self, string):
        if(self.should_log):
            print(f"[WARN] {string}")

    def error(self, string):
        if(self.should_log):
            print(f"[ERROR] {string}")

class Emulator():
    window = None
    
    def __init__(self, window_width, window_height):
        self.window = pyglet.window.Window(window_width, window_height)

    program_counter = 0
    keys = []
    memory = []
    registers = []
    display_buffer = []
    stack = []
    inputs = [0] * 16
    operation_code = 0
    index = 0
    delay_timer = 0
    sound_timer = 0
    should_draw = False
    running = False
    key_wait = False
    logger = Logger
    vx = 0
    vy = 0
    sprites = []
    function_map = None
    batch = None

    pixel = pyglet.resource.image('pixel.png')

    # Operation functions
    def _0000(self):
        extracted_operation = self.operation_code & 0xF0FF
        try:
            self.function_map[extracted_operation]()
        except:
            self.logger.warn(f"Uknown instruction: {self.operation_code}")

    def _8XXX(self):
        extracted_operation = self.operation_code & 0xF00F
        extracted_operation += 0xFF0
        try:
            self.function_map[extracted_operation]()
        except:
            self.logger.warn(f"Uknown instruction: {self.operation_code}")

    def _9XXX(self):
        if self.registers[self.vx] != self.registers[self.vy]:
            self.program_counter += 2

    def _00E0(self):
        self.logger.info("Cleared screen")
        self.display_buffer = [0] * 64 * 32 # Resetting the display
        self.should_draw = True

    def _00EE(self):
        self.logger.info("Returned from subroutine")
        self.program_counter = self.stack.pop()

    def _1NNN(self):
        self.logger.info("Setting address to NNN")
        self.program_counter = self.operation_code & 0x0FFF

    def _2NNN(self):
        self.stack.append(self.program_counter)
        self.program_counter = self.operation_code & 0x0FFF

    def _3XKK(self):
        if self.registers[self.vx] == self.operation_code & 0x00FF:
            self.program_counter += 2

    def _4XKK(self):
        if self.registers[self.vx] != self.operation_code & 0x00FF:
            self.program_counter += 2

    def _5XY0(self):
        if self.registers[self.vx] == self.registers[self.vy]:
            self.program_counter += 2

    def _6XKK(self):
        self.logger.info("Setting Vx to KK")
        self.registers[self.vx] = self.operation_code & 0x00FF

    def _7XKK(self):
        self.registers[self.vx] += self.operation_code & 0xFF

    def _8XY0(self):
        self.registers[self.vx] = self.registers[self.vy]
        self.registers[self.vx] &= 0xFF

    def _8XY1(self):
        self.registers[self.vx] |= self.registers[self.vy]
        self.registers[self.vx] &= 0xFF

    def _8XY2(self):
        self.registers[self.vx] &= self.registers[self.vy]
        self.registers[self.vx] &= 0xFF

    def _8XY3(self):
        self.registers[self.vx] ^= self.registers[self.vy]
        self.registers[self.vx] &= 0xFF

    def _8XY4(self):
        if self.registers[self.vx] + self.registers[self.vy] > 0xFF:
            self.registers[0xF] = 1
        else:
            self.registers[0xF] = 0

        self.registers[self.vx] += self.registers[self.vy]
        self.registers[self.vx] &= 0xFF

    def _8XY5(self):
        if self.registers[self.vx] > self.registers[self.vy]:
            self.registers[0xF] = 1
        else:
            self.registers[0xF] = 0

        self.registers[self.vx] -= self.registers[self.vy]
        self.registers[self.vx] &= 0xFF

    def _8XY6(self):
        self.registers[0xF] = self.registers[self.vx] & 0x0001
        self.registers[self.vx] = self.registers[self.vx] >> 1

    def _8XY7(self):
        if self.registers[self.vy] > self.registers[self.vx]:
            self.registers[0xF] = 1
        else:
            self.registers[0xF] = 0

        self.registers[self.vx] = self.registers[self.vy] - self.registers[self.vx]
        self.registers[self.vx] &= 0xFF
    
    def _8XYE(self):
        self.registers[0xF] = (self.registers[self.vx] & 0x00F0) >> 7
        self.registers[self.vx] = self.registers[self.vx] << 1
        self.registers[self.vx] &= 0xFF

    def _9XY0(self):
        if self.registers[self.vx] != self.registers[self.vy]:
            self.program_counter += 2

    def _ANNN(self):
        self.index = self.operation_code & 0x0FFF

    def _BNNN(self):
        self.program_counter = (self.operation_code & 0x0FFF) + self.registers[0]

    def _CXKK(self):
        random_number = random.randint(0, 0xFF)
        self.registers[self.vx] = random_number & (self.operation_code & 0x00FF)
        self.registers[self.vx] &= 0xFF

    def _DXYN(self):
        self.logger.info("Drawing a sprite")
        self.registers[0xF] = 0
        x = self.registers[self.vx] & 0xFF
        y = self.registers[self.vy] & 0xFF
        height = self.operation_code & 0x000F
        row = 0

        while row < height:
            current_row = self.memory[row + self.index]
            pixel_offset = 0
            while pixel_offset < 8:
                location = x + pixel_offset + ((y + row) * 64)
                pixel_offset += 1
                if(y + row) >= 32 or (x + pixel_offset - 1) >= 64:
                    # bitmask = 1 << 8 - pixel_offset
                    # current_pixel = (current_row & bitmask) >> (8 - pixel_offset)
                    # self.display_buffer[location] ^= current_pixel
                    continue
                bitmask = 1 << 8 - pixel_offset
                current_pixel = (current_row & bitmask) >> (8 - pixel_offset)
                self.display_buffer[location] ^= current_pixel    
                
                if self.display_buffer[location] == 0:
                    self.registers[0xF] = 1
                else:
                    self.registers[0xF] = 0

            row += 1
        self.should_draw = True

    def _EXXX(self):
        extracted_operation = self.operation_code & 0xF00F
        try:
            self.function_map[extracted_operation]()
        except:
            self.logger.warn(f"Uknown instruction: {self.operation_code}")

    def _EX9E(self):
        key_pressed = self.registers[self.vx] & 0xF
        if self.keys[key_pressed] == 1:
            self.program_counter += 2

    def _EXA1(self):
        key_pressed = self.registers[self.vx] & 0xF
        if self.keys[key_pressed] == 0:
            self.program_counter += 2
    
    def _FXXX(self):
        extracted_operation = self.operation_code & 0xF0FF
        try:
            self.function_map[extracted_operation]()
        except:
            self.logger.warn(f"Uknown instruction: {self.operation_code}")

    def _FX07(self):
        self.registers[self.vx] = self.delay_timer

    def _FX0A(self):
        key_pressed = self.get_key()
        if key_pressed >= 0:
            self.registers[self.vx] = key_pressed
        else:
            self.program_counter -= 2

    def _FX15(self):
        self.delay_timer = self.registers[self.vx]

    def _FX18(self):
        self.sound_timer = self.registers[self.vx]

    def _FX1E(self):
        self.index += self.registers[self.vx]
        if self.index > 0xFFF:
            self.registers[0xF] = 1
            self.index &= 0xFFF
        else:
            self.registers[0xF] = 0

    def _FX29(self):
        self.index = (5 * (self.registers[self.vx])) & 0xFFF

    def _FX33(self):
        self.memory[self.index] = self.registers[self.vx] / 100
        self.memory[self.index + 1] = (self.registers[self.vx] % 100) / 10
        self.memory[self.index + 2] = self.registers[self.vx] % 10

    def _FX55(self):
        i = 0
        while i <= self.vx:
            self.memory[self.index + i] = self.registers[i]
            i += 1

        self.index += self.vx + 1


    def _FX65(self):
        i = 0
        while i <= self.vx:
            self.registers[i] = self.memory[self.index + i]
            i += 1

        self.index += self.vx + 1

    def init(self):
        self.window.clear()

        # The program counter which will be used
        # to execute instructions from memory.
        # We're offsetting the program counter 
        # by 512 bytes because the first 512
        # bytes are where the original interpreter
        # was located 
        self.program_counter = 0x200 # 512 in decimal

        # Memory or RAM of 4096 bytes or 4 kilobytes.
        # Everything in memory will be represented by
        # a hexadecimal number since each instruction
        # will be 8 bits (8 bits * 4096)
        self.memory = [0] * 4096

        # 16 16-bit registers
        self.registers = [0] * 16

        # 64 x 32 display
        self.display_buffer = [0] * 64 * 32

        # The stack
        self.stack = []

        # Keys
        self.keys = [0] * 16

        # 16 key inputs
        self.inputs = [0] * 16

        # Operation code
        self.operation_code = 0

        # Register index
        self.index = 0

        # A delay timer
        self.delay_timer = 0

        # Sound timer
        self.sound_timer = 0

        # Drawing
        self.should_draw = 0

        # Logging messages
        self.logger = Logger(False)

        # State of the emulator
        self.running = True

        # 2 general registers
        self.vx = 0
        self.vy = 0

        self.batch = pyglet.graphics.Batch()

        for i in range(0, 2048):
            self.sprites.append(pyglet.sprite.Sprite(self.pixel, batch = self.batch))

        for i in range(0, 80):
            self.memory[i] = FONTS[i]
            
        self.function_map = {
                    0x0000: self._0000,
                    0x00e0: self._00E0,
                    0x00ee: self._00EE,
                    0x1000: self._1NNN,
                    0x2000: self._2NNN,
                    0x3000: self._3XKK,
                    0x4000: self._4XKK,
                    0x5000: self._5XY0,
                    0x6000: self._6XKK,
                    0x7000: self._7XKK,
                    0x8000: self._8XXX,
                    0x8FF0: self._8XY0,
                    0x8FF1: self._8XY1,
                    0x8FF2: self._8XY2,
                    0x8FF3: self._8XY3,
                    0x8FF4: self._8XY4,
                    0x8FF5: self._8XY5,
                    0x8FF6: self._8XY6,
                    0x8FF7: self._8XY7,
                    0x8FFE: self._8XYE,
                    0x9000: self._9XXX,
                    0xA000: self._ANNN,
                    0xB000: self._BNNN,
                    0xC000: self._CXKK,
                    0xD000: self._DXYN,
                    0xE000: self._EXXX,
                    0xE00E: self._EX9E,
                    0xE001: self._EXA1,
                    0xF000: self._FXXX,
                    0xF007: self._FX07,
                    0xF00A: self._FX0A,
                    0xF015: self._FX15,
                    0xF018: self._FX18,
                    0xF01E: self._FX1E,
                    0xF029: self._FX29,
                    0xF033: self._FX33,
                    0xF055: self._FX55,
                    0xF065: self._FX65
                    }

        
        self.window.push_handlers(self.on_key_press)
        self.window.push_handlers(self.on_key_release)
        self.window.push_handlers(self.on_close)

    def load(self, rom_path):
        self.logger.info(f"Loading {rom_path}")
        chip_8_binary_file = open(rom_path, "rb") # for reading binary files
        chip_8_binary_data = chip_8_binary_file.read()
        for i in range(len(chip_8_binary_data)):
            self.memory[i + 0x200] = chip_8_binary_data[i]

    def render(self):
        if self.should_draw:
            for i in range(0, 2048):
                if self.display_buffer[i] == 1:
                    self.sprites[i].x = (i % 64) * 10
                    self.sprites[i].y = 310 - ((i / 64) * 10)
                    self.sprites[i].batch = self.batch

                else:
                    self.sprites[i].batch = None

            self.window.clear()
            self.batch.draw()
            self.window.flip()
            self.should_draw = False

    def cycle(self):
        self.operation_code = (self.memory[self.program_counter] << 8) | self.memory[self.program_counter + 1]
        self.logger.info(f"operation code: {self.operation_code}")

        self.program_counter += 2
        self.vx = (self.operation_code & 0x0F00) >> 8
        self.vy = (self.operation_code & 0x00F0) >> 4

        extracted_operation = self.operation_code & 0xF000

        try:
            self.function_map[extracted_operation]()
        except:
            self.logger.warn(f"Uknown instruction {self.operation_code}")

        if self.delay_timer > 0:
            self.delay_timer -= 1
        
        if self.sound_timer > 0:
            self.sound_timer -= 1
            
            if self.sound_timer == 0:
                pass

    def on_key_press(self, key, mod):
        self.logger.info(f"{key} pressed")
        if key in KEY_MAP.keys():
            self.keys[KEY_MAP[key]] = 1
            if self.key_wait:
                self.key_wait = False

        elif key == pyglet.window.key.ESCAPE:
            self.close()

    def on_key_release(self, key, mod):
        self.logger.info(f"{key} pressed")
        if key in KEY_MAP.keys():
            self.keys[KEY_MAP[key]] = 0

    def on_close(self):
        self.running = False


    def get_key(self):
        for i in range(0, 16):
            if self.keys[i] == 1:
                return i
        return -1

    def main_loop(self):
        self.init()
        self.load(sys.argv[1])
        while(self.running):
            self.window.dispatch_events()
            self.cycle()
            self.render()

if __name__ == "__main__":
    emulator = Emulator(640, 320)
    emulator.main_loop()