# air_pressure_controller.py
import time
from ads1115 import read_all_channels
from modbus_relay import set_relay
from config_manager import load_config

# Глобальные переменные ПИД
_last_control_time = 0
_integral = 0.0
_last_error = 0.0

def apply_calibration(raw_voltages, config):
    """
    Применяет калибровку ко всем 4 каналам.
    Возвращает словарь с физическими значениями.
    """
    def v2y(v, key):
        ch = config[key]
        vmin, vmax = ch["v_min"], ch["v_max"]
        ymin, ymax = ch["y_min"], ch["y_max"]
        if vmax == vmin:
            return ymin
        return (ymax - ymin) / (vmax - vmin) * (v - vmin) + ymin

    return {
        "o2_1": v2y(raw_voltages[0], "ch0"),
        "o2_2": v2y(raw_voltages[1], "ch1"),
        "gas_flow": v2y(raw_voltages[2], "ch2"),
        "air_pressure": v2y(raw_voltages[3], "ch3"),
        "o2_avg": (v2y(raw_voltages[0], "ch0") + v2y(raw_voltages[1], "ch1")) / 2.0
    }

def linear_interpolate(x, table):
    """Интерполяция по таблице: список словарей с 'gas' и 'air_target'"""
    if not table:
        return 0.0
    if x <= table[0]["gas"]:
        return table[0]["air_target"]
    if x >= table[-1]["gas"]:
        return table[-1]["air_target"]
    for i in range(len(table) - 1):
        x0, y0 = table[i]["gas"], table[i]["air_target"]
        x1, y1 = table[i+1]["gas"], table[i+1]["air_target"]
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1]["air_target"]

def run_automatic_control():
    global _last_control_time, _integral, _last_error
    cfg = load_config()
    pid = cfg.get("pid_control", {})
    
    if not pid.get("enabled", False):
        return {"status": "disabled"}

    now = time.time()
    interval = pid.get("control_interval", 10)
    if now - _last_control_time < interval:
        return None

    # === ЧИТАЕМ СЫРЫЕ НАПРЯЖЕНИЯ ===
    raw_voltages = read_all_channels()

    # === ПРИМЕНЯЕМ КАЛИБРОВКУ — ПОЛУЧАЕМ ФИЗИЧЕСКИЕ ЗНАЧЕНИЯ ===
    values = apply_calibration(raw_voltages, cfg)
    o2 = values["o2_avg"]
    gas = values["gas_flow"]
    pressure = values["air_pressure"]

    if None in (o2, gas, pressure):
        return {"error": "Invalid sensor data"}

    # === Уровень 1: базовое целевое давление по таблице ===
    air_target_base = linear_interpolate(gas, cfg.get("air_fuel_table", []))

    # Безопасность
    min_p = pid.get("pressure_min_safe", 0.5)
    max_p = pid.get("pressure_max_safe", 9.0)
    if pressure < min_p or pressure > max_p:
        return {"warning": f"Pressure out of safe range: {pressure:.2f}"}

    # === Уровень 2: ПИД-коррекция по O2 ===
    o2_setpoint = pid.get("o2_setpoint", 3.5)
    error = o2_setpoint - o2  # (+) → мало O2 → нужно больше воздуха

    deadband = pid.get("deadband", 0.1)
    if abs(error) <= deadband:
        correction = 0.0
        _integral = 0.0
        _last_error = 0.0
        action = "HOLD"
    else:
        dt = interval
        _integral += error * dt
        derivative = (error - _last_error) / dt if _last_error is not None else 0.0

        Kp = pid.get("Kp", 0.8)
        Ki = pid.get("Ki", 0.02)
        Kd = pid.get("Kd", 0.1)

        pid_output = Kp * error + Ki * _integral + Kd * derivative
        max_corr = pid.get("max_correction", 0.8)
        correction = max(-max_corr, min(max_corr, pid_output))

        _last_error = error

        # Управление реле (РЕЛЕ 1 = МЕНЬШЕ, РЕЛЕ 2 = БОЛЬШЕ)
        if correction > 0.1:
            # Нужно УВЕЛИЧИТЬ давление → включаем РЕЛЕ 2 ("больше")
            set_relay(4, True)   # ← было 1, стало 2
            time.sleep(pid.get("impulse_duration", 1.5))
            set_relay(4, False)
            action = "UP"
        elif correction < -0.1:
            # Нужно УМЕНЬШИТЬ давление → включаем РЕЛЕ 1 ("меньше")
            set_relay(3, True)   # ← было 2, стало 1
            time.sleep(pid.get("impulse_duration", 1.5))
            set_relay(3, False)
            action = "DOWN"

    _last_control_time = now
    return {
        "gas_flow": round(gas, 1),
        "air_target_base": round(air_target_base, 2),
        "air_pressure": round(pressure, 2),
        "o2_avg": round(o2, 2),
        "error": round(error, 2),
        "correction": round(correction, 2) if 'correction' in locals() else 0.0,
        "action": action
    }