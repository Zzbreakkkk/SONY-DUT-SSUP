import mido
import time
import threading
from collections import deque
from guitar_player import GuitarPlayer

file_path = "春雷.mid"

class MIDIPlayer:
    def __init__(self):
        self.guitar_player = GuitarPlayer()
        self.available_channels = [0, 1, 2, 3, 4, 5, 6]  # 跳过通道10(打击乐)
        self.channel_usage = {}  # 通道使用记录: {channel: release_time}
        self.scheduler = None
        self.playing_notes = []  # 当前播放的音符

    def parse_midi(self, file_path):
        """解析MIDI文件，提取音符信息[[6]][[9]]"""
        midi = mido.MidiFile(file_path)
        ticks_per_beat = midi.ticks_per_beat
        tempo = 500000  # 默认速度(500000 μs/beat)

        # 存储所有音符事件 (开始时间, 持续时间, 音高)
        note_events = []
        # 当前时间(ticks)和激活的音符{音符编号: 开始时间}
        current_tick = 0
        active_notes = {}

        for track in midi.tracks:
            for msg in track:
                current_tick += msg.time

                # 处理速度变化
                if msg.type == 'set_tempo':
                    tempo = msg.tempo

                # 音符开始事件
                elif msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = current_tick

                # 音符结束事件
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start_tick = active_notes[msg.note]
                        duration = current_tick - start_tick
                        note_events.append((start_tick, duration, msg.note))
                        del active_notes[msg.note]

        # 计算时间转换因子
        μs_per_tick = tempo / ticks_per_beat
        return [
            (start_tick * μs_per_tick / 1_000_000,  # 转换为秒
             duration * μs_per_tick / 1_000_000,  # 持续时间(秒)
             note)
            for start_tick, duration, note in note_events
        ]

    def allocate_channel(self, required_time):
        """分配可用通道"""
        now = time.time()

        # 检查是否有通道已释放
        for channel, release_time in list(self.channel_usage.items()):
            if release_time <= now:
                del self.channel_usage[channel]
                self.available_channels.append(channel)

        # 优先使用空闲通道
        if self.available_channels:
            return self.available_channels.pop(0)

        # 无空闲通道时，等待最早释放的通道
        earliest_release = min(self.channel_usage.values())
        time.sleep(max(0, earliest_release - time.time()))
        return self.allocate_channel(required_time)  # 递归直到获得通道

    def play_note(self, start_time, duration, pitch):
        """播放单个音符"""
        # 等待到指定开始时间
        current_time = time.time()
        if current_time < start_time:
            time.sleep(start_time - current_time)

        # 分配通道并播放
        channel = self.allocate_channel(start_time + duration)
        self.guitar_player.play(pitch, channel)
        self.channel_usage[channel] = start_time + duration
        self.playing_notes.append((pitch, channel, start_time + duration))

    def play_midi(self, file_path):
        """主播放函数[[6]][[10]]"""

        # 解析MIDI文件
        note_events = sorted(self.parse_midi(file_path), key=lambda x: x[0])
        if not note_events:
            print("未找到可播放的音符")
            return

        # 计算时间偏移，使第一个音符在0时刻播放
        first_note_time = note_events[0][0]
        start_time = time.time() + 0.1  # 100ms启动延迟

        # 创建播放线程
        threads = []
        for event in note_events:
            abs_start = start_time + (event[0] - first_note_time)
            t = threading.Thread(
                target=self.play_note,
                args=(abs_start, event[1], event[2])
            )
            t.daemon = True
            threads.append(t)
            t.start()

        # 等待所有音符开始播放
        time.sleep(abs_start - time.time() + 0.1)

        # 等待最短播放时间
        min_duration = min(event[1] for event in note_events)
        time.sleep(min_duration)

        print("播放完成")

player = MIDIPlayer()
player.play_midi("One More Time One More Chance.mid")