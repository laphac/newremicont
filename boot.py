# main.py
import network
import socket
import time
from webserver import handle_request
from air_pressure_controller import run_automatic_control

# Wi-Fi AP
ap = network.WLAN(network.AP_IF)
ap.config(essid='ADS1115_Sensor', password='12345678', authmode=3)
ap.active(True)
while not ap.active():
    time.sleep(0.1)
print("AP запущена. IP:", ap.ifconfig()[0])

# HTTP-сервер (неблокирующий)
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 80))
s.listen(5)
s.settimeout(1.0)  # неблокирующий режим

print("Веб-сервер и регулятор запущены")

last_log = 0
while True:
    # Обработка HTTP-запросов
    try:
        conn, addr = s.accept()
        handle_request(conn)
    except OSError:
        pass  # таймаут
    except Exception as e:
        print("HTTP error:", e)

    # Автоматическое управление
    result = run_automatic_control()
    if result and time.time() - last_log > 10:
        print("[AUTO CTRL]", result)
        last_log = time.time()

    time.sleep_ms(50)