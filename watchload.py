#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "argparse>=1.4.0",
#     "psutil>=7.2.2",
# ]
# ///

import subprocess
import os
import glob
import re
import psutil
import argparse
import curses
import time
import traceback


logo = [
 "===========================================================",
 "||        __  __             _ _                         ||",
 "||       |  \/  | ___  _ __ (_) |_ ___  _ __             ||",
 "||       | |\/| |/ _ \| '_ \| | __/ _ \| '__|            ||",
 "||       | |  | | (_) | | | | | || (_) | |               ||",
 "||       |_|  |_|\___/|_| |_|_|\__\___/|_|    V1.0       ||",
 "||                                                       ||",
 "||      Author: https://github.com/CodeZsheep1314        ||",
 "||                                                       ||",
 "|=========================================================|",
]


# 获取 NPU 负载的函数
def get_npu_load():
    try:
        # 执行命令获取输出字符串
        result = subprocess.run(['sudo', 'cat', '/sys/kernel/debug/rknpu/load'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode != 0:
            print(f"Error reading NPU load: {result.stderr.decode()}")
            return [0, 0, 0]

        output = result.stdout.decode().strip()
        
        # 正则匹配 Core0、Core1、Core2 的百分比
        core_loads = re.findall(r'Core\d+: *(\d+)%', output)
        if core_loads:
            loads = list(map(int, core_loads))
        else:
            # 正则匹配 NPU Load 的百分比
            single_load = re.search(r'NPU load: *(\d+)%', output)
            if single_load:
                loads = [int(single_load.group(1))]
            else:
                print(f"Unrecognized load format: {output}")
                return [0, 0, 0]
            
        return loads

    except Exception as e:
        print(f"Error parsing load data: {e}")
        return [0, 0, 0]

# 获取 CPU 负载的函数
def get_cpu_load():
    # 获取每个核心的 CPU 使用率
    cpu_percent = psutil.cpu_percent(percpu=True)
    return cpu_percent

def get_npudriver_version():
    npuversion_str = subprocess.run(['sudo', 'cat', '/sys/kernel/debug/rknpu/version'], stdout=subprocess.PIPE).stdout.decode('utf-8')
    # return npuversion.stdout.decode('utf-8')

    # 使用正则表达式匹配版本号
    version_match = re.search(r'RKNPU driver: v(\d+\.\d+\.\d+)', npuversion_str)
    if version_match:
        version = version_match.group(1)
        return version
        
    else:
        return "Version not found"

def get_memory_usage():
    mem_info = psutil.virtual_memory()
    memory_usage_percent = mem_info.percent
    return memory_usage_percent

# 读取所有热区温度 (°C)
def get_temperatures():
    temps = {}
    try:
        zones = sorted(glob.glob('/sys/class/thermal/thermal_zone*'))
        for zone in zones:
            try:
                with open(os.path.join(zone, 'type'), 'r') as f:
                    name = f.read().strip()
                with open(os.path.join(zone, 'temp'), 'r') as f:
                    temp_milli = int(f.read().strip())
                if name:
                    temps[name] = temp_milli / 1000.0
            except (IOError, OSError, ValueError):
                continue
    except Exception as e:
        print(f"Error reading temperatures: {e}")
    return temps

# 绘制终端中条形图的函数
def draw_bar(win, y, x, value, label, max_width=40, unit="%", label_width=None, decimals=None):
    # 标签按 label_width 右补空格, 保证多条进度条起止对齐
    if label_width is not None and len(label) < label_width:
        label = label.ljust(label_width)
    # 以 100 为上限 (用于温度时即 100°C 封顶)
    value = min(value, 100)
    bar_length = int((value / 100) * max_width)
    color = 1 if value < 40 else (2 if value < 60 else 3)  # <40 绿, 40-60 黄, >=60 红
    val_width = 9                      # 固定 9: 保证 "%" (1字符) 和 "°C" (2字符) 进度条右封口列对齐
    if decimals is not None:
        val_str = f"{value:.{decimals}f}{unit} | "
    else:
        val_str = f"{value}{unit} | "
    win.addstr(y, x, label + ": " + val_str.rjust(val_width))
    win.addstr(y, x + len(label) + 2 + val_width, "▩" * bar_length, curses.color_pair(color))
    win.addstr(y, x + len(label) + 2 + val_width + bar_length, " " * (max_width - bar_length))
    win.addstr(y, x + len(label) + 2 + val_width + max_width + 1, "|")

def draw_bar_vertical(win, flag, y, x, value, colorid, ch):
    if flag == 0 :
        for i in range(value):
            if colorid != 0 :
                win.addstr(y + i, x, ch, curses.color_pair(colorid))
            else :
                win.addstr(y + i, x, ch) # 0 默认色
    elif flag == 1:
        for i in range(value):
            if colorid != 0 :
                win.addstr(y - i, x, ch, curses.color_pair(colorid))
            else :
                win.addstr(y - i, x, ch) # 0 默认色

# 绘制 logo 的函数
def draw_logo(stdscr):
    for i, line in enumerate(logo):
        stdscr.addstr(i, 2, line)

def terminalShow(stdscr):
    curses.curs_set(0)  # 不显示光标
    stdscr.nodelay(1)   # 不等待输入
    stdscr.timeout(500)  # 更新间隔时间

    # 初始化颜色
    curses.start_color() 
    curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)   # 负载 <40% 绿色
    curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # 负载 40-60% 黄色
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)     # 负载 >=60% 红色
    curses.init_pair(4, curses.COLOR_MAGENTA, curses.COLOR_BLACK) # 提示文字洋红

    while True:
        try:
            height, width = stdscr.getmaxyx()

            # 获取所有数据 (统一在前面采集, 方便后面计算布局)
            npu_load = get_npu_load()
            cpu_load = get_cpu_load()
            npu_driver_version = get_npudriver_version()
            memory_usage_percent = get_memory_usage()
            temps = get_temperatures()

            # 清空屏幕
            stdscr.clear()

            # 绘制 logo
            draw_logo(stdscr)

            # 绘制 NPU 驱动版本
            npu_driver_str = ("RKNPU driver: v" + npu_driver_version).center(57)
            stdscr.addstr(len(logo)+0, 2, "|" + npu_driver_str + "|")

            offset = 1

            # 绘制 NPU 负载
            stdscr.addstr(len(logo)+offset+0, 2, "|---------------------------------------------------------|")
            stdscr.addstr(len(logo)+offset+1, 2, "| NPU Load per Core:                                      |")
            stdscr.addstr(len(logo)+offset+2, 2, "|---------------------------------------------------------|")
            for i, load in enumerate(npu_load):
                draw_bar(stdscr, len(logo)+offset+3 + i, 2, load, f"| NPU{i}")

            # 绘制 CPU 负载
            stdscr.addstr(len(logo)+offset+6, 2, "|---------------------------------------------------------|")
            stdscr.addstr(len(logo)+offset+7, 2, "| CPU Load per Core:                                      |")
            stdscr.addstr(len(logo)+offset+8, 2, "|---------------------------------------------------------|")
            for i, load in enumerate(cpu_load[:8]):  # 只显示前 8 个核心
                draw_bar(stdscr, len(logo)+offset+9 + i, 2, load, f"| CPU{i+1}")
            stdscr.addstr(len(logo)+offset+17, 2, "|---------------------------------------------------------|")

            # 温度区行号 (后面内存条要延伸到温度区底部)
            temp_row = len(logo) + offset + 18
            # 内存竖条底部 = 温度区最后一行, 整体高度随热区数量自适应延长
            mem_bar_bottom = temp_row + 3 + len(temps) - 1

            # 绘制内存使用情况 (右侧竖条进度条)
            draw_bar_vertical(stdscr, 0, 1, 61, mem_bar_bottom, 0, "|")
            stdscr.addstr(0, 61, "=====")
            # 在条形图顶部显示标签 占用数据
            stdscr.addstr(1, 62, f"{(int)(memory_usage_percent)}%".center(4))
            # 在条形图底部显示标签 MEM
            stdscr.addstr(mem_bar_bottom - 1, 62, "===")
            stdscr.addstr(mem_bar_bottom, 62, "MEM")
            stdscr.addstr(mem_bar_bottom + 1, 61, "-----")
            draw_bar_vertical(stdscr, 0, 1, 65, mem_bar_bottom, 0, "|")
            # 填充条高度 = mem_bar_bottom - 3 (扣除顶部 2 行标签和底部 1 行标签)
            mem_max_height = mem_bar_bottom - 3
            draw_bar_vertical(stdscr, 1, mem_bar_bottom - 2, 62,
                              (int)(memory_usage_percent * mem_max_height / 100),
                              (1 if memory_usage_percent < 50 else 2), '▓▓▓')

            # 绘制温度信息 (°C) — 使用与 NPU/CPU 一致的进度条样式
            stdscr.addstr(temp_row + 0, 2, "|---------------------------------------------------------|")
            stdscr.addstr(temp_row + 1, 2, "| Temperatures (\xb0C):                                      |")
            stdscr.addstr(temp_row + 2, 2, "|---------------------------------------------------------|")
            for i, (name, temp) in enumerate(temps.items()):
                # 去掉 "-thermal" 后缀, 标题已写明是温度, 不再加 "TMP-" 前缀
                short_name = name.replace("-thermal", "")
                # label_width=16 让所有温度条起点对齐; decimals=1 保留 1 位小数
                draw_bar(stdscr, temp_row + 3 + i, 2, temp, f"| {short_name}",
                         max_width=30, unit="\xb0C", label_width=16, decimals=1)

            # 温度区底部封口 (与内存竖条的 "-----" 在同一行, 形成完整底边)
            stdscr.addstr(temp_row + 3 + len(temps), 2, "-----------------------------------------------------------")

            # 绘制用法 (放在温度区下方)
            stdscr.addstr(temp_row + 3 + len(temps) + 1, 22, "press 'q' to exit", curses.color_pair(4))

            # 刷新屏幕
            stdscr.refresh()

            # 检查是否按下 'q' 键退出
            key = stdscr.getch()
            if key == ord('q'):
                break

            time.sleep(1)
        except Exception as e:
            stdscr.clear()
            tb = traceback.format_exc()
            stdscr.addstr(0, 0, "press 'q' to exit", curses.color_pair(4))
            stdscr.addstr(2, 0, "|| 可能因为窗口大小不足，请调整窗口大小。\n|| Maybe The window size is insufficient to draw. Please adjust the window size.")
            stdscr.addstr(5, 0, f"error: {tb}")
            
            stdscr.refresh()
            time.sleep(1)  # 等待1秒，让用户看到提示

            # 检查是否按下 'q' 键退出
            key = stdscr.getch()
            if key == ord('q'):
                break

            continue


parser = argparse.ArgumentParser(description='终端实时显示 NPU/CPU 负载与温度')
parser.add_argument('--mode', '-m', type=str, default='t', help='运行方式, 固定为 "t" (terminal 终端模式)')
args = parser.parse_args()

if __name__ == "__main__":
    if args.mode == "t":
        curses.wrapper(terminalShow)
    else:
        print("[Error] ==> 仅支持终端模式 (terminal), 用法:  python3 watchload.py  或  python3 watchload.py -m t")