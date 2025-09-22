import os
import time
import threading
import numpy as np
import torch

from magenta.models.drums_rnn import drums_rnn_sequence_generator
from note_seq.protobuf import generator_pb2
from note_seq.protobuf import music_pb2
from drum_player import DrumPlayer
from magenta.models.shared import sequence_generator_bundle

# ===== 常量 =====
PAD_IDX = 18819
START_TOKEN = 18816
EOS_TOKEN = 18818

SEQ_LEN = 8192
NUM_OUT_BATCHES = 1
MODEL_TOP_P = 0.96
MODEL_TEMPERATURE = 1.2
NUM_PRIME_TOKENS = 7168
NUM_GEN_TOKENS = 128  # 对应 Drums RNN 生成长度

MAX_CURRENT_HITS_NUM = 100000  # 累计击打数量达到后触发生成
TIME_TOKEN_MS = 16
MAX_TIME_TOKEN = 255
MAX_HISTORY = 500

# ===== 生成音乐参数 =====
GENERATED_MUSIC_DURATION = 60  # 生成60秒的音乐
LOOP_PLAYBACK = True  # 是否循环播放生成音乐
LOOP_GAP = 0.5  # 循环间隙（秒），0表示无缝循环

# 鼓件词表
DRUM_VOCAB = {
    "kick": 0,
    "snare": 1,
    "hihat_closed": 2,
    "hihat_open": 3,
    "tom_low": 4,
    "tom_mid": 5,
    "tom_high": 6,
    "crash": 7,
    "ride": 8,
    "clap": 10,
    "cowbell": 11,
}
ID2DRUM = {v: k for k, v in DRUM_VOCAB.items()}
DRUM_BASE_TOKEN = 256

# MIDI 映射（Drums RNN 使用标准 GM Drum Kit MIDI 号）
DRUM_TO_MIDI = {
    "kick": 36,
    "snare": 38,
    "hihat_closed": 42,
    "hihat_open": 46,
    "tom_low": 43,
    "tom_mid": 47,
    "tom_high": 50,
    "crash": 49,
    "ride": 51,
    "clap": 39,
    "cowbell": 56
}
MIDI_TO_DRUM = {v: k for k, v in DRUM_TO_MIDI.items()}


# ===== 环境加速 =====
def set_environment():
    os.environ['USE_FLASH_ATTENTION'] = '1'
    try:
        torch.set_float32_matmul_precision('high')
    except Exception:
        pass
    try:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    except Exception:
        pass
    # 下面启用高级 SDP/FLASH 的调用放在 try/except，以防某些 torch 版本没有这些 API
    try:
        torch.backends.cuda.enable_mem_efficient_sdp(True)
        torch.backends.cuda.enable_math_sdp(True)
        torch.backends.cuda.enable_flash_sdp(True)
        torch.backends.cuda.enable_cudnn_sdp(True)
    except Exception:
        pass


class MusicContinuator:
    def __init__(self, bundle_path: str):
        set_environment()
        self.device = 'cuda'
        self.bundle = sequence_generator_bundle.read_bundle_file(bundle_path)
        generator_map = drums_rnn_sequence_generator.get_generator_map()
        gen_key = 'drum_kit'
        # 加载 Drums RNN 模型
        self.generator = generator_map[gen_key](checkpoint=None, bundle=self.bundle)
        self.generator.initialize()  # 初始化模型

        self.drum_player = DrumPlayer()
        self.current_hits = [[]]  # 累计输入击打（['drum', ms, name]）
        self.generated_hits = [[]]  # 最近一轮模型生成（['drum', ms, name]）
        self.start_generation_step = False
        self.can_play_generated_music = False  # 是否可以播放生成音乐
        self.generating = False
        self.generated_music_ready = False  # 生成音乐是否已准备好
        self.music_loop_active = False  # 音乐循环是否正在进行
        self.music_segment_duration = None  # 生成音乐的时长（ms）

        # 播放管理
        self._playback_thread = None
        self._playback_stop = threading.Event()
        self._playback_lock = threading.Lock()

        # playback buffer: key = absolute quantized tick index (int),
        # value = list of drum_name to play at that tick.
        self.playback_buffer = {}
        self.playback_buffer_lock = threading.Lock()

        # 参考时间基准（ms），所有绝对时间都以 self.ref_time_ms 为基准
        self.ref_time_ms = None
        self.ref_perf = None  # perf_counter 对应 ref_time_ms 的时间点（秒）

        # 控制线程退出
        self._stop_playback = threading.Event()

        self.current_hits_lock = threading.Lock()
        self.generated_hits_lock = threading.Lock()

        # 启动持续播放线程
        self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._playback_thread.start()

        print("Music Continuator Drum Model 成功加载并启动播放调度线程")


    def input_a_hit(self, drum_name: str, abs_time: float):
        if drum_name not in DRUM_VOCAB:
            return
        # 检查是否可以开始播放生成音乐
        self._check_play_generated_music(drum_name)
        # 初始化参考时间，这里所有内部时间使用以 ms 为单位的绝对时间（相对于 ref_time_ms）
        if self.ref_time_ms is None:
            self.ref_time_ms = int(abs_time * 1000)
            self.ref_perf = time.perf_counter()
        rel_ms = int(round((abs_time * 1000) - self.ref_time_ms))
        with self.current_hits_lock:
            self.current_hits[0].append(['drum', rel_ms, drum_name])
        # 立刻把这个输入的击打加入播放缓冲（量化）
        self._schedule_hit(rel_ms, drum_name)
        # 触发本地播放（非阻塞）
        self._safe_play(drum_name)
        # 检查是否触发模型生成
        with self.current_hits_lock:
            if not self.start_generation_step and len(self.current_hits[0]) >= MAX_CURRENT_HITS_NUM:
                self.start_generation_step = True
                self.can_play_generated_music = False
                print(f"已达到 {MAX_CURRENT_HITS_NUM} 个击打，启动自动生成")
        if self.start_generation_step and not self.generating:
            threading.Thread(target=self._generate_loop, daemon=True).start()








    def _check_play_generated_music(self, drum_name: str):
        """检查是否满足播放生成音乐的条件"""
        if self.start_generation_step and not self.can_play_generated_music and self.generated_music_ready:
            with self.current_hits_lock:
                if len(self.current_hits[0]) >= MAX_CURRENT_HITS_NUM:
                    self.can_play_generated_music = True
                    print(f"[DEBUG] 检测到额外击打，开始播放60秒生成音乐")
                    # 启动音乐循环播放
                    if LOOP_PLAYBACK:
                        self.music_loop_active = True
                        threading.Thread(target=self._music_loop_playback, daemon=True).start()
                    else:
                        # 非循环模式，直接调度一次播放
                        self._schedule_generated_music()

    def _schedule_generated_music(self):
        """将生成的音乐调度到播放缓冲"""
        with self.generated_hits_lock:
            if not self.generated_hits or not self.generated_hits[0]:
                return
            # 计算当前时间，用于调整生成音乐的时间偏移
            if self.ref_time_ms is None:
                current_ms = 0
            else:
                elapsed_s = time.perf_counter() - self.ref_perf
                current_ms = int(round(elapsed_s * 1000))
            # 调度生成音乐，从当前时间开始播放
            for hit in self.generated_hits[0]:
                _, t_ms, drum_name = hit
                # 将生成音乐的时间调整到从当前时间开始播放
                adjusted_ms = current_ms + t_ms
                self._schedule_hit(adjusted_ms, drum_name)
            print(f"已调度 {len(self.generated_hits[0])} 个生成击打到播放缓冲")

    def _music_loop_playback(self):
        """循环播放生成音乐"""
        print(f"启动生成音乐循环播放")
        self.music_loop_active = True
        while self.music_loop_active and not self._stop_playback.is_set():
            # 调度当前循环的音乐
            self._schedule_generated_music()
            # 计算需要等待的时间（音乐时长 + 间隙）
            wait_time = (self.music_segment_duration / 1000.0) + LOOP_GAP
            print(f"音乐循环播放完成，等待 {wait_time:.1f}秒后重新播放")
            # 等待下一轮循环
            time.sleep(wait_time)
        print(f"音乐循环播放已停止")











    # ================= 调度与量化 =================
    def _quantize_ms_to_tick(self, abs_ms: int) -> int:
        # 量化到 TIME_TOKEN_MS 的最近刻度（整数 tick）
        return int(round(abs_ms / TIME_TOKEN_MS))

    def _schedule_hit(self, rel_ms: int, drum_name: str):
        """
        rel_ms: 相对于 self.ref_time_ms 的毫秒（int），可以为负（非常早的输入）——仍会放入 buffer
        """
        tick = self._quantize_ms_to_tick(rel_ms)
        with self.playback_buffer_lock:
            if tick not in self.playback_buffer:
                self.playback_buffer[tick] = []
            self.playback_buffer[tick].append(drum_name)
        # keep buffer small: 清理过期刻度（比当前早很多的）
        self._prune_old_ticks()

    def _prune_old_ticks(self):
        # 删除比当前 tick 早超过 BUFFER_WINDOW_TICKS 的条目
        WINDOW_MS = 70000  # 保留70秒，适应60秒循环音乐
        now_tick = self._current_tick()
        if now_tick is None:
            return
        prune_before = now_tick - int(WINDOW_MS / TIME_TOKEN_MS)
        with self.playback_buffer_lock:
            # 构造待删除列表避免运行时修改字典
            to_del = [t for t in self.playback_buffer.keys() if t < prune_before]
            for t in to_del:
                del self.playback_buffer[t]

    def _current_tick(self):
        if self.ref_time_ms is None or self.ref_perf is None:
            return None
        elapsed_s = time.perf_counter() - self.ref_perf
        elapsed_ms = int(round(elapsed_s * 1000))
        return self._quantize_ms_to_tick(elapsed_ms + 0)  # +0 for clarity

    # ================= 编解码（保留原实现） =================
    def encode_hits_to_tokens(self):
        # 可保留用于调试
        if not self.current_hits or not self.current_hits[0]:
            return [START_TOKEN]

        seq = sorted(self.current_hits[0], key=lambda x: x[1])
        tokens = [START_TOKEN]
        last_time = 0
        for _, t_ms, drum_name in seq:
            delta_ms = max(0, t_ms - last_time)
            dt_tok = max(0, min(MAX_TIME_TOKEN, int(round(delta_ms / TIME_TOKEN_MS))))
            tokens.append(dt_tok)
            drum_id = DRUM_VOCAB[drum_name]
            tokens.append(DRUM_BASE_TOKEN + drum_id)
            last_time = t_ms
        return tokens

    def decode_tokens_to_hits(self, tokens):
        hits = []
        cur_time_ms = 0
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if 0 <= tok <= MAX_TIME_TOKEN:
                cur_time_ms += tok * TIME_TOKEN_MS
                i += 1
                continue
            if DRUM_BASE_TOKEN <= tok < DRUM_BASE_TOKEN + len(DRUM_VOCAB):
                drum_id = tok - DRUM_BASE_TOKEN
                drum_name = ID2DRUM.get(drum_id, None)
                if drum_name:
                    hits.append(['drum', cur_time_ms, drum_name])
                i += 1
                continue
            i += 1
        self.generated_hits = hits
        return hits

    # ================= NoteSequence 转换 =================
    def hits_to_note_sequence(self):
        ns = music_pb2.NoteSequence()
        ns.tempos.add(qpm=120)  # 默认 120 BPM
        last_time = 0
        seq = sorted(self.current_hits[0], key=lambda x: x[1])
        for _, t_ms, drum_name in seq:
            t_sec = t_ms / 1000.0
            note = ns.notes.add()
            note.instrument = 10  # 鼓组通道
            note.pitch = DRUM_TO_MIDI.get(drum_name, 36)
            note.velocity = 100
            note.start_time = t_sec
            note.end_time = t_sec + 0.125  # 16分音符
            last_time = max(last_time, note.end_time)  # 更新最后时间
        ns.total_time = last_time  # **确保 total_time 正确**
        return ns

    def note_sequence_to_hits(self, ns):
        hits = []
        max_time_ms = 0
        for note in ns.notes:
            t_ms = int(round(note.start_time * 1000))
            drum_name = MIDI_TO_DRUM.get(note.pitch, None)
            if drum_name:
                hits.append(['drum', t_ms, drum_name])
            max_time_ms = max(max_time_ms, int(round(note.end_time * 1000)))

        # 记录音乐段的持续时间
        self.music_segment_duration = max_time_ms
        return hits

    # ================= 后台生成（生成60秒音乐） =================
    def _generate_loop(self):
        self.generating = True
        print(f"[DEBUG] 开始生成 {GENERATED_MUSIC_DURATION} 秒鼓点...")

        try:
            # 一次性生成60秒音乐
            with self.current_hits_lock:
                if len(self.current_hits[0]) > MAX_HISTORY:
                    self.current_hits[0] = self.current_hits[0][-MAX_HISTORY:]
                primer_ns = self.hits_to_note_sequence()

            print(f"[DEBUG] 输入击打数量: {len(self.current_hits[0])}")
            start_time = time.time()

            generator_options = generator_pb2.GeneratorOptions()
            generate_section = generator_options.generate_sections.add()
            generate_section.start_time = primer_ns.total_time  # 从序列末尾开始生成
            generate_section.end_time = primer_ns.total_time + GENERATED_MUSIC_DURATION  # 生成60秒
            generator_options.args['temperature'].float_value = MODEL_TEMPERATURE

            generated_ns = self.generator.generate(primer_ns, generator_options)
            print(f"[DEBUG] 60秒音乐生成完成，耗时: {time.time() - start_time:.2f}秒")

            # 把生成的 NoteSequence 转为击打，但不立即调度
            with self.generated_hits_lock:
                gen_hits = self.note_sequence_to_hits(generated_ns)
                self.generated_hits = [gen_hits]  # 存储但不播放
                self.generated_music_ready = True  # 标记音乐已生成
                print(f"[DEBUG] 生成了 {len(gen_hits)} 个鼓点（{GENERATED_MUSIC_DURATION}秒），等待额外击打触发循环播放")

            # 等待播放条件满足
            while self.start_generation_step and not self.can_play_generated_music and not self._stop_playback.is_set():
                print(f"[DEBUG] 等待额外击打触发播放...")
                time.sleep(0.1)

        except Exception as e:
            print(f"[ERROR] 生成线程异常: {e}")
        finally:
            self.generating = False
            print("[DEBUG] 生成线程结束")

    # ================= 持续播放线程 =================
    def _playback_loop(self):
        """
        持续运行：按刻度检查 playback_buffer，触发该刻度上的所有击打（并发触发）。
        """
        MIN_SLEEP = 0.002  # 最小 sleep 精度
        print("[DEBUG] 播放调度线程已启动")
        while not self._stop_playback.is_set():
            if self.ref_time_ms is None:
                # 没有启用时间参考，短暂等待
                time.sleep(0.01)
                continue
            now_perf = time.perf_counter()
            elapsed_ms = int(round((now_perf - self.ref_perf) * 1000))
            current_tick = self._quantize_ms_to_tick(elapsed_ms)

            # 取出当前 tick 的事件并触发
            with self.playback_buffer_lock:
                events = self.playback_buffer.pop(current_tick, None)

            if events:
                # 并发触发该刻度上的所有击打
                for drum in events:
                    self._spawn_play(drum)

            # 微小睡眠以节省 CPU，但仍保持精度
            time.sleep(MIN_SLEEP)

        print("[DEBUG] 播放调度线程已停止")

    def _spawn_play(self, drum_name):
        """
        将播放实际调用放入独立线程，使得同一时刻多个声音可以并行触发（避免串行阻塞）。
        """
        t = threading.Thread(target=self._call_play_safe, args=(drum_name,), daemon=True)
        t.start()

    def _call_play_safe(self, drum_name):
        try:
            self.drum_player.play(drum_name)
        except Exception as e:
            print(f"[ERROR] _call_play_safe 播放失败 {drum_name}: {e}")

    # 保留向后兼容的接口（其他地方可能仍调用）
    def _safe_play(self, drum_name: str):
        """
        立即触发一次播放（非阻塞）。
        也会在播放缓冲中预写当前刻度（避免丢失）。
        """
        if self.ref_time_ms is None:
            # 如果还没有参考时间，立刻设定，保证缓冲和 perf 的参考一致
            self.ref_time_ms = int(time.time() * 1000)
            self.ref_perf = time.perf_counter()

        # 立即在播放缓冲中安排当前刻度
        now_elapsed_ms = int(round((time.perf_counter() - self.ref_perf) * 1000))
        quant_tick = self._quantize_ms_to_tick(now_elapsed_ms)
        with self.playback_buffer_lock:
            if quant_tick not in self.playback_buffer:
                self.playback_buffer[quant_tick] = []
            self.playback_buffer[quant_tick].append(drum_name)

        # 并行触发一次播放（以降低感知延迟）
        self._spawn_play(drum_name)

    # ================= 控制方法 =================
    def stop_music_loop(self):
        """停止音乐循环播放"""
        self.music_loop_active = False
        print("[DEBUG] 音乐循环播放已停止")

    def start_music_loop(self):
        """手动启动音乐循环播放（如果已生成音乐）"""
        if self.generated_music_ready and not self.music_loop_active:
            self.can_play_generated_music = True
            self.music_loop_active = True
            threading.Thread(target=self._music_loop_playback, daemon=True).start()
            print("[DEBUG] 手动启动音乐循环播放")

    # ================= 其他工具方法 =================
    def stop(self):
        """在程序退出或不需要时调用"""
        self._stop_playback.set()
        self.music_loop_active = False
        self.can_play_generated_music = False
        self.generated_music_ready = False
        self.generating = False
        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=1.0)
        print("[DEBUG] MusicContinuator 已停止")

    def set_generation_params(self, duration: int = 60, loop: bool = True, gap: float = 0.5):
        """动态调整生成参数"""
        global GENERATED_MUSIC_DURATION, LOOP_PLAYBACK, LOOP_GAP
        GENERATED_MUSIC_DURATION = duration
        LOOP_PLAYBACK = loop
        LOOP_GAP = gap
        print(f"[DEBUG] 生成参数更新: 音乐时长={duration}s, 循环播放={loop}, 间隙={gap}s")