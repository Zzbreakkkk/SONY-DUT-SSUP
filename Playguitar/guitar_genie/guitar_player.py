import pygame
import os
import time
import threading

class GuitarPlayer:
    
    def __init__(self):
        file_dir = os.path.dirname(os.path.abspath(__file__))
        pygame.mixer.init()
        self.sound_list = [pygame.mixer.Sound(os.path.join(file_dir, "sounds/ukulele", f"{i}.wav")) for i in range(40, 100)]
        self.channel_list = [pygame.mixer.Channel(i) for i in range(7)]
        self.playing_notes = False
        self.list_to_be_played = []
    
    def play(self, pitch, string):
        if not self.playing_notes:
            self.channel_list[string - 1].play(self.sound_list[pitch - 40])
    def play_a_note(self, pitch, string):
        self.channel_list[string - 1].play(self.sound_list[pitch - 40])
    def add_to_play_list(self, notes):
        self.list_to_be_played.append(notes)
    def play_notes_in_list(self):
        if not self.playing_notes and self.list_to_be_played:
            notes = self.list_to_be_played.pop(0)
            self.play_notes(notes)
    def note_off(self, pitch, string):
        """停止指定弦上的音符播放"""
        channel = self.channel_list[string - 1]
        channel.fadeout(100)
    def play_notes(self, notes):
        channel_usage = {}
        playing_notes = []
        available_channels = [0, 1, 2, 3, 4, 5, 6]
        self.playing_notes = True

        def allocate_channel(required_time):
            """分配可用通道"""
            now = time.time()
            # 检查是否有通道已释放
            for channel, release_time in list(channel_usage.items()):
                if release_time <= now:
                    del channel_usage[channel]
                    available_channels.append(channel)
            # 优先使用空闲通道
            if available_channels:
                return available_channels.pop(0)
            # 无空闲通道时，等待最早释放的通道
            earliest_release = min(channel_usage.values())
            time.sleep(max(0, earliest_release - time.time()))
            return allocate_channel(required_time)  # 递归直到获得通道
        def play_note(self, start_time, duration, pitch):
            """播放单个音符"""
            # 等待到指定开始时间
            current_time = time.time()
            if current_time < start_time:
                time.sleep(start_time - current_time)
            # 分配通道并播放
            channel = allocate_channel(start_time + duration)
            self.play_a_note(pitch, channel)
            channel_usage[channel] = start_time + duration
            playing_notes.append((pitch, channel, start_time + duration))
        # 计算时间偏移，使第一个音符在0时刻播放
        first_note_time = notes[0][0]
        start_time = time.time() + 0.1  # 100ms启动延迟
        # 创建播放线程
        threads = []
        for note in notes:
            abs_start = start_time + (note[0] - first_note_time)
            t = threading.Thread(
                target=play_note,
                args=(self, abs_start, note[1], note[2])
            )
            t.daemon = True
            threads.append(t)
            t.start()
        # 等待所有音符开始播放
        time.sleep(abs_start - time.time() + 0.1)
        # 等待最短播放时间
        min_duration = min(note[1] for note in notes)
        time.sleep(min_duration)
        self.playing_notes = False
        print("播放完成")
