"""
CPU Power Control — System Tray App
MSI GF63 / i7-12650H + RTX 4060

Controls:
  - CPU PL1/PL2 via WinRing0 MSR writes
  - Turbo Boost via powercfg
  - Auto-switches to Battery mode when unplugged

Requirements:
  - WinRing0x64.dll + WinRing0x64.sys in same folder
  - Run as Administrator
  - pip install pystray pillow psutil
"""

import sys
import os
import json
import subprocess
import threading
import time
import ctypes
import psutil
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item, Menu

# ─── PATHS ───────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
MUTEX_NAME  = "CPUPowerControl_SingleInstance"

# ─── MODE DEFINITIONS ────────────────────────────────────────────────────────

MODES = {
    "Battery": {
        "pl1": 10, "pl2": 15,
        "boost": False,
        "boost_toggleable": False,
        "color": (0, 255, 65),
    },
    "Balanced": {
        "pl1": 20, "pl2": 25,
        "boost": True,
        "boost_toggleable": True,
        "color": (255, 215, 0),
    },
    "Performance": {
        "pl1": 30, "pl2": 65,
        "boost": True,
        "boost_toggleable": True,
        "color": (255, 68, 68),
    },
}

# ─── STATE ───────────────────────────────────────────────────────────────────

current_mode          = "Balanced"
boost_overrides       = {"Battery": None, "Balanced": None, "Performance": None}
winring0              = None
winring0_available    = False
tray_icon             = None
_mutex_handle         = None
cpu_power_watt        = 0.0
_last_energy_raw      = None
_last_energy_time     = None

# ─── SINGLE INSTANCE CHECK ───────────────────────────────────────────────────

def ensure_single_instance():
    global _mutex_handle
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, True, MUTEX_NAME)
    last_error    = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:
        ctypes.windll.user32.MessageBoxW(
            0,
            "CPU Power Control is already running.\nCheck your system tray.",
            "Already Running",
            0x40
        )
        sys.exit(0)

# ─── ADMIN ELEVATION ─────────────────────────────────────────────────────────

def ensure_admin():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1
        )
        sys.exit(0)

# ─── PERSISTENT CONFIG ───────────────────────────────────────────────────────

def load_config():
    global current_mode, boost_overrides
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            mode = cfg.get("last_mode", "Balanced")
            if mode in MODES:
                current_mode = mode
            saved_overrides = cfg.get("boost_overrides", {})
            for k in boost_overrides:
                if k in saved_overrides:
                    boost_overrides[k] = saved_overrides[k]
    except Exception:
        pass

def save_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({
                "last_mode":       current_mode,
                "boost_overrides": boost_overrides
            }, f, indent=2)
    except Exception:
        pass

# ─── TOAST NOTIFICATION ──────────────────────────────────────────────────────

def _notify(title, message):
    try:
        script = (
            f"Add-Type -AssemblyName System.Windows.Forms;"
            f"$n = New-Object System.Windows.Forms.NotifyIcon;"
            f"$n.Icon = [System.Drawing.SystemIcons]::Information;"
            f"$n.Visible = $true;"
            f"$n.ShowBalloonTip(3000, '{title}', '{message}', "
            f"[System.Windows.Forms.ToolTipIcon]::None);"
            f"Start-Sleep -Milliseconds 3500;"
            f"$n.Dispose()"
        )
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=0x08000000
        )
    except Exception:
        pass

# ─── WINRING0 MSR ACCESS ─────────────────────────────────────────────────────

def init_winring0():
    global winring0, winring0_available
    dll  = os.path.join(BASE_DIR, "WinRing0x64.dll")
    sys_ = os.path.join(BASE_DIR, "WinRing0x64.sys")
    if not os.path.exists(dll) or not os.path.exists(sys_):
        winring0_available = False
        return False
    try:
        winring0 = ctypes.WinDLL(dll)
        winring0.InitializeOls.restype = ctypes.c_bool
        if not winring0.InitializeOls():
            winring0 = None
            winring0_available = False
            return False
        winring0_available = True
        return True
    except Exception:
        winring0 = None
        winring0_available = False
        return False

def _read_msr(idx):
    if not winring0:
        return None
    eax, edx = ctypes.c_uint32(), ctypes.c_uint32()
    if winring0.Rdmsr(ctypes.c_uint32(idx), ctypes.byref(eax), ctypes.byref(edx)):
        return (edx.value << 32) | eax.value
    return None

def _write_msr(idx, val):
    if not winring0:
        return False
    eax = ctypes.c_uint32(val & 0xFFFFFFFF)
    edx = ctypes.c_uint32((val >> 32) & 0xFFFFFFFF)
    return bool(winring0.Wrmsr(ctypes.c_uint32(idx), eax, edx))

def _power_unit():
    msr = _read_msr(0x606)
    return 0.125 if msr is None else 1.0 / (1 << (msr & 0xF))

def set_power_limits(pl1w, pl2w):
    if not winring0_available:
        return False
    unit    = _power_unit()
    current = _read_msr(0x610)
    if current is None:
        return False
    if (current >> 63) & 1:
        return False
    pl1u = int(pl1w / unit) & 0x7FFF
    pl2u = int(pl2w / unit) & 0x7FFF
    new  = current
    new  = (new & ~0x7FFF) | pl1u
    new |= (1 << 15)
    new  = (new & ~(0x7FFF << 32)) | (pl2u << 32)
    new |= (1 << 47)
    return _write_msr(0x610, new)

# ─── RAPL CPU POWER READING ──────────────────────────────────────────────────

def _sample_cpu_power():
    """Read CPU package power via RAPL MSR_PKG_ENERGY_STATUS (0x611)"""
    global cpu_power_watt, _last_energy_raw, _last_energy_time
    if not winring0_available:
        return
    try:
        unit_msr = _read_msr(0x606)
        if unit_msr is None:
            return
        energy_unit  = 1.0 / (1 << ((unit_msr >> 8) & 0x1F))
        energy_msr   = _read_msr(0x611)
        if energy_msr is None:
            return
        energy_raw   = energy_msr & 0xFFFFFFFF
        now          = time.time()
        if _last_energy_raw is not None and _last_energy_time is not None:
            delta_raw    = (energy_raw - _last_energy_raw) & 0xFFFFFFFF  # handle wrap
            delta_joules = delta_raw * energy_unit
            delta_t      = now - _last_energy_time
            if delta_t > 0:
                cpu_power_watt = delta_joules / delta_t
        _last_energy_raw  = energy_raw
        _last_energy_time = now
    except Exception:
        pass

# ─── TURBO BOOST ─────────────────────────────────────────────────────────────

def get_active_scheme_guid():
    try:
        result = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True, text=True, creationflags=0x08000000
        )
        parts = result.stdout.strip().split()
        for i, p in enumerate(parts):
            if p == "GUID:" and i + 1 < len(parts):
                return parts[i + 1]
    except Exception:
        pass
    return "381b4222-f694-41f0-9685-ff5bb260df2e"

def set_turbo_boost(enabled: bool):
    val  = "2" if enabled else "0"
    guid = get_active_scheme_guid()
    for scope in ("ac", "dc"):
        subprocess.run(
            ["powercfg", f"/set{scope}valueindex", guid,
             "SUB_PROCESSOR", "PERFBOOSTMODE", val],
            capture_output=True, creationflags=0x08000000
        )
    subprocess.run(
        ["powercfg", "/setactive", guid],
        capture_output=True, creationflags=0x08000000
    )

# ─── BOOST HELPERS ───────────────────────────────────────────────────────────

def get_boost(mode_name):
    ov = boost_overrides.get(mode_name)
    return ov if ov is not None else MODES[mode_name]["boost"]

def toggle_boost(mode_name):
    boost_overrides[mode_name] = not get_boost(mode_name)
    if current_mode == mode_name:
        set_turbo_boost(boost_overrides[mode_name])
    save_config()
    _rebuild_tray()

# ─── APPLY MODE ──────────────────────────────────────────────────────────────

def apply_mode(mode_name, notify=False):
    global current_mode
    current_mode = mode_name
    mode  = MODES[mode_name]
    boost = get_boost(mode_name)
    set_power_limits(mode["pl1"], mode["pl2"])
    set_turbo_boost(boost)
    save_config()
    if notify:
        boost_str = "Boost ON" if boost else "Boost OFF"
        _notify(
            "CPU Power Control",
            f"Switched to {mode_name}  |  PL1:{mode['pl1']}W  |  {boost_str}"
        )

# ─── GRACEFUL EXIT ────────────────────────────────────────────────────────────

def graceful_exit(icon):
    set_turbo_boost(True)
    set_power_limits(125, 125)
    save_config()
    if winring0:
        try:
            winring0.DeinitializeOls()
        except Exception:
            pass
    icon.stop()

# ─── BATTERY MONITOR ─────────────────────────────────────────────────────────

_last_ac = None

def _battery_loop():
    global _last_ac
    while True:
        try:
            batt = psutil.sensors_battery()
            if batt:
                on_ac = batt.power_plugged
                if _last_ac is not None and _last_ac != on_ac:
                    if not on_ac:
                        apply_mode("Battery", notify=True)
                    else:
                        apply_mode("Balanced", notify=True)
                    _rebuild_tray()
                _last_ac = on_ac
        except Exception:
            pass
        time.sleep(10)

def _power_monitor_loop():
    """Samples CPU power every 2s and updates tray tooltip"""
    # Prime the first reading
    _sample_cpu_power()
    time.sleep(2)
    while True:
        try:
            _sample_cpu_power()
            _update_tooltip()
        except Exception:
            pass
        time.sleep(2)

# ─── ICON BUILDER ────────────────────────────────────────────────────────────

def _make_icon(mode_name):
    r, g, b = MODES[mode_name]["color"]
    boost   = get_boost(mode_name)
    size    = 64
    img     = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d       = ImageDraw.Draw(img)
    d.ellipse([1,  1,  size-2,  size-2],  fill=(r, g, b, 60))
    d.ellipse([6,  6,  size-7,  size-7],  fill=(r, g, b, 255))
    d.ellipse([14, 14, size-15, size-15], fill=(15, 15, 20, 230))
    bars    = {"Battery": 1, "Balanced": 2, "Performance": 3}
    n       = bars[mode_name]
    bw, bh, gap = 8, 16, 5
    total   = n * bw + (n - 1) * gap
    x_start = (size - total) // 2
    for i in range(n):
        x = x_start + i * (bw + gap)
        d.rectangle([x, 24, x + bw, 24 + bh], fill=(r, g, b, 255))
    if not boost:
        d.ellipse([46, 46, 58, 58], fill=(255, 255, 255, 220))
        d.ellipse([49, 49, 55, 55], fill=(30, 30, 30, 255))
    return img

# ─── TRAY MENU ───────────────────────────────────────────────────────────────

def _power_str():
    if not winring0_available:
        return "CPU: N/A"
    return f"CPU: {cpu_power_watt:.1f}W"

def _update_tooltip():
    """Lightweight tooltip update — no menu rebuild, no icon redraw"""
    if tray_icon:
        mode      = MODES[current_mode]
        boost_str = "Boost ON" if get_boost(current_mode) else "Boost OFF"
        tray_icon.title = (
            f"CPU Control  |  {current_mode}  |  "
            f"PL1:{mode['pl1']}W PL2:{mode['pl2']}W  |  "
            f"{boost_str}  |  {_power_str()}"
        )

def _rebuild_tray():
    if tray_icon:
        tray_icon.icon  = _make_icon(current_mode)
        mode            = MODES[current_mode]
        boost_str       = "Boost ON" if get_boost(current_mode) else "Boost OFF"
        tray_icon.title = (
            f"CPU Control  |  {current_mode}  |  "
            f"PL1:{mode['pl1']}W PL2:{mode['pl2']}W  |  "
            f"{boost_str}  |  {_power_str()}"
        )
        tray_icon.menu = _build_menu()
        tray_icon.update_menu()

def _make_apply_handler(m):
    def handler(icon, itm):
        apply_mode(m)
        _rebuild_tray()
    return handler

def _make_toggle_handler(m):
    def handler(icon, itm):
        toggle_boost(m)
    return handler

def _build_menu():
    menu_items = []
    for mode_name in ("Battery", "Balanced", "Performance"):
        mode      = MODES[mode_name]
        active    = current_mode == mode_name
        check     = "✔ " if active else "     "
        boost_str = "Boost ON" if get_boost(mode_name) else "Boost OFF"
        label     = f"{check}{mode_name}   [{mode['pl1']}W / {mode['pl2']}W | {boost_str}]"
        sub       = [item(label, _make_apply_handler(mode_name))]
        if MODES[mode_name]["boost_toggleable"]:
            cur_boost    = get_boost(mode_name)
            toggle_label = f"   Turbo Boost: {'ON  ->  turn OFF' if cur_boost else 'OFF  ->  turn ON'}"
            sub.append(item(toggle_label, _make_toggle_handler(mode_name)))
        menu_items.append(item(mode_name, Menu(*sub)))

    menu_items.append(Menu.SEPARATOR)
    mode    = MODES[current_mode]
    boost   = get_boost(current_mode)
    batt    = psutil.sensors_battery()
    pwr     = "Plugged In" if (batt and batt.power_plugged) else "On Battery"
    status  = f"[ {current_mode} | PL1:{mode['pl1']}W PL2:{mode['pl2']}W | {'Boost ON' if boost else 'Boost OFF'} | {pwr} ]"
    pwr_now = f"[ {_power_str()} live ]"
    wr_stat = "MSR: Active (PL1/PL2 + Boost)" if winring0_available else "MSR: No WinRing0 (Boost only)"
    menu_items.append(item(status,  None, enabled=False))
    menu_items.append(item(pwr_now, None, enabled=False))
    menu_items.append(item(wr_stat, None, enabled=False))
    menu_items.append(Menu.SEPARATOR)
    menu_items.append(item("Exit  (restores defaults)", graceful_exit))
    return Menu(*menu_items)

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    global tray_icon
    ensure_single_instance()
    ensure_admin()
    load_config()
    init_winring0()

    batt      = psutil.sensors_battery()
    init_mode = "Battery" if (batt and not batt.power_plugged) else current_mode
    apply_mode(init_mode)

    threading.Thread(target=_battery_loop,        daemon=True).start()
    threading.Thread(target=_power_monitor_loop,  daemon=True).start()

    mode      = MODES[init_mode]
    boost_str = "Boost ON" if get_boost(init_mode) else "Boost OFF"

    tray_icon = pystray.Icon(
        name  = "CPU Power Control",
        icon  = _make_icon(init_mode),
        title = f"CPU Control  |  {init_mode}  |  PL1:{mode['pl1']}W PL2:{mode['pl2']}W  |  {boost_str}",
        menu  = _build_menu()
    )
    tray_icon.run()

if __name__ == "__main__":
    main()
