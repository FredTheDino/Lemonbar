#!/usr/bin/python
from time import sleep
from math import sin
import sys
import datetime
import subprocess
import colorsys as c 
import threading

# Requires i3, pulsectl, and evdev.
import i3
import evdev
import pulsectl

def hex_pad(n):
    s = hex(int(n))[2:]
    padding = 2 - len(s)
    if padding > 0:
        return "0" * padding + s
    else:
        return s[:2]

def to_hex(color, alpha=255):
    out  = "#"
    out += hex_pad(alpha) # Alpha is first...
    out += hex_pad(color[0]) 
    out += hex_pad(color[1]) 
    out += hex_pad(color[2]) 
    return out.upper()

# Assumes RGB in values
def lerp_as_hsv(color_a, color_b, value):
    a = c.rgb_to_hsv(color_a[0] / 255, color_a[1] / 255, color_a[2] / 255)
    b = c.rgb_to_hsv(color_b[0] / 255, color_b[1] / 255, color_b[2] / 255)
    lerped = [x * value + y * (1.0 - value) for x, y in zip(a, b)]
    out_rgb = c.hsv_to_rgb(lerped[0], lerped[1], lerped[2])

    return tuple([out_rgb[0] * 255, out_rgb[1] * 255, out_rgb[2] * 255])

def hex_to_rgb(color_code):
    return tuple(int(color_code[i:i+2], 16) for i in (1, 3, 5))    

colors = {
    "default_bg" : hex_to_rgb("#1f1b21"),
    "default_fg" : hex_to_rgb("#cdd2da"),
    "black"      : hex_to_rgb("#22252a"),
    "red"        : hex_to_rgb("#603b38"), 
    "blue"       : hex_to_rgb("#7b3a86"),
    "dark_blue"  : hex_to_rgb("#53265b"),
    "green"      : hex_to_rgb("#715c57"),
    "yellow"     : hex_to_rgb("#67717a"),
}

def bar(text):
    print(text)
    sys.stdout.flush()

def empty():
    return ""

def endline():
    fg = set_fg(colors["default_fg"], 0)
    bg = set_bg(colors["default_bg"], 0)
    u = set_u(colors["default_bg"], 0)
    return fg + bg + u

def reset():
    fg = set_fg(colors["default_fg"])
    bg = set_bg(colors["default_bg"])
    u = set_u(colors["default_bg"])
    return fg + bg + u

def section(text, highlight):
    spacer = blank(15)
    bg = colors["default_bg"]
    fg = colors["default_fg"]
    u = highlight # highlight
    return set_bg(bg) + set_fg(fg) + set_u(u) + spacer + str(text) + spacer + reset()

def set_u(color, alpha=255):
    return "%{U" + to_hex(color)[0:-2] + "}"

def set_fg(color, alpha=255):
    return "%{F" + to_hex(color, alpha) + "}"

def set_bg(color, alpha=255):
    return "%{B" + to_hex(color, alpha) + "}"

def center():
    return "%{c}"

def right():
    return "%{r}"

def left():
    return "%{l}"

def blank(space):
    return "%{{O{}}}".format(space)

#def is_fullscreen():
#    windows = get_windows_from_current_workspace() 
#
#    num_bars = 0
#    if len(windows) <= num_bars:
#        return False
#
#    for w in windows:
#        if w["fullscreen_mode"] and w["type"] != "workspace":
#            return True
#    return False

def get_current_workspace():
    ''' Returns the current workspace '''
    workspaces = i3.msg('get_workspaces')
    workspace = i3.filter(tree=workspaces, focused=True)
    if workspace:
        return workspace[0]["name"]
    return ''

def get_windows_from_current_workspace():
    res = []
    ws = get_current_workspace()
    workspace = i3.filter(name=ws)
    if workspace:
        workspace = workspace[0]
        return i3.filter(workspace, nodes=[])
    return res

def setup_evdev():
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        if "keyboard" in dev.name:
            return dev

workspace_cache = ""
def format_workspaces():
    global workspace_cache
    unused_sym = "●"
    current_sym = "●"
    used_sym = "○"

    workspaces = i3.get_workspaces()
    if not workspaces:
        return workspace_cache
    num_workspaces = 10
    default = set_fg(colors["black"]) + unused_sym
    out = [default] * num_workspaces
    for workspace in workspaces:
        urgent = workspace["urgent"]
        focused = workspace["focused"]
        index = int(workspace['name']) - 1
        if index < 0:
            index = 9

        if focused:
            sym = set_fg(colors["default_fg"]) + current_sym
        else:
            sym = set_fg(colors["default_fg"]) + used_sym

        out[index] = sym

    bg_color = colors["default_bg"]
    workspace_cache = section(" ".join(out), bg_color)
    return workspace_cache

weekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
def time():
    today = datetime.datetime.today()
    now = datetime.datetime.now()
    time_string =  weekdays[today.weekday()] + " {:%H:%M}".format(now)
    text = time_string

    t = (now.hour * 60 + now.minute) / 60
    fade_value = -t * (t - 24) / 144 #Parabola
    bg_color = lerp_as_hsv(colors["yellow"], colors["red"], fade_value)
    return section(text, bg_color)

pulse = pulsectl.Pulse("lemonbar", threading_lock=True)
def volume():
    sink = pulse.sink_list()[0]
    if sink.mute:
        text = "MUTE"
        fade_value = 0.0
    else:
        vol = round(sink.volume.value_flat * 100)
        text = "VOL {}%".format(vol)
        fade_value = (vol / 100) ** 2

    bg_color = lerp_as_hsv(colors["dark_blue"], colors["yellow"], fade_value) 
    return section(text, bg_color)

def fetch_battery_status():
    base = "/sys/class/power_supply/"
    procentage = int(open(base + "BAT0/capacity", "r").read())
    plugged_in = "1" in open(base + "AC/online", "r").read()
    return procentage, plugged_in

def power():
    procentage, plugged_in = fetch_battery_status()

    if plugged_in:
        fade_value = 1.0
    else:
        p = procentage / 100
        fade_value = min((p - 0.2) * (p + 0.2), 0)

    text = "BAT {}%".format(procentage)
    bg_color = lerp_as_hsv(colors["green"], colors["red"], fade_value) 
    return section(text, bg_color)

def power_warning():
    procentage, plugged_in = fetch_battery_status()
    if (not plugged_in and procentage < 20):
        return right() + section("(WARNING) BAT {}%".format(procentage), colors["red"])
    return ""

def checker():
    while True:
        connection_checker()
        sleep(0.5)

online_lock = threading.Lock()
online_status = False
def connection_checker():
    global online_lock, online_status
    cmd = ["ping", "www.sunet.se", "-c 1"]
    ret_code = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    online_lock.acquire()
    online_status = (ret_code == 0)
    online_lock.release()

def online(online_color, offline_color):
    global online_lock, online_status
    online_lock.acquire()
    status = online_status
    online_lock.release()
    if status:
        return section("ONLINE", online_color)
    return section("OFFLINE", offline_color)

def full_bar():
    spacer = blank(10)
    left_line   = left()   + time()
    center_line = center() + format_workspaces()
    right_line  = right()  + online(colors["blue"], colors["red"]) 
    right_line += spacer   + volume() 
    right_line += spacer   + power()
    return left_line + center_line + right_line + endline()

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

if __name__ == "__main__":
    thread = threading.Thread(name="i3 Checker", target=checker)
    thread.start()
    keyboard = setup_evdev()
    super_key = 125
    redraw_counter = 0
    warning_counter = 0
    redraw_on_key = False
    while True:
        for event in keyboard.read_loop():
            if event.code == super_key:
                if event.value == 0:
                    bar(empty())
                    warning_counter = 9999
                    redraw_on_key = False
                elif event.value == 1:
                    bar(full_bar())
                    redraw_on_key = True
            elif event.value == 2 and redraw_on_key:
                redraw_counter += 1
                if redraw_counter > 40:
                    redraw_counter = 0
                    bar(full_bar())
            elif redraw_on_key:
                redraw_counter = 0
                bar(full_bar())
            elif not redraw_on_key:
                warning_counter += 1
                warning_counter = max(warning_counter, 100)
                warning = power_warning()
                if warning_counter > 15:
                    warning_counter = 0
                    bar(warning)
                    continue
