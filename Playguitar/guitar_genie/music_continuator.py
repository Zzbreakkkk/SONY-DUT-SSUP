import os
import torch
import numpy as np
import threading
import TMIDIX
from x_transformers_2_3_1 import TransformerWrapper, AutoregressiveWrapper, Decoder, top_p
from guitar_player import GuitarPlayer

NOTE_DURATION_TICK = 500
NOTE_TRACK = 0
NOTE_VELOCITY = 100
NOTE_INSTRUMENT = 25
NUM_OUT_BATCHES = 1
SEQ_LEN = 8192
PAD_IDX = 18819
MODEL_TOP_P = 0.96
MODEL_TEMPERATURE = 1.2
NUM_PRIME_TOKENS = 7168
NUM_GEN_TOKENS = 512
MAX_CURRENT_NOTES_NUM = 10

def set_environment():
    os.environ['USE_FLASH_ATTENTION'] = '1'

    torch.set_float32_matmul_precision('high')
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cuda.enable_mem_efficient_sdp(True)
    torch.backends.cuda.enable_math_sdp(True)
    torch.backends.cuda.enable_flash_sdp(True)
    torch.backends.cuda.enable_cudnn_sdp(True)

class MusicContinuator:
    def __init__(self, model_path):
        set_environment()
        self.device = 'cuda'
        dtype = 'bfloat16'
        self.ptdtype = {'bfloat16': torch.bfloat16, 'float16': torch.float16}[dtype]
        self.ctx = torch.amp.autocast(device_type=self.device, dtype=self.ptdtype)
        self.model = TransformerWrapper(
            num_tokens=PAD_IDX + 1,
            max_seq_len=SEQ_LEN,
            attn_layers=Decoder(
                dim=2048,
                depth=8,
                heads=32,
                rotary_pos_emb=True,
                attn_flash=True
            )
        )
        self.model = AutoregressiveWrapper(self.model, ignore_index=PAD_IDX, pad_value=PAD_IDX)
        self.model.load_state_dict(torch.load(model_path, map_location='cuda', weights_only=True))
        self.model = torch.compile(self.model, mode='max-autotune')
        self.model.cuda()
        self.model.eval()
        self.guitar_player = GuitarPlayer()
        self.current_notes = [[]]
        self.generated_notes = [[]]
        self.start_generation_step = False
        self.generating = False

        print("Music Continuator Model成功加载")

    def input_a_note(self, pitch, time):
        if not self.start_generation_step:
            note_on_tick = int(time * 1000)
            note = ['note', note_on_tick, NOTE_DURATION_TICK, NOTE_TRACK, pitch, NOTE_VELOCITY, NOTE_INSTRUMENT]
            self.current_notes[0].append(note)
            if len(self.current_notes[0]) > MAX_CURRENT_NOTES_NUM:
                self.start_generation_step = True
        else:
            if not self.generating:
                threading.Thread(target=self.generate_continuation, daemon=True).start()
            self.guitar_player.play_notes_in_list()

    def encode_notes_to_tokens(self):
        if self.current_notes:

            enhanced_notes = TMIDIX.augment_enhanced_score_notes(self.current_notes[0], sort_drums_last=True)
            dscore = TMIDIX.delta_score_notes(enhanced_notes)
            dcscore = TMIDIX.chordify_score([d[1:] for d in dscore])
            melody_chords = [18816]

            for i, c in enumerate(dcscore):

                delta_time = c[0][0]
                melody_chords.append(delta_time)

                for e in c:
                    dur = max(1, min(255, e[1]))
                    pat = max(0, min(128, e[5]))
                    ptc = max(1, min(127, e[3]))
                    vel = max(8, min(127, e[4]))
                    velocity = round(vel / 15) - 1
                    pat_ptc = (128 * pat) + ptc
                    dur_vel = (8 * dur) + velocity

                    melody_chords.extend([pat_ptc + 256, dur_vel + 16768])

            return melody_chords
        else:
            return [18816]

    def decode_tokens_to_notes(self, tokens):
        time = 0
        dur = 1
        vel = 90
        pitch = 60
        channel = 0
        patch = 0
        patches = [-1] * 16
        channels = [0] * 16
        channels[9] = 1
        song_f = []
        for ss in tokens:
            if 0 <= ss < 256:
                time += ss * 16
            if 256 <= ss < 16768:
                patch = (ss - 256) // 128
                if patch < 128:
                    if patch not in patches:
                        if 0 in channels:
                            cha = channels.index(0)
                            channels[cha] = 1
                        else:
                            cha = 15
                        patches[cha] = patch
                        channel = patches.index(patch)
                    else:
                        channel = patches.index(patch)
                if patch == 128:
                    channel = 9
                pitch = (ss - 256) % 128
            if 16768 <= ss < 18816:
                dur = ((ss - 16768) // 8) * 16
                vel = (((ss - 16768) % 8) + 1) * 15
                song_f.append(['note', time, dur, channel, pitch, vel, patch])
        patches = [0 if x == -1 else x for x in patches]
        output_score, patches, overflow_patches = TMIDIX.patch_enhanced_score_notes(song_f)
        self.generated_notes = output_score

    def generate_continuation(self):
        self.generating = True
        print("开始生成延续...")
        prime = self.encode_notes_to_tokens()
        model_top_p = MODEL_TOP_P
        model_temperature = MODEL_TEMPERATURE
        num_prime_tokens = NUM_PRIME_TOKENS
        num_gen_tokens = NUM_GEN_TOKENS
        num_gen_batches = NUM_OUT_BATCHES
        if len(prime) >= NUM_PRIME_TOKENS:
            prime = [18816] + prime[-NUM_PRIME_TOKENS:]
        inputs = prime
        inp = torch.LongTensor([inputs] * num_gen_batches).cuda()
        with self.ctx:
            out = self.model.generate(
                inp,
                num_gen_tokens,
                filter_logits_fn=top_p,
                filter_kwargs={'thres': model_top_p},
                temperature=model_temperature,
                eos_token=18818,
                return_prime=False,
                verbose=True
            )
        gen_tokens = out.tolist()[0]
        self.decode_tokens_to_notes(gen_tokens)
        self.current_notes = [self.generated_notes]
        self.guitar_player.add_to_play_list(self.get_generated_notes())
        print("生成完毕...")
        self.generating = False

    def get_generated_notes(self):
        def align_to_grid(time, grid):
            idx = np.abs(grid - time).argmin()
            return grid[idx]
        simplified_generated_notes =  [(generated_note[1] / 1000, generated_note[2] / 1000, generated_note[4]) for generated_note in self.generated_notes]
        start_times = [note[0] for note in simplified_generated_notes]
        intervals = np.diff(sorted(start_times))
        base_interval = np.median(intervals[intervals > 0.1])
        target_interval = base_interval if base_interval <= 1.2 else 0.6
        max_time = max(start_times)
        beat_grid = np.arange(0, max_time + target_interval, target_interval)
        improved_notes = [
            (align_to_grid(start, beat_grid), duration, pitch)
            for start, duration, pitch in simplified_generated_notes
        ]
        for i in range(1, len(improved_notes)):
            prev_end = improved_notes[i - 1][0] + improved_notes[i - 1][1]
            gap = improved_notes[i][0] - prev_end
            if gap > target_interval * 1.5:  #
                # 对齐到下一小节首拍
                improved_notes[i] = (np.ceil(prev_end / (target_interval * 4)) * (target_interval * 4),
                                      improved_notes[i][1],
                                      improved_notes[i][2])
        time_groups = {}
        for note in improved_notes:
            time_groups.setdefault(note[0], []).append(note)
        for time, group in time_groups.items():
            if len(group) > 1:
                avg_time = sum(n[0] for n in group) / len(group)
                for note in group:
                    note = (avg_time, note[1], note[2])
        return improved_notes











