import time
import torch
import random
from note_seq.protobuf import music_pb2, generator_pb2
from magenta.models.drums_rnn import drums_rnn_sequence_generator
from magenta.models.shared import sequence_generator_bundle
from drum_player import DrumPlayer
import threading  # 新增：用于异步更新
import queue  # 新增：用于线程间通信

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


class DrumAwareProb:
    """
    实时鼓点修正类：根据模型预测概率判断用户输入是否合理。
    """

    def __init__(self, bundle_path, threshold: float = 0.3, device=None, max_history_ms=2000,
                 pregen_duration_sec=10, update_interval_sec=5):
        """
        :param bundle_path: Drums RNN 模型路径
        :param threshold: 用户输入合理性概率阈值
        :param max_history_ms: 最大历史长度（毫秒）
        :param pregen_duration_sec: 预生成序列长度（秒）
        :param update_interval_sec: 异步更新间隔（秒）
        """
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.threshold = threshold
        self.drum_player = DrumPlayer()
        self.max_history_ms = max_history_ms
        self.pregen_duration_sec = pregen_duration_sec
        self.update_interval_sec = update_interval_sec

        # 加载 Drums RNN
        self.bundle = sequence_generator_bundle.read_bundle_file(bundle_path)
        generator_map = drums_rnn_sequence_generator.get_generator_map()
        self.generator = generator_map['drum_kit'](checkpoint=None, bundle=self.bundle)
        self.generator.initialize()

        self.history_hits = []
        self.start_time = None
        self.pre_generated_hits = []  # 新增：存储预生成候选击打列表（[tick_ms, drum_name]，相对时间）
        self.pre_gen_base_time = 0  # 新增：预生成序列的基准时间（ms）

        # 线程安全锁和队列
        self.lock = threading.Lock()  # 新增：保护共享数据
        self.update_queue = queue.Queue()  # 新增：用于触发更新

        # 初始化预生成序列
        self._pre_generate_sequence()

        # 启动异步更新线程
        self._start_update_thread()

    # ---------------- 外部接口 ----------------
    def input_hit(self, drum_name: str, abs_time: float):
        """接收当前击打，返回修正后的击打"""
        if drum_name not in DRUM_VOCAB:
            return None
        if self.start_time is None:
            self.start_time = abs_time
        tick_ms = int((abs_time - self.start_time) * 1000)
        # 更新历史并限制长度
        with self.lock:
            self.history_hits.append(['drum', tick_ms, drum_name])
            self.history_hits = [h for h in self.history_hits if tick_ms - h[1] <= self.max_history_ms]
        # 从预生成序列中提取候选击打
        candidate_hits = self._extract_candidates(tick_ms)
        corrected_hit = self._choose_hit_prob(drum_name, candidate_hits)
        # 播放最终击打
        self.drum_player.play(corrected_hit)
        # 更新历史（用修正后的击打）
        with self.lock:
            self.history_hits[-1] = ['drum', tick_ms, corrected_hit]  # 替换用户输入为修正后
        # 触发更新
        return corrected_hit

    # ---------------- 内部方法 ----------------
    def _hits_to_note_sequence(self, hits):
        ns = music_pb2.NoteSequence()
        ns.tempos.add(qpm=120)
        last_time = 0
        for _, t_ms, drum_name in hits:
            t_sec = t_ms / 1000.0
            note = ns.notes.add()
            note.instrument = 10
            note.pitch = DRUM_TO_MIDI[drum_name]
            note.velocity = 100
            note.start_time = t_sec
            note.end_time = t_sec + 0.125
            last_time = max(last_time, note.end_time)
        ns.total_time = last_time
        return ns

    def _note_sequence_to_hits(self, ns):
        hits = []
        for note in ns.notes:
            drum_name = MIDI_TO_DRUM.get(note.pitch, None)
            if drum_name:
                hits.append([int(note.start_time * 1000), drum_name])  # 返回 [tick_ms, drum_name]
        return hits

    def _pre_generate_sequence(self):
        """预生成长序列"""
        with self.lock:
            primer_hits = self.history_hits[:]  # 复制历史
            primer_ns = self._hits_to_note_sequence(primer_hits)
            base_time_sec = primer_ns.total_time
            self.pre_gen_base_time = int(base_time_sec * 1000)  # 更新基准时间

        generator_options = generator_pb2.GeneratorOptions()
        section = generator_options.generate_sections.add()
        section.start_time = base_time_sec
        section.end_time = base_time_sec + self.pregen_duration_sec
        generator_options.args['temperature'].float_value = 1.2

        generated_ns = self.generator.generate(primer_ns, generator_options)
        new_hits = self._note_sequence_to_hits(generated_ns)  # [tick_ms_relative, drum_name]，tick_ms从0开始（相对base_time）

        with self.lock:
            self.pre_generated_hits = [[t_ms + self.pre_gen_base_time, drum] for t_ms, drum in new_hits]  # 转换为绝对时间

    def _extract_candidates(self, current_tick_ms, window_ms=500):
        """从预生成序列中提取当前时间后的窗口内候选击打"""
        candidates = []
        with self.lock:
            for t_ms, drum in self.pre_generated_hits:
                if current_tick_ms < t_ms <= current_tick_ms + window_ms:
                    candidates.append(['drum', t_ms, drum])
        return candidates

    def _start_update_thread(self):
        """启动异步更新线程"""
        def update_loop():
            while True:
                time.sleep(self.update_interval_sec)
                self._pre_generate_sequence()

        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()

    import random

    def _choose_hit_prob(self, user_hit, candidate_hits, context_window=4, user_weight=0.15):
        """
        改进版选择击打：
        1. 使用候选击打频率作为概率分布
        2. 给用户输入加权
        3. 考虑上下文窗口，避免重复
        """
        if not candidate_hits:
            return user_hit

        # 统计候选击打出现次数
        freq = {}
        for _, _, drum in candidate_hits:
            freq[drum] = freq.get(drum, 0) + 1

        total = sum(freq.values())
        probs = {k: v / total for k, v in freq.items()}

        # 用户输入加权
        if user_hit in probs:
            probs[user_hit] += user_weight
        else:
            probs[user_hit] = user_weight

        # 上下文限制：避免连续重复
        with self.lock:
            recent_hits = [h[2] for h in self.history_hits[-context_window:]]
        for drum in recent_hits:
            if drum in probs:
                probs[drum] *= 0.5  # 降低最近出现鼓件概率

        # 归一化概率
        s = sum(probs.values())
        probs = {k: v / s for k, v in probs.items()}

        # 概率采样
        drums, drum_probs = zip(*probs.items())
        chosen = random.choices(drums, weights=drum_probs, k=1)[0]
        return chosen