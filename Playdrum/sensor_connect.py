import asyncio
import struct
import math
from bleak import BleakClient
from bleak import BleakScanner
from bleak.backends.device import BLEDevice

# 传感器名称与MAC地址的映射
SENSOR_MAP = {
    "HEAD": "3C:38:F4:CE:59:4C",
    "L_WRIST": "3C:38:F4:D0:07:21",
    "R_WRIST": "3C:38:F4:CD:00:7E",
    "HIP": "3C:38:F4:CF:19:02",
    "L_ANKLE": "3C:38:F4:CD:F3:02",
    "R_ANKLE": "3C:38:F4:CF:91:2A",
}

# BLE特征UUID (适配Mocopi)
DATA_CHAR_UUID = "25047e64-657c-4856-afcf-e315048a965b"
CMD_CHAR_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"

# 绕X轴旋转四元数并交换Y与Z轴
def rotate_quaternion(quat, axis, angle_degrees):
    # 将角度转换为弧度
    angle_radians = math.radians(angle_degrees)
    sin_half = math.sin(angle_radians / 2)
    cos_half = math.cos(angle_radians / 2)
    w2 = cos_half
    x2 = axis[0] * sin_half
    y2 = axis[1] * sin_half
    z2 = axis[2] * sin_half
    w1, x1, y1, z1 = quat
    return (
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
    )

# 提取Mocopi格式的四元数和加速度
def convert_quaternion_and_accel(data: bytes):
    if len(data) < 30:
        return None, None
    def to_float(b):
        raw = int.from_bytes(b, byteorder='little', signed=True)
        return raw / 8192.0
    qw = to_float(data[8:10])
    qx = to_float(data[10:12])
    qy = to_float(data[12:14])
    qz = to_float(data[14:16])
    original_quat = (qw, qx, -qy, qz)
    rotated_quat = rotate_quaternion(original_quat, (1, 0, 0), 90)
    final_quat = (
        rotated_quat[0],   # w
        rotated_quat[1],   # x
        rotated_quat[3],   # z -> y
        rotated_quat[2],   # y -> z
    )
    ax = struct.unpack('<e', data[24:26])[0]
    ay = struct.unpack('<e', data[26:28])[0]
    az = struct.unpack('<e', data[28:30])[0]
    return final_quat, (ax, ay, az)

# 单台传感器管理类
class SingleTracker:
    def __init__(self, mac_or_device, sensor_id=0, name="Unknown"):
        self.mac = mac_or_device.address if isinstance(mac_or_device, BLEDevice) else mac_or_device
        self.device = mac_or_device if isinstance(mac_or_device, BLEDevice) else None
        self.name = name
        self.client = None
        self.pcounter = 0
        self.sensor_id = sensor_id
        self.last_quat = None  # 存储上一次四元数值，用于变化检测
        self.is_connected = False

    # 断开连接
    async def disconnect(self):
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
                print(f"已断开 {self.name} ({self.mac}) 的连接")
                self.is_connected = False
            except Exception as e:
                print(f"断开 {self.name} ({self.mac}) 连接时出错: {e}")

# 传感器连接管理类
class SensorConnector:
    def __init__(self):
        self.trackers = []
        self.sensor_map = SENSOR_MAP
        for i, (name, mac) in enumerate(self.sensor_map.items()):
            self.trackers.append(SingleTracker(mac, sensor_id=i, name=name))

    # 通知处理函数（当数据变化时调用回调，并传入current_quat）
    async def notification_handler(self, _, data: bytes, tracker: SingleTracker, callback):
        try:
            quat, accel = convert_quaternion_and_accel(data)
            if quat is None or accel is None:
                return
            w, x, y, z = quat
            tracker.pcounter += 1

            # 变化检测：阈值0.01，若四元数分量变化超过阈值则调用回调
            current_quat = (w, x, y, z)
            if tracker.last_quat is None or any(abs(current_quat[i] - tracker.last_quat[i]) > 0.03 for i in range(4)):
                callback(tracker.sensor_id, tracker.name, current_quat, accel)
                tracker.last_quat = current_quat
        except Exception as e:
            print(f"{tracker.name} ({tracker.mac}) 的通知处理出错: {e}")

    # 保持连接的任务
    async def maintain_connection(self, tracker: SingleTracker):
        print(f"正在为 {tracker.name} ({tracker.mac}) 保持连接 ...")
        try:
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            print(f"{tracker.name} 的连接维护出错: {e}")
        finally:
            await tracker.disconnect()

    # 扫描设备（获取真实BLEDevice对象）
    async def scan_devices(self):
        print("正在扫描设备...")
        devices = await BleakScanner.discover(timeout=10.0)
        found_devices = {}
        for device in devices:
            if device.name and device.name.startswith("QM-SS1"):
                # 匹配MAC地址（忽略大小写和冒号）
                clean_mac = device.address.replace(':', '').lower()
                for name, mac in self.sensor_map.items():
                    if clean_mac == mac.replace(':', '').lower():
                        found_devices[mac] = device
                        print(f"找到设备 {device.name} 在 {device.address}，对应 {name}")
        return found_devices

    # 连接单台传感器，无限重试直到成功
    async def connect_tracker_once(self, tracker: SingleTracker, callback):
        attempt = 0
        while True:
            attempt += 1
            print(f"[尝试 {attempt}] 正在连接 {tracker.name} ({tracker.mac}) (ID={tracker.sensor_id})")
            try:
                # 使用device对象（如果可用）或MAC地址
                client = BleakClient(tracker.device if tracker.device else tracker.mac, timeout=10.0)
                await client.connect()
                tracker.client = client  # 存储client引用
                tracker.is_connected = True

                # 尝试配对（可选）
                try:
                    if hasattr(client, "pair"):
                        await client.pair(protection_level=2)
                        print(f"尝试为 {tracker.name} ({tracker.mac}) 配对")
                except Exception as pair_err:
                    print(f"配对不支持或失败: {pair_err}")

                print(f"[尝试 {attempt}] 已连接到 {tracker.name} ({tracker.mac}) (传感器ID={tracker.sensor_id})")
                await client.start_notify(
                    DATA_CHAR_UUID,
                    lambda s, d: asyncio.create_task(self.notification_handler(s, d, tracker, callback))
                )
                print(f"[{tracker.name} ({tracker.mac})] 通知已启动")
                await client.write_gatt_char(
                    CMD_CHAR_UUID,
                    bytearray([0x7e, 0x03, 0x18, 0xd6, 0x01, 0x00, 0x00])
                )
                print(f"[{tracker.name} ({tracker.mac})] 已发送流启动命令")
                asyncio.create_task(self.maintain_connection(tracker))
                return
            except Exception as e:
                print(f"[尝试 {attempt}] 连接 {tracker.name} ({tracker.mac}) (ID={tracker.sensor_id}) 出错: {e}")
                print(f"正在重试...")
                await asyncio.sleep(2)
            tracker.is_connected = False

    # 检查未连接的传感器并输出
    async def check_unconnected(self):
        while True:
            unconnected = [t.name for t in self.trackers if not t.is_connected]
            if unconnected:
                print(f"尚未连接的设备: {', '.join(unconnected)}")
            else:
                print("所有传感器连接成功")
                break
            await asyncio.sleep(3)

    # 连接所有传感器
    async def connect_all(self, callback):
        print("开始连接传感器")
        # 先扫描设备
        found_devices = await self.scan_devices()
        # 更新trackers的device
        for t in self.trackers:
            if t.mac in found_devices:
                t.device = found_devices[t.mac]

        # 启动检查未连接任务
        check_task = asyncio.create_task(self.check_unconnected())

        # 并发启动所有连接任务
        connect_tasks = [asyncio.create_task(self.connect_tracker_once(t, callback)) for t in self.trackers]
        await asyncio.gather(*connect_tasks, return_exceptions=True)  # 允许异常不阻塞其他任务

        # 等待检查任务完成
        await check_task

        # 保持运行以处理数据
        while True:
            await asyncio.sleep(1)