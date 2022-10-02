from __future__ import annotations

import os
from argparse import ArgumentParser

import matplotlib.pyplot as plt
import numpy as np
import pelutils.ds.plots as plots
import torch
from tqdm import tqdm
from scipy.stats.mstats import mquantiles

from deepspeedcube import device
from deepspeedcube.envs import get_env
from deepspeedcube.eval.load_hard_cube_states import load_hard_and_intermediate_states
from deepspeedcube.model import Model, ModelConfig
from deepspeedcube.train.train import TrainConfig


env = get_env("cube")

@torch.no_grad()
def value_correlations(out: str, qtm_datafile: str, model_names: list[str], model_sets: list[list[Model]]):

    states = load_hard_and_intermediate_states(qtm_datafile)[-1]
    states_d = states.to(device)
    states_oh = env.multiple_oh(states_d)

    with plots.Figure(f"{out}/value-correlations-24.png"):
        preds = np.zeros((2, len(states)))
        for i, (model_name, model_set) in tqdm(enumerate(zip(model_names, model_sets)), total=len(model_sets)):
            for model in model_set:
                preds[i] += model(states_oh).squeeze().cpu().numpy()
            preds[i] = preds[i] / len(model_set)

        plt.scatter(*preds)
        plt.gca().set_aspect("equal")

        plt.xlabel(model_names[0])
        plt.ylabel(model_names[1])
        plt.grid()

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("qtm")
    parser.add_argument("-m", "--model-dirs", nargs=2)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    model_sets = list()
    for model_dir in args.model_dirs:
        train_cfg = TrainConfig.load(model_dir)
        model_cfg = ModelConfig.load(model_dir)
        model_set = list()
        for i in range(train_cfg.num_models):
            model = Model(model_cfg).to(device)
            model.load_state_dict(torch.load(
                f"{model_dir}/model-{i}.pt",
                map_location=device,
            ))
            model.eval()
            model_set.append(model)
        model_sets.append(model_set)

    value_correlations(
        args.out,
        args.qtm,
        [os.path.split(x)[-1] for x in args.model_dirs],
        model_sets,
    )