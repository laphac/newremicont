# ads1115.py
from machine import I2C, Pin
import time

ADDR1 = 0x48  # ADDR → GND
ADDR2 = 0x49  # ADDR → VCC

REG_CONFIG = 0x01
REG_CONVERSION = 0x00

BASE_CONFIG = (1 << 15) | (1 << 8) | (7 << 5) | 3
CONFIG_A0_A1 = BASE_CONFIG | (0 << 12)
CONFIG_A2_A3 = BASE_CONFIG | (3 << 12)

SCALE_VOLT = 6.144 / 32768.0

i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)

def write_config(addr, config):
    buf = bytearray([REG_CONFIG, (config >> 8) & 0xFF, config & 0xFF])
    i2c.writeto(addr, buf)

def read_voltage(addr):
    buf = bytearray(2)
    i2c.readfrom_mem_into(addr, REG_CONVERSION, buf)
    raw = (buf[0] << 8) | buf[1]
    if raw & 0x8000:
        raw -= 65536
    return raw * SCALE_VOLT

def read_all_channels():
    write_config(ADDR1, CONFIG_A0_A1); time.sleep_ms(2)
    v1_01 = read_voltage(ADDR1)
    write_config(ADDR1, CONFIG_A2_A3); time.sleep_ms(2)
    v1_23 = read_voltage(ADDR1)
    write_config(ADDR2, CONFIG_A0_A1); time.sleep_ms(2)
    v2_01 = read_voltage(ADDR2)
    write_config(ADDR2, CONFIG_A2_A3); time.sleep_ms(2)
    v2_23 = read_voltage(ADDR2)
    return [v1_01, v1_23, v2_01, v2_23]