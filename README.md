# CPU Power Control — Setup Guide

---

## What This App Does

| Feature | How |
|---|---|
| PL1 / PL2 watt control | WinRing0 MSR writes |
| Turbo Boost ON/OFF | Windows powercfg |
| Auto Battery mode | psutil AC/DC detection |
| System tray | pystray |

---

## Modes
example:
| Mode | PL1 | PL2 | Boost | Auto-activate |
|---|---|---|---|---|
| Battery | 10W | 20W | OFF | When unplugged |
| Balanced | 20W | 25W | ON (toggleable) | When plugged in |
| Performance | 35W | 50W | ON (toggleable) | Manual |

---

## Step 1 — Install Python Dependencies

Double-click `install.bat` OR run manually:
```
pip install pystray==0.19.5 Pillow psutil
```

---

> If WinRing0 files are missing, the app still runs — it will control
> Turbo Boost only. The tray will show "MSR: ✘ WinRing0 missing"

---

## Step 2 — Run the App

Double-click `launch.bat`

OR right-click `cpu_tray.py` → "Run as Administrator"

> Must be run as Administrator — MSR writes require kernel-level access

---

## Step 3 — Using the Tray

- Look for the colored circle icon in your system tray (bottom right)
- **Green (1 bar)** = Battery mode
- **Yellow (2 bars)** = Balanced mode  
- **Red (3 bars)** = Performance mode
- **Right-click** to open menu
- Hover over mode name to see submenu → click to apply
- Balanced/Performance have a "Toggle Boost" option

---

## Step 4 — Auto-Start with Windows (Optional)

1. Press `Win + R` → type `shell:startup` → Enter
2. Create a shortcut to `launch.bat` in that folder
3. The app will start silently with Windows

---


---

## Notes

- Changes reset on reboot — app must be running to maintain settings
- WinRing0 installs a temporary kernel service — this is normal
- If Windows Defender flags WinRing0, add an exception (it's a legitimate hardware access driver used by CPU-Z, ThrottleStop, etc.)
