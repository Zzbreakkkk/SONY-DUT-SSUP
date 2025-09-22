import torch
import torch.nn.functional as F
import json
from model import PianoGenieAutoencoder
from constant_parameters import *

DELTA_TIME_MAX = 1
SOS = KEY_NUM
DEFAULT_TEMPERATURE = 0.25

def sample_from_logits(logits, temperature=DEFAULT_TEMPERATURE, seed=None):
    if temperature < 0 or temperature > 1:
        raise ValueError("Temperature must be in [0, 1]")

    if temperature == 0:
        return torch.argmax(logits, dim=-1)
    else:
        # 温度缩放
        scaled_logits = logits / temperature

        # 多类别采样
        probs = F.softmax(scaled_logits, dim=-1)
        distribution = torch.distributions.Categorical(probs)
        sample = distribution.sample()
        return sample

class GuitarGenie:

    def __init__(self, model_path, cfg_path):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        with open(cfg_path, "r") as f:
            self.cfg = json.load(f)
        self.model = PianoGenieAutoencoder(self.cfg)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        self.dec = self.model.dec
        self.quant = self.model.quant
        self.last_time = None
        self.last_key = None
        self.last_hidden = None

        print("Guitar Genie Model成功加载")

    def reset(self):
        self.last_time = None
        self.last_key = None
        self.last_hidden = None

    def press(self, time, input, temperature=DEFAULT_TEMPERATURE):
        # 输入验证
        input = max(0, min(input, NUM_BUTTONS))
        # 计算时间差
        delta_time = DELTA_TIME_MAX if self.last_time is None else time - self.last_time
        delta_time = min(max(delta_time, 0), DELTA_TIME_MAX)
        # 准备输入
        last_key = SOS if self.last_key is None else self.last_key
        last_hidden = self.last_hidden
        # 执行模型推理
        k_prev = torch.tensor([[last_key]], dtype=torch.int64, device=self.device)
        delta_t = torch.tensor([[delta_time]], dtype=torch.float32, device=self.device)
        input_i = torch.tensor([[input]], dtype=torch.int64, device=self.device)
        input_i = self.quant.discrete_to_real(input_i)
        # 模型前向传播
        hatki, hidden = self.dec(k_prev, delta_t, input_i, last_hidden)
        # 采样输出
        key = sample_from_logits(torch.squeeze(hatki), temperature).item()
        # 更新状态
        self.last_time = time
        self.last_key = key
        self.last_hidden = hidden
        pitch = key + LOWEST_KEY_MIDI_PITCH
        return pitch

































