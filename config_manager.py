# config_manager.py
import json

DEFAULT_CONFIG = {
    "ch0": {"name": "O2_1", "v_min": 0.0, "v_max": 1.0, "y_min": 0.0, "y_max": 25.0, "unit": "%"},
    "ch1": {"name": "O2_2", "v_min": 0.0, "v_max": 1.0, "y_min": 0.0, "y_max": 25.0, "unit": "%"},
    "ch2": {"name": "Gas_Flow", "v_min": 0.0, "v_max": 1.0, "y_min": 0.0, "y_max": 100.0, "unit": "м³/ч"},
    "ch3": {"name": "Air_Pressure", "v_min": 0.0, "v_max": 1.0, "y_min": 0.0, "y_max": 10.0, "unit": "кПа"},

    # === Базовое соотношение газ/воздух (5 точек) ===
    "air_fuel_table": [
        {"gas": 0.0,  "air_target": 1.0},
        {"gas": 20.0, "air_target": 2.0},
        {"gas": 40.0, "air_target": 3.5},
        {"gas": 70.0, "air_target": 6.0},
        {"gas": 100.0,"air_target": 8.5}
    ],

    # === ПИД-коррекция по O2 ===
    "pid_control": {
        "enabled": True,
        "o2_setpoint": 3.5,      # %
        "deadband": 0.1,         # % — зона бездействия
        "Kp": 0.8,               # коэффициент пропорциональный
        "Ki": 0.02,              # интегральный
        "Kd": 0.1,               # дифференциальный
        "max_correction": 0.8,   # максимальная коррекция давления (± кПа)
        "control_interval": 10,  # сек
        "impulse_duration": 1.5, # сек
        "pressure_min_safe": 0.5,
        "pressure_max_safe": 9.0
    }
}

def load_config():
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
            # Обеспечиваем наличие всех секций
            for key in DEFAULT_CONFIG:
                if key not in cfg:
                    cfg[key] = DEFAULT_CONFIG[key]
            return cfg
    except:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(cfg):
    with open("config.json", "w") as f:
        json.dump(cfg, f)