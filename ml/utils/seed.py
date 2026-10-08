"""Seed every random number generator used in training."""
from __future__ import annotations

import os
import random

import numpy as np
import torch


def seed_everything(seed: int, deterministic: bool = True) -> int:
    """Seed Python, NumPy and PyTorch (CPU and CUDA) and set the CUDNN flags.

    With ``deterministic=True`` CUDNN picks reproducible algorithms and benchmarking is
    off, which can make training slower. Returns the seed.
    """
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = deterministic
    torch.backends.cudnn.benchmark = not deterministic
    return seed
