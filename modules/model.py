from typing import NamedTuple

import torch
from torch import nn
from torch.nn import functional as F

from modules.embedding.id_embedder import SemIdEmbedder, UserIdEmbedder
from modules.tokenizer.semids import TokenizedSeqBatch
from modules.transformer.model import TransformerDecoder


class ModelOutput(NamedTuple):
    loss: torch.Tensor


class DecoderRetrievalModel(nn.Module):
    def __init__(self, embedding_dim, d_out, dropout, num_heads, n_layers, num_embeddings, max_pos=2048) -> None:
        super().__init__()
        self.num_embeddings = num_embeddings
        self.sem_id_embedder = SemIdEmbedder(num_embeddings, embedding_dim)
        self.user_id_embedder = UserIdEmbedder(2000, embedding_dim)

        self.wpe = nn.Embedding(num_embeddings=max_pos, embedding_dim=embedding_dim)

        self.decoder = TransformerDecoder(
            d_in=embedding_dim,
            d_out=d_out,
            dropout=dropout,
            num_heads=num_heads,
            n_layers=n_layers,
            do_cross_attn=False,
        )

        self.out_proj = nn.Linear(d_out, num_embeddings)

    def forward(self, batch: TokenizedSeqBatch) -> ModelOutput:
        seq_mask = batch.seq_mask
        user_emb = self.user_id_embedder(batch.user_ids)
        sem_ids_emb = self.sem_id_embedder(batch.sem_ids)

        B, N, D = sem_ids_emb.shape

        pos = torch.arange(N, device=sem_ids_emb.device)
        wpe = self.wpe(pos)

        input_embedding = user_emb.unsqueeze(1) + wpe.unsqueeze(0) + sem_ids_emb
        transformer_output = self.decoder(input_embedding)

        logits = self.out_proj(transformer_output)

        target_mask = seq_mask[:, 1:]
        out = logits[:, :-1, :][target_mask, :]
        target = batch.sem_ids[:, 1:][target_mask]
        loss = F.cross_entropy(out, target)

        return ModelOutput(loss=loss)
