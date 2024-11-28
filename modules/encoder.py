from typing import List

import torch
from torch import nn

from modules.normalize import L2NormalizationLayer


class MLP(nn.Module):
    def __init__(self, input_dim: int, hidden_dims: List[int], out_dim: int, normalize: bool = False) -> None:
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.out_dim = out_dim

        dims = [self.input_dim] + self.hidden_dims + [self.out_dim]

        self.mlp = nn.Sequential()
        for i, (in_d, out_d) in enumerate(zip(dims[:-1], dims[1:])):
            self.mlp.append(nn.Linear(in_d, out_d))
            if i != len(dims) - 2:
                self.mlp.append(nn.SiLU())
        self.mlp.append(L2NormalizationLayer() if normalize else nn.Identity())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        assert x.shape[-1] == self.input_dim, f"Invalid input dim: Expected {self.input_dim}, found {x.shape[-1]}"
        return self.mlp(x)
