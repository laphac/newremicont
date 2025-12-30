# webserver.py
import socket
from ads1115 import read_all_channels
from modbus_relay import set_relay
from config_manager import load_config, save_config
from url_decode import url_decode

def voltage_to_value(v, ch_cfg):
    vmin = ch_cfg["v_min"]
    vmax = ch_cfg["v_max"]
    ymin = ch_cfg["y_min"]
    ymax = ch_cfg["y_max"]
    if vmax == vmin:
        return ymin
    return (ymax - ymin) / (vmax - vmin) * (v - vmin) + ymin

def parse_post_data(data):
    try:
        if b'\r\n\r\n' in data:
            body = data.split(b'\r\n\r\n', 1)[1]
            body_str = body.decode('utf-8')
            params = {}
            for pair in body_str.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    k = url_decode(k)
                    v = url_decode(v)
                    params[k] = v
            return params
    except Exception as e:
        print("POST parse error:", e)
    return {}

def handle_relay_request(params):
    try:
        ch = int(params.get("relay", "0"))
        action = params.get("action", "")
        if 1 <= ch <= 4 and action in ("on", "off"):
            set_relay(ch, action == "on")
    except Exception as e:
        print("Relay error:", e)

def build_web_page(voltages, cfg):
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ADS1115 + Регулятор</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 10px; background: #f9f9f9; }
        h1, h2 { color: #2c3e50; }
        .channel, .relay, .table, .pid { background: white; padding: 14px; margin: 12px 0; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        input, button, select { padding: 6px; margin: 4px; }
        .num { width: 70px; }
        .unit { width: 50px; }
        .name { width: 120px; }
        button { background: #27ae60; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button.off { background: #e74c3c; }
        .result { font-weight: bold; color: #e74c3c; font-size: 1.2em; }
        table { width: 100%; border-collapse: collapse; margin: 8px 0; }
        th, td { border: 1px solid #ccc; padding: 6px; text-align: center; }
        th { background: #f0f0f0; }
    </style>
</head>
<body>
    <h1>🎛️ Калибровка и управление</h1>
"""
    # === Каналы датчиков ===
    for i, (v, key) in enumerate(zip(voltages, ["ch0", "ch1", "ch2", "ch3"])):
        c = cfg[key]
        value = voltage_to_value(v, c)
        html += f"""
    <div class="channel">
        <strong>{c['name']}</strong><br>
        Напряжение: <code>{v:+.4f} В</code> → <span class="result">{value:.2f} {c['unit']}</span><br>
        <form action="/" method="POST">
            <input type="hidden" name="ch" value="{key}">
            Название: <input type="text" name="name" class="name" value="{c['name']}">
            Напряжение: 
            <input type="number" step="any" class="num" name="v_min" value="{c['v_min']}"> – 
            <input type="number" step="any" class="num" name="v_max" value="{c['v_max']}"> В<br>
            Значение: 
            <input type="number" step="any" class="num" name="y_min" value="{c['y_min']}"> – 
            <input type="number" step="any" class="num" name="y_max" value="{c['y_max']}">
            <input type="text" name="unit" class="unit" value="{c['unit']}">
            <button type="submit">💾 Сохранить</button>
        </form>
    </div>
"""

    # === Таблица газ/воздух ===
    table = cfg.get("air_fuel_table", [])
    # Убедимся, что 5 точек
    while len(table) < 5:
        table.append({"gas": 0.0, "air_target": 0.0})
    if len(table) > 5:
        table = table[:5]

    html += '<h2>📊 Базовое соотношение газ/воздух</h2>\n<div class="table">\n'
    html += '<form action="/table" method="POST">\n'
    html += '<table>\n<tr><th>Расход газа (м³/ч)</th><th>Целевое давление (кПа)</th></tr>\n'
    for i, point in enumerate(table):
        html += f'<tr><td><input type="number" step="0.1" class="num" name="gas_{i}" value="{point["gas"]}"</td>'
        html += f'<td><input type="number" step="0.1" class="num" name="air_{i}" value="{point["air_target"]}"</td></tr>\n'
    html += '</table>\n<button type="submit">💾 Сохранить таблицу</button>\n</form>\n</div>'

    # === ПИД-регулятор ===
    pid = cfg.get("pid_control", {})
    enabled = "checked" if pid.get("enabled", True) else ""
    html += f'''
    <h2>⚙️ ПИД-коррекция по O₂</h2>
    <div class="pid">
        <form action="/pid" method="POST">
            <label><input type="checkbox" name="enabled" value="on" {enabled}> Включить ПИД</label><br><br>

            Уставка O₂ (%): 
            <input type="number" step="0.1" class="num" name="o2_setpoint" value="{pid.get("o2_setpoint", 3.5)}"> ±
            <input type="number" step="0.1" class="num" name="deadband" value="{pid.get("deadband", 0.1)}"> %
            <br><br>

            ПИД-коэффициенты:<br>
            Kp: <input type="number" step="0.01" class="num" name="Kp" value="{pid.get("Kp", 0.8)}">
            Ki: <input type="number" step="0.001" class="num" name="Ki" value="{pid.get("Ki", 0.02)}">
            Kd: <input type="number" step="0.01" class="num" name="Kd" value="{pid.get("Kd", 0.1)}">
            <br><br>

            Макс. коррекция (кПа): 
            <input type="number" step="0.1" class="num" name="max_correction" value="{pid.get("max_correction", 0.8)}"><br>
            Интервал (сек): 
            <input type="number" step="1" class="num" name="control_interval" value="{pid.get("control_interval", 10)}">
            Импульс (сек): 
            <input type="number" step="0.1" class="num" name="impulse_duration" value="{pid.get("impulse_duration", 1.5)}">
            <br><br>

            Безопасные пределы давления:<br>
            <input type="number" step="0.1" class="num" name="pressure_min_safe" value="{pid.get("pressure_min_safe", 0.5)}"> — 
            <input type="number" step="0.1" class="num" name="pressure_max_safe" value="{pid.get("pressure_max_safe", 9.0)}">
            <br><br>

            <button type="submit">💾 Сохранить ПИД</button>
        </form>
    </div>
'''

    # === Ручное управление реле ===
    html += '<h2>🔌 Ручное управление реле</h2>'
    for ch in range(1, 5):
        html += f'''
    <div class="relay">
        <strong>Реле {ch}</strong>
        <form action="/relay" method="POST" style="display:inline;">
            <input type="hidden" name="relay" value="{ch}">
            <input type="hidden" name="action" value="on">
            <button type="submit">🟢 ВКЛ</button>
        </form>
        <form action="/relay" method="POST" style="display:inline;">
            <input type="hidden" name="relay" value="{ch}">
            <input type="hidden" name="action" value="off">
            <button type="submit" class="off">🔴 ВЫКЛ</button>
        </form>
    </div>
'''
    html += "</body></html>"
    return html

# === Вспомогательные функции парсинга ===
def safe_float(s, default):
    try:
        return float(s.strip().replace(',', '.')) if s and s.strip() else default
    except:
        return default

def safe_int(s, default):
    try:
        return int(float(s.strip())) if s and s.strip() else default
    except:
        return default

# === Обработка POST-запросов ===
def handle_request(conn):
    try:
        request = conn.recv(1024)
        cfg = load_config()

        # === Обработка реле ===
        if b"POST /relay" in request:
            params = parse_post_data(request)
            handle_relay_request(params)
            conn.send(b"HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n")

        # === Обработка таблицы газ/воздух ===
        elif b"POST /table" in request:
            params = parse_post_data(request)
            table = []
            for i in range(5):
                gas = safe_float(params.get(f"gas_{i}"), 0.0)
                air = safe_float(params.get(f"air_{i}"), 0.0)
                table.append({"gas": gas, "air_target": air})
            cfg["air_fuel_table"] = table
            save_config(cfg)
            conn.send(b"HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n")

        # === Обработка ПИД ===
        elif b"POST /pid" in request:
            params = parse_post_data(request)
            pid = cfg.get("pid_control", {})

            pid["enabled"] = params.get("enabled") == "on"
            pid["o2_setpoint"] = safe_float(params.get("o2_setpoint"), pid.get("o2_setpoint", 3.5))
            pid["deadband"] = safe_float(params.get("deadband"), pid.get("deadband", 0.1))
            pid["Kp"] = safe_float(params.get("Kp"), pid.get("Kp", 0.8))
            pid["Ki"] = safe_float(params.get("Ki"), pid.get("Ki", 0.02))
            pid["Kd"] = safe_float(params.get("Kd"), pid.get("Kd", 0.1))
            pid["max_correction"] = safe_float(params.get("max_correction"), pid.get("max_correction", 0.8))
            pid["control_interval"] = safe_int(params.get("control_interval"), pid.get("control_interval", 10))
            pid["impulse_duration"] = safe_float(params.get("impulse_duration"), pid.get("impulse_duration", 1.5))
            pid["pressure_min_safe"] = safe_float(params.get("pressure_min_safe"), pid.get("pressure_min_safe", 0.5))
            pid["pressure_max_safe"] = safe_float(params.get("pressure_max_safe"), pid.get("pressure_max_safe", 9.0))

            cfg["pid_control"] = pid
            save_config(cfg)
            conn.send(b"HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n")

        # === Обработка калибровки датчиков ===
        elif b"POST" in request:
            params = parse_post_data(request)
            ch = params.get("ch")
            if ch in cfg and ch.startswith("ch"):
                old = cfg[ch].copy()
                try:
                    name = params.get("name", old["name"]).strip()
                    cfg[ch]["name"] = name if name else old["name"]

                    cfg[ch]["v_min"] = safe_float(params.get("v_min"), old["v_min"])
                    cfg[ch]["v_max"] = safe_float(params.get("v_max"), old["v_max"])
                    cfg[ch]["y_min"] = safe_float(params.get("y_min"), old["y_min"])
                    cfg[ch]["y_max"] = safe_float(params.get("y_max"), old["y_max"])

                    unit = params.get("unit", old["unit"]).strip()
                    cfg[ch]["unit"] = unit if unit else "ед."

                    if cfg[ch]["v_min"] >= cfg[ch]["v_max"]:
                        cfg[ch]["v_max"] = cfg[ch]["v_min"] + 0.001

                    save_config(cfg)
                except Exception as e:
                    print("Calibration error:", e)
                    cfg[ch] = old
            conn.send(b"HTTP/1.1 303 See Other\r\nLocation: /\r\n\r\n")

        # === GET-запрос — главная страница ===
        else:
            voltages = read_all_channels()
            html = build_web_page(voltages, cfg)
            response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html
            conn.send(response.encode())
    except Exception as e:
        print("Request error:", e)
    finally:
        try:
            conn.close()
        except:
            pass