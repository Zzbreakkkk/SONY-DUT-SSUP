import gzip
import json
import torch
import torch.nn.functional as F
import pathlib
import random
import numpy as np
from model import PianoGenieAutoencoder, CFG
from constant_parameters import *

with gzip.open("maestro-v2.0.0-simple.json.gz", "rb") as f:
    dataset = json.load(f)

run_dir = pathlib.Path("trained_model")
run_dir.mkdir(exist_ok=True)
with open(pathlib.Path(run_dir, "cfg.json"), "w") as f:
    f.write(json.dumps(CFG, indent=2))

# Set seed
if CFG["seed"] is not None:
    random.seed(CFG["seed"])
    np.random.seed(CFG["seed"])
    torch.manual_seed(CFG["seed"])
    torch.cuda.manual_seed_all(CFG["seed"])

# Create model
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = PianoGenieAutoencoder(CFG)
model.train()
model.to(device)
print("-" * 80)
for n, p in model.named_parameters():
    print(f"{n}, {p.shape}")

# Create optimizer
optimizer = torch.optim.Adam(model.parameters(), lr=CFG["lr"])

# Subsamples performances to create a minibatch
def performances_to_batch(performances, device, train=True):
    batch_k = []
    batch_t = []
    for p in performances:
        # Subsample seq_len notes from performance
        assert len(p) >= CFG["seq_len"]
        if train:
            subsample_offset = random.randrange(0, len(p) - CFG["seq_len"])
        else:
            subsample_offset = 0
        subsample = p[subsample_offset: subsample_offset + CFG["seq_len"]]
        assert len(subsample) == CFG["seq_len"]

        # Data augmentation
        if train:
            stretch_factor = random.random() * CFG["data_augment_time_stretch_max"] * 2
            stretch_factor += 1 - CFG["data_augment_time_stretch_max"]
            transposition_factor = random.randint(
                -CFG["data_augment_transpose_max"], CFG["data_augment_transpose_max"]
            )
            subsample = [
                (
                    n[0] * stretch_factor,
                    n[1] * stretch_factor,
                    max(0, min(n[2] + transposition_factor, KEY_NUM - 1)),
                    n[3],
                )
                for n in subsample
            ]

        # Key features
        batch_k.append([n[2] for n in subsample])

        # Onset features
        # NOTE: For stability, we pass delta time to Piano Genie instead of time.
        t = np.diff([n[0] for n in subsample])
        t = np.concatenate([[1e8], t])
        t = np.clip(t, 0, CFG["data_delta_time_max"])
        batch_t.append(t)

    return (torch.tensor(batch_k).long(), torch.tensor(batch_t).float())


# Train
step = 0
best_eval_loss = float("inf")
while CFG["max_num_steps"] is None or step < CFG["max_num_steps"]:
    if step % CFG["eval_frequency"] == 0:
        model.eval()

        with torch.no_grad():
            eval_losses_recons = []
            eval_violates_contour = []
            for i in range(0, len(dataset["validation"]), CFG["batch_size"]):
                eval_batch = performances_to_batch(
                    dataset["validation"][i: i + CFG["batch_size"]],
                    device,
                    train=False,
                )
                eval_k, eval_t = tuple(t.to(device) for t in eval_batch)
                eval_hat_k, eval_e = model(eval_k, eval_t)
                eval_b = model.quant.real_to_discrete(eval_e)
                eval_loss_recons = F.cross_entropy(
                    eval_hat_k.view(-1, KEY_NUM),
                    eval_k.view(-1),
                    reduction="none",
                )
                eval_violates = torch.logical_not(
                    torch.sign(torch.diff(eval_k, dim=1))
                    == torch.sign(torch.diff(eval_b, dim=1)),
                ).float()
                eval_violates_contour.extend(eval_violates.cpu().numpy().tolist())
                eval_losses_recons.extend(eval_loss_recons.cpu().numpy().tolist())

            eval_loss_recons = np.mean(eval_losses_recons)
            if eval_loss_recons < best_eval_loss:
                torch.save(model.state_dict(), pathlib.Path(run_dir, "model.pt"))
                best_eval_loss = eval_loss_recons

        eval_metrics = {
            "eval_loss_recons": eval_loss_recons,
            "eval_contour_violation_ratio": np.mean(eval_violates_contour),
        }

        print(step, "eval", eval_metrics)

        model.train()

    # Create minibatch
    batch = performances_to_batch(
        random.sample(dataset["train"], CFG["batch_size"]), device, train=True
    )
    k, t = tuple(t.to(device) for t in batch)

    # Run model
    optimizer.zero_grad()
    k_hat, e = model(k, t)

    # Compute losses and update params
    loss_recons = F.cross_entropy(k_hat.view(-1, KEY_NUM), k.view(-1))
    loss_margin = torch.square(
        torch.maximum(torch.abs(e) - 1, torch.zeros_like(e))
    ).mean()
    loss_contour = torch.square(
        torch.maximum(
            1 - torch.diff(k, dim=1) * torch.diff(e, dim=1),
            torch.zeros_like(e[:, 1:]),
        )
    ).mean()
    loss = torch.zeros_like(loss_recons)
    loss += loss_recons
    if CFG["loss_margin_multiplier"] > 0:
        loss += CFG["loss_margin_multiplier"] * loss_margin
    if CFG["loss_contour_multiplier"] > 0:
        loss += CFG["loss_contour_multiplier"] * loss_contour
    loss.backward()
    optimizer.step()
    step += 1

    if step % CFG["summarize_frequency"] == 0:
        metrics = {
            "loss_recons": loss_recons.item(),
            "loss_margin": loss_margin.item(),
            "loss_contour": loss_contour.item(),
            "loss": loss.item(),
        }
        print(step, "train", metrics)
