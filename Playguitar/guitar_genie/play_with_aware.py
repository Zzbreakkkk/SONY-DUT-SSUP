import serial
import serial.tools.list_ports
from pynput import keyboard
import time
from guitar_genie import GuitarGenie
from time_syncer import TimeSyncer
from music_continuator import MusicContinuator

# 配置 GuitarGenie 和 MusicContinuator
GUITAR_GENIE_MODEL_PATH = "trained_model/guitar_genie/model.pt"
GUITAR_GENIE_CFG_PATH = "trained_model/guitar_genie/cfg.json"
MUSIC_CONTINUATOR_MODEL_PATH = "trained_model/music_continuator/model.pth"
guitar_genie = GuitarGenie(GUITAR_GENIE_MODEL_PATH, GUITAR_GENIE_CFG_PATH)
music_continuator = MusicContinuator(MUSIC_CONTINUATOR_MODEL_PATH)
time_syncer = TimeSyncer(1.0)


# 定义 base_frets for keys 1-9
base_frets = [1, 2, 4, 1, 2, 4, 1, 2, 4]
# 定义音高表
pitch_table = [
    [67, 60, 64, 69],  # fret 0
    [68, 61, 65, 70],
    [69, 62, 66, 71],
    [70, 63, 67, 72],
    [71, 64, 68, 73],
    [72, 65, 69, 74],
    [73, 66, 70, 75],
    [74, 67, 71, 76],
    [75, 68, 72, 77],
    [76, 69, 73, 78],
    [77, 70, 74, 79],
    [78, 71, 75, 80],
    [79, 72, 76, 81],
    [80, 73, 77, 82],
    [81, 74, 78, 83],
    [82, 75, 79, 84],
    [83, 76, 80, 85],
    [84, 77, 81, 86],
    [85, 78, 82, 87],
    [86, 79, 83, 88],
    [87, 80, 84, 89]   # fret 20
]

# 按键到通道的映射 (only 1-9)
key_to_channel = {
    '1': 0,
    '2': 1,
    '3': 2,
    '4': 3,
    '5': 4,
    '6': 5,
    '7': 6,
    '8': 7,
    '9': 8
}

# 全局变量
arduino = None
listener = None
pressed_channels = set()  # 当前按下的通道
last_press_time = {}  # 记录每个按键的最后触发时间
DEBOUNCE_TIME = 0.4  # 防抖时间（秒，增加到200ms以确保过滤重复）
active_strings = {}  # 记录每个弦的当前音高 {string_num: pitch}
PITCH_LIMIT = (60, 83)
OPTIMIZE_MODE = True
CONTINUATION_MODE = True

def update_note(original_pitch, current_time):
    original_pitch = max(PITCH_LIMIT[0], min(original_pitch, PITCH_LIMIT[1]))
    input = int((original_pitch - PITCH_LIMIT[0]) / 3) + 1
    new_pitch = guitar_genie.press(current_time, input)
    print(f"输入音高：{original_pitch} -> 输出音高：{new_pitch}")
    return new_pitch



def on_press(key):
    try:
        key_str = key.char.lower()
        if key_str in key_to_channel:
            current_time = time.time()
            # 防抖：检查是否在防抖时间内
            if key_str not in last_press_time or current_time - last_press_time[key_str] > DEBOUNCE_TIME:
                last_press_time[key_str] = current_time
                channel = key_to_channel[key_str]
                if channel not in pressed_channels:
                    pressed_channels.add(channel)
                    # 计算当前偏移，但不播放
                    fret_offset = sum(base_frets[ch] for ch in pressed_channels)
                    print(f"Pressed: key {key_str}, channel {channel}, fret_offset {fret_offset}")
    except AttributeError:
        pass


def on_release(key):
    try:
        key_str = key.char.lower()
        if key_str in key_to_channel:
            channel = key_to_channel[key_str]
            if channel in pressed_channels:
                pressed_channels.remove(channel)
                # 计算当前偏移，但不播放
                fret_offset = sum(base_frets[ch] for ch in pressed_channels) if pressed_channels else 0
                print(f"Released: key {key_str}, channel {channel}, fret_offset {fret_offset}")
                # 如果没有按键了，停止所有活跃的弦
                if not pressed_channels:
                    for string_num, pitch in list(active_strings.items()):
                        music_continuator.guitar_player.note_off(pitch, string_num)
                        print(f"Stopped: string {string_num}, pitch {pitch}")
                    active_strings.clear()
    except AttributeError:
        pass

def connect_port():
    global arduino
    while True:
        try:
            ports = serial.tools.list_ports.comports()
            arduino_port = None
            for port in ports:
                if "ttyUSB" in port.device or "ttyACM" in port.device:
                    arduino_port = port.device
                    break
            if arduino_port:
                arduino = serial.Serial(port=arduino_port, baudrate=115200, timeout=1)
                time.sleep(2)
                print(f"端口{arduino_port}已连接")
                return
            else:
                print("Arduino未运行")
                time.sleep(5)
        except Exception as e:
            print(f"错误: {e}")
            time.sleep(10)

def loop():
    global listener
    if not arduino:
        print("未检测到端口连接")
        return
    try:
        while listener and listener.is_alive():
            if arduino.in_waiting > 0:
                data = arduino.readline().decode('utf-8').strip()
                try:
                    string_num, handle = map(int, data.split(','))
                    print(f"Received from Arduino: string={string_num}, handle={handle}")
                    string_idx = string_num - 1
                    fret_offset = sum(base_frets[ch] for ch in pressed_channels)
                    effective_fret = fret_offset + handle - 1 if fret_offset != 0 else 0
                    effective_fret = max(0, min(20, effective_fret))
                    new_pitch = pitch_table[effective_fret][string_idx]
                    # 触发播放
                    if string_num in active_strings:
                        old_pitch = active_strings[string_num]
                        music_continuator.guitar_player.note_off(old_pitch, string_num)
                    current_time = time_syncer.get_relative_time()
                    if OPTIMIZE_MODE:
                        new_pitch = update_note(new_pitch, current_time)
                    current_time_synced = time_syncer.get_relative_time()
                    music_continuator.guitar_player.play(new_pitch, string_num)
                    active_strings[string_num] = new_pitch
                    if CONTINUATION_MODE:
                        music_continuator.input_a_note(new_pitch, current_time_synced)
                    print(f"Played: string {string_num}, pitch {new_pitch}")
                except ValueError:
                    print(f"Invalid data from serial: {data}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("进程中断")
    finally:
        if listener and listener.is_alive():
            listener.stop()
        if arduino and arduino.is_open:
            arduino.close()























def init():
    global listener
    connect_port()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    print("开始演奏...")

def main():
    init()
    loop()

if __name__ == "__main__":
    main()