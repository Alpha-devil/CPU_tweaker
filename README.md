# CPU Power Control — Setup Guide
### MSI GF63 / i7-12650H + RTX 4060

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

## Step 2 — Get WinRing0 Files (REQUIRED for PL1/PL2 control)

Without WinRing0, only Turbo Boost control works. PL1/PL2 wattage control requires the kernel driver.

1. Go to: https://github.com/GermanAizek/WinRing0/releases
2. Download the latest release zip
3. Extract and find these two files:
   - `WinRing0x64.dll`
   - `WinRing0x64.sys`
4. Place BOTH files in the same folder as `cpu_tray.py`

```
cpu_power_control/
├── cpu_tray.py          ← main app
├── WinRing0x64.dll      ← place here
├── WinRing0x64.sys      ← place here
├── install.bat
├── launch.bat
└── requirements.txt
```

> If WinRing0 files are missing, the app still runs — it will control
> Turbo Boost only. The tray will show "MSR: ✘ WinRing0 missing"

---

## Step 3 — Run the App

Double-click `launch.bat`

OR right-click `cpu_tray.py` → "Run as Administrator"

> Must be run as Administrator — MSR writes require kernel-level access

---

## Step 4 — Using the Tray

- Look for the colored circle icon in your system tray (bottom right)
- **Green (1 bar)** = Battery mode
- **Yellow (2 bars)** = Balanced mode  
- **Red (3 bars)** = Performance mode
- **Right-click** to open menu
- Hover over mode name to see submenu → click to apply
- Balanced/Performance have a "Toggle Boost" option

---

## Step 5 — Auto-Start with Windows (Optional)

1. Press `Win + R` → type `shell:startup` → Enter
2. Create a shortcut to `launch.bat` in that folder
3. The app will start silently with Windows

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Access Denied" | Must run as Administrator |
| PL1/PL2 not changing | Check WinRing0 files are in same folder |
| Lock bit error | Some OEM BIOSes lock MSR 0x610 — nothing can override this |
| App doesn't start | Run `python cpu_tray.py` in cmd to see error |
| Boost not toggling | powercfg might need a restart to take effect |

---

## Notes

- Changes reset on reboot — app must be running to maintain settings
- WinRing0 installs a temporary kernel service — this is normal
- If Windows Defender flags WinRing0, add an exception (it's a legitimate hardware access driver used by CPU-Z, ThrottleStop, etc.)
