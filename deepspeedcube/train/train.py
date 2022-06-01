from __future__ import annotations

from dataclasses import dataclass, field

import torch
import torch.optim as optim
import torch.nn as nn
from pelutils import log, thousands_seperators, TT
from pelutils.datastorage import DataStorage
from pelutils.parser import JobDescription
from deepspeedcube import tensor_size

from deepspeedcube.model import Model, ModelConfig
from deepspeedcube.envs import get_env
from deepspeedcube.train.gen_states import gen_new_states
from deepspeedcube.train.generator_network import clone_model, update_generator_network


@dataclass
class TrainConfig(DataStorage, json_name="train_config.json", indent=4):
    env: str
    num_models: int
    batches: int
    batch_size: int
    scramble_depth: int
    lr: float
    tau: float

@dataclass
class TrainResults(DataStorage, json_name="train_results.json", indent=4):
    lr: list[float] = field(default_factory=list)
    losses: list[list[float]] = field(default_factory=list)

def train(job: JobDescription):

    # Args either go into the model config or into the training config
    # Those that go into the training config are filtered out here
    train_cfg = TrainConfig(
        env            = job.env,
        num_models     = job.num_models,
        batches        = job.batches,
        batch_size     = job.batch_size,
        scramble_depth = job.scramble_depth,
        lr             = job.lr,
        tau            = job.tau,
    )
    log("Got training config", train_cfg)

    log("Setting up environment '%s'" % train_cfg.env)
    env = get_env(train_cfg.env)

    log.section("Building models")
    model_cfg = ModelConfig(
        state_size          = env.state_oh_size,
        hidden_layer_sizes  = job.hidden_layer_sizes,
        num_residual_blocks = job.num_residual_blocks,
        residual_size       = job.residual_size,
        dropout             = job.dropout,
    )
    log("Got model config", model_cfg)

    criterion = nn.MSELoss()
    models: list[Model] = list()
    gen_models: list[Model] = list()
    optimizers = list()
    schedulers = list()
    for _ in range(train_cfg.num_models):
        TT.profile("Build model")
        model = Model(model_cfg)
        gen_model = Model(model_cfg)
        clone_model(model, gen_model)
        optimizer = optim.AdamW(model.parameters(), lr=train_cfg.lr)
        scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(optimizer, T_0=100)
        models.append(model)
        gen_models.append(gen_model)
        optimizers.append(optimizer)
        schedulers.append(scheduler)
        TT.end_profile()
    log(
        "Built %i models" % train_cfg.num_models,
        "Parameters per model: %s" % thousands_seperators(models[0].numel()),
        "Total parameters:     %s" % thousands_seperators(sum(m.numel() for m in models)),
    )
    log(models[0])

    log.section("Starting training")
    train_results = TrainResults()
    train_results.losses.extend(list() for _ in range(train_cfg.num_models))

    for i in range(train_cfg.batches):
        TT.profile("Batch")
        log("Batch %i / %i" % (i+1, train_cfg.batches))

        log.debug("Generating %i states" % (train_cfg.batch_size * train_cfg.num_models))
        with TT.profile("Generate scrambled states"):
            all_states = gen_new_states(
                env,
                train_cfg.batch_size * train_cfg.num_models,
                train_cfg.scramble_depth,
            )
        log.debug("Size of all states in bytes: %s" % thousands_seperators(tensor_size(all_states)))

        for j in range(train_cfg.num_models):
            log.debug("Training model %i / %i" % (j+1, train_cfg.num_models))

            model = models[j]
            optimizer = optimizers[j]
            scheduler = schedulers[j]

            log.debug("Generating neighbour states")
            states = all_states[j*train_cfg.batch_size:(j+1)*train_cfg.batch_size]
            neighbour_states = env.neighbours(states)

            log.debug("Forward passing states")
            with TT.profile("OH neighbour states"):
                neighbour_states_oh = env.multiple_oh(neighbour_states)
            assert neighbour_states.is_contiguous() and neighbour_states_oh.is_contiguous()

            with TT.profile("Value estimates"), torch.no_grad():
                # TODO Forward pass only unique and non-solved states
                value_estimates = model(neighbour_states_oh).squeeze()

            with TT.profile("Set solved states to j = 0"):
                solved_states = env.multiple_is_solved(neighbour_states)
                value_estimates[solved_states] = 0
            value_estimates = value_estimates.view(len(states), len(env.action_space))

            with TT.profile("Calculate targets"):
                targets = torch.min(1+value_estimates, dim=1).values

            with TT.profile("OH states"):
                states_oh = env.multiple_oh(states)
            assert states.is_contiguous() and states_oh.is_contiguous()

            with TT.profile("Train model"):
                preds = model(states_oh).squeeze()
                loss = criterion(preds, targets)
                loss.backward()
                log.debug("Loss: %.4f" % loss.item())
                train_results.losses[j].append(loss.item())
                optimizer.step()
                if torch.cuda.is_available():
                    torch.cuda.synchronize()

            if j == 0:
                train_results.lr.append(schedulers[j].get_last_lr()[0])
                log.debug(
                    "Shapes",
                    "states:              %s" % list(states.shape),
                    "states_oh:           %s" % list(states_oh.shape),
                    "neighbour_states:    %s" % list(neighbour_states.shape),
                    "neighbour_states_oh: %s" % list(neighbour_states_oh.shape),
                    "value_estimates:     %s" % list(value_estimates.shape),
                    "targets:             %s" % list(targets.shape),
                    sep="\n    ",
                )
                log.debug(
                    "Sizes in bytes",
                    "states:              %s" % thousands_seperators(tensor_size(states)),
                    "states_oh:           %s" % thousands_seperators(tensor_size(states_oh)),
                    "neighbour_states:    %s" % thousands_seperators(tensor_size(neighbour_states)),
                    "neighbour_states_oh: %s" % thousands_seperators(tensor_size(neighbour_states_oh)),
                    "value_estimates:     %s" % thousands_seperators(tensor_size(value_estimates)),
                    "targets:             %s" % thousands_seperators(tensor_size(targets)),
                    sep="\n    ",
                )

            scheduler.step()

            with TT.profile("Update generator network"):
                update_generator_network(train_cfg.tau, gen_models[j], models[j])
        TT.end_profile()

    log.section("Saving")
    with TT.profile("Save"):
        train_cfg.save(job.location)
        model_cfg.save(job.location)
        train_results.save(job.location)
