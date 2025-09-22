import pygame
import time
from typing import List, Tuple


class DrumPlayer:
    def __init__(self):
        pygame.mixer.init()
        # 设置足够多的声道（默认8个）
        pygame.mixer.set_num_channels(128)
        self.sounds = {
            "kick": pygame.mixer.Sound("DrumSamples/kick-808.wav"),
            "snare": pygame.mixer.Sound("DrumSamples/snare-808.wav"),
            "hihat_closed": pygame.mixer.Sound("DrumSamples/hihat-acoustic01.wav"),
            "hihat_open": pygame.mixer.Sound("DrumSamples/hihat-acoustic02.wav"),
            "tom_low": pygame.mixer.Sound("DrumSamples/tom-acoustic01.wav"),
            "tom_mid": pygame.mixer.Sound("DrumSamples/tom-acoustic01.wav"),
            "tom_high": pygame.mixer.Sound("DrumSamples/tom-808.wav"),
            "crash": pygame.mixer.Sound("DrumSamples/crash-808.wav"),
            "ride": pygame.mixer.Sound("DrumSamples/ride-acoustic01.wav"),
            "clap": pygame.mixer.Sound("DrumSamples/clap-808.wav"),
            "cowbell": pygame.mixer.Sound("DrumSamples/cowbell-808.wav"),
        }
        # 跟踪可用声道
        self.channels = [pygame.mixer.Channel(i) for i in range(pygame.mixer.get_num_channels())]
        self.channel_index = 0
    def play(self, drum_name: str):
        if drum_name in self.sounds:
            # 动态分配一个空闲声道
            channel = self._get_free_channel()
            if channel:
                channel.play(self.sounds[drum_name])
            else:
                print(f"No free channel available for {drum_name}")
    def _get_free_channel(self):
        # 循环查找空闲声道
        for _ in range(len(self.channels)):
            channel = self.channels[self.channel_index]
            self.channel_index = (self.channel_index + 1) % len(self.channels)
            if not channel.get_busy():
                return channel
        return None
    def add_to_play_list(self, playlist: List[Tuple[float, str]]):
        if not playlist:
            return
        # 按时间戳排序
        playlist.sort(key=lambda x: x[0])
        start_time = time.time()
        # 分组处理同一时间戳的鼓点
        current_time = playlist[0][0]
        current_group = []
        i = 0
        while i < len(playlist):
            time_sec, drum_name = playlist[i]
            if abs(time_sec - current_time) < 0.001:  # 同一时间戳（允许1ms误差）
                current_group.append(drum_name)
                i += 1
            else:
                # 等待直到当前时间戳
                elapsed = time.time() - start_time
                if elapsed < current_time:
                    time.sleep(current_time - elapsed)
                # 并行播放当前组的鼓点
                for drum_name in current_group:
                    self.play(drum_name)
                # 更新到下一组
                current_time = time_sec
                current_group = [drum_name]
                i += 1
        # 播放最后一组
        elapsed = time.time() - start_time
        if elapsed < current_time:
            time.sleep(current_time - elapsed)
        for drum_name in current_group:
            self.play(drum_name)

    def __del__(self):
        pygame.mixer.quit()