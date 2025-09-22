import gzip
import json
from collections import defaultdict
import pretty_midi
from tqdm import tqdm
import os
from constant_parameters import *

dataset_name = "maestro-v2.0.0"
dataset_file_path = os.path.join("dataset", dataset_name)
dataset_json_file = "maestro-v2.0.0.json"

dataset = defaultdict(list)

with open(os.path.join(dataset_file_path, dataset_json_file), "r") as f:
    for attrs in tqdm(json.load(f)):
        split = attrs["split"]
        filename = attrs["midi_filename"]
        midi = pretty_midi.PrettyMIDI(os.path.join(dataset_file_path, filename))
        if len(midi.instruments) != 1:
            print(f"警告: {filename} 包含多个乐器音轨，跳过处理")
            continue

        notes = [
            (
                max(0.0, float(n.start)),  # 起始时间 ≥0
                max(0.0, float(n.end) - float(n.start)),  # 持续时间 ≥0
                max(0, min(int(n.pitch - LOWEST_KEY_MIDI_PITCH), KEY_NUM - 1)),  # 键位索引
                max(1, min(int(n.velocity), 127)),  # 力度[1,128]
            )
            for n in midi.instruments[0].notes
        ]

        # This list is in sorted order of onset time, i.e., $t_{i-1} \leq t_i ~\forall~i \in \{2, \ldots, N\}$.
        notes = sorted(notes, key=lambda n: (n[0], n[2]))
        dataset[split].append(notes)
with gzip.open(dataset_name + "-simple.json.gz", "w") as f:
    f.write(json.dumps(dataset).encode("utf-8"))