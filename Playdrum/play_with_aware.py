import asyncio
import time
from music_continuator_new import MusicContinuator
from sensor_connect import SensorConnector
from drum_aware import DrumAwareProb

# ================== 配置 ==================
SENSOR_DRUM_MAP = {
    0: "kick",       # HIP
    1: "snare",      # HEAD
    2: "tom_high",   # L_WRIST
    3: "crash",      # R_WRIST
    4: "clap",       # L_ANKLE
    5: "cowbell"     # R_ANKLE
}

SENSOR_COOLDOWN_TIME = 0.45  # 秒
MUSIC_CONTINUATOR_MODEL_PATH = "/home/kong/PycharmProjects/Playdrum/drum_kit_rnn.mag"
DRUM_MODEL_PATH = "/home/kong/PycharmProjects/Playdrum/drum_kit_rnn.mag"

# ================== 初始化 ==================
music_continuator = MusicContinuator(MUSIC_CONTINUATOR_MODEL_PATH)
drum_aware = DrumAwareProb(DRUM_MODEL_PATH, threshold=0.3)
# 跟踪每个传感器的上次触发时间
last_sensor_trigger_time = {}
# ================== 传感器回调 ==================
def sensor_moved(sensor_id: int, sensor_name: str, timestamp: float, accel=None):
    current_time = time.time()
    # 冷却检测
    if sensor_id in last_sensor_trigger_time and current_time - last_sensor_trigger_time[sensor_id] < SENSOR_COOLDOWN_TIME:
        return
    last_sensor_trigger_time[sensor_id] = current_time
    drum = SENSOR_DRUM_MAP.get(sensor_id)
    if drum is None:
        return
    # 校正
    corrected_drum = drum_aware.input_hit(drum, current_time)
    # 输入到 MusicContinuator（生成连贯鼓点）
    music_continuator.input_a_hit(corrected_drum, current_time)
    # 即时播放（由 DrumPlayer 内部线程管理并发）
    music_continuator._safe_play(corrected_drum)
    print(f"Sensor {sensor_name} (ID={sensor_id}) triggered. Drum={drum}, Corrected={corrected_drum}")
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
        print("[DEBUG] 停止播放...")
        music_continuator.stop()























