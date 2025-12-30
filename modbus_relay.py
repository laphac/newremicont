# modbus_relay.py
from machine import UART, Pin
import time

uart = UART(1, baudrate=9600, tx=Pin(0), rx=Pin(1), bits=8, parity=None, stop=1)

def modbus_crc(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

def set_relay(channel, state):
    if not (1 <= channel <= 4):
        return False
    device_id = 0x02
    function = 0x05
    coil_address = channel - 1
    value = 0xFF00 if state else 0x0000

    data = bytearray([device_id, function])
    data.extend(coil_address.to_bytes(2, 'big'))
    data.extend(value.to_bytes(2, 'big'))
    crc = modbus_crc(data)
    data.extend(crc.to_bytes(2, 'little'))

    uart.write(data)
    time.sleep_ms(50)
    return True