from pynput import keyboard
import time
import mido
from music_continuator import MusicContinuator

# 配置 MusicContinuator
MUSIC_CONTINUATOR_MODEL_PATH = "trained_model/music_continuator/model.pth"
music_continuator = MusicContinuator(MUSIC_CONTINUATOR_MODEL_PATH)
# 全局变量
listener = None
note_index = 0  # 当前 MIDI 音符索引
last_press_time = {}  # 记录每个按键的最后触发时间
DEBOUNCE_TIME = 0.2  # 防抖时间（秒）
active_note = None  # 当前正在播放的音符
active_string = None  # 当前音符使用的弦

# 按键到通道的映射 (1-9)
key_to_channel = {
    '1': 0, '2': 1, '3': 2, '4': 3, '5': 4,
    '6': 5, '7': 6, '8': 7, '9': 8
}
# MIDI 文件路径
MIDI_PATH = "/home/jetson/PycharmProjects/guitar2/guitar_genie/春雷_30s.mid"  # MIDI 文件路径

# 加载 MIDI 文件并提取音高序列
midi = mido.MidiFile(MIDI_PATH)
notes = []
for track in midi.tracks:
    for msg in track:
        if hasattr(msg, 'type') and msg.type == 'note_on' and msg.velocity > 0:
            notes.append(msg.note)
print(f"Loaded {len(notes)} notes from MIDI file: {notes}")
if not notes:
    exit(1)

def on_press(key):
    global note_index, active_note, active_string
    try:
        key_str = key.char.lower()
        if key_str in key_to_channel:
            current_time = time.time()
            if key_str not in last_press_time or current_time - last_press_time[key_str] > DEBOUNCE_TIME:
                last_press_time[key_str] = current_time
                if note_index < len(notes):
                    # 停止上一个音符
                    if active_note is not None and active_string is not None:
                        music_continuator.guitar_player.note_off(active_note, active_string)
                        print(f"Stopped note: {active_note} on string {active_string}")
                    # 播放当前音符
                    pitch = notes[note_index]
                    string_num = (note_index % 4) + 1  # 循环使用 1-4 弦
                    music_continuator.guitar_player.play(pitch, string_num)
                    active_note = pitch
                    active_string = string_num
                    print(f"{key_str} Played note: {pitch} on string {string_num} (index: {note_index})")
                    note_index += 1
                    if note_index >= len(notes):
                        note_index = 0
                        print("Reached end of MIDI notes, looping back")
    except AttributeError:
        pass

def on_release(key):
    global active_note, active_string
    try:
        key_str = key.char.lower()
        if key_str in key_to_channel:
            # 停止当前音符
            if active_note is not None and active_string is not None:
                music_continuator.guitar_player.note_off(active_note, active_string)
                print(f"Stopped note: {active_note} on string {active_string}")
                active_note = None
                active_string = None
    except AttributeError:
        pass

def init():
    global listener
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    print("开始演奏")
    music_continuator.guitar_player.play(60, 1)
    time.sleep(1)
    music_continuator.guitar_player.note_off(60, 1)
def main():
    init()
    try:
        listener.join()
    except KeyboardInterrupt:
        print("程序退出")
    finally:
        if listener:
            listener.stop()
if __name__ == "__main__":
    main()