import asyncio
import time
from music_continuator_new import MusicContinuator
from sensor_connect import SensorConnector
from drum_aware import DrumAwareProb

# ================== 配置 ==================
SENSOR_DRUM_MAP = {
    0: "kick",  # HIP
    1: "snare",  # HEAD
    2: "tom_high",  # L_WRIST
    3: "crash",  # R_WRIST
    4: "clap",  # L_ANKLE
    5: "cowbell"  # R_ANKLE
}

SENSOR_COOLDOWN_TIME = 0.25  # 秒
MUSIC_CONTINUATOR_MODEL_PATH = "/home/kong/PycharmProjects/Playdrum/drum_kit_rnn.mag"
DRUM_MODEL_PATH = "/home/kong/PycharmProjects/Playdrum/drum_kit_rnn.mag"




# 曲谱
DRUM_PATTERN = [
    # 小节 1
    "crash", "hihat_closed", "snare", "hihat_closed",  # crash 开头，snare 在第2拍
    "kick", "hihat_closed", "snare", "hihat_closed",   # kick 在第1拍
    # 小节 2
    "kick", "hihat_closed", "snare", "hihat_closed",
    "kick", "hihat_closed", "clap", "hihat_open",      # 用 clap 和 hihat_open 点缀
    # 小节 3
    "kick", "hihat_closed", "snare", "hihat_closed",
    "kick", "hihat_closed", "snare", "hihat_closed",
    # 小节 4
    "kick", "hihat_closed", "snare", "hihat_closed",
    "kick", "hihat_closed", "clap", "cowbell"          # 用 cowbell 结束，增加趣味
]
# ================== 初始化 ==================
music_continuator = MusicContinuator(MUSIC_CONTINUATOR_MODEL_PATH)
drum_aware = DrumAwareProb(DRUM_MODEL_PATH, threshold=0.3)
# 跟踪每个传感器的上次触发时间
last_sensor_trigger_time = {}
# 跟踪曲谱中的当前位置
current_pattern_index = 0
# ================== 传感器回调 ==================
def sensor_moved(sensor_id: int, sensor_name: str, timestamp: float, accel=None):
    """
    当传感器移动时触发，按照曲谱播放下一个鼓点
    """
    global current_pattern_index
    current_time = time.time()
    # 冷却检测
    if sensor_id in last_sensor_trigger_time and current_time - last_sensor_trigger_time[
        sensor_id] < SENSOR_COOLDOWN_TIME:
        return
    last_sensor_trigger_time[sensor_id] = current_time
    # 获取曲谱中的下一个鼓点
    drum = DRUM_PATTERN[current_pattern_index]
    # 更新曲谱索引，循环到开头
    current_pattern_index = (current_pattern_index + 1) % len(DRUM_PATTERN)
    # 输入到 MusicContinuator（生成连贯鼓点）
    music_continuator.input_a_hit(drum, current_time)
    # 即时播放（由 DrumPlayer 内部线程管理并发）
    music_continuator._safe_play(drum)
    print(f"Sensor {sensor_name} (ID={sensor_id}) triggered. Played drum={drum}, Pattern index={current_pattern_index}")
# ================== 主 asyncio 循环 ==================
async def main():
    # 初始化传感器连接器
    connector = SensorConnector()
    # 连接所有传感器，并传入回调函数
    await connector.connect_all(sensor_moved)







if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("停止播放...")
        music_continuator.stop()