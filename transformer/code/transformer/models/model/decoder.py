"""
@author : Hyunwoong
@when : 2019-12-18
@homepage : https://github.com/gusdnd852
"""
import torch
from torch import nn

from models.blocks.decoder_layer import DecoderLayer
from models.embedding.transformer_embedding import TransformerEmbedding


class Decoder(nn.Module):
    def __init__(self, dec_voc_size, max_len, d_model, ffn_hidden, n_head, n_layers, drop_prob, device):
        super().__init__()
        self.emb = TransformerEmbedding(d_model=d_model,
                                        drop_prob=drop_prob,
                                        max_len=max_len,
                                        vocab_size=dec_voc_size,
                                        device=device)

        self.layers = nn.ModuleList([DecoderLayer(d_model=d_model,
                                                  ffn_hidden=ffn_hidden,
                                                  n_head=n_head,
                                                  drop_prob=drop_prob)
                                     for _ in range(n_layers)])

        self.linear = nn.Linear(d_model, dec_voc_size)

    def forward(self, trg, enc_src, trg_mask, src_mask, use_cache, cache):
        # token embedding + positional encoding，在训练时，trg是已知的输出
        trg = self.emb(trg)
        if cache is not None:
            cache_dict = cache
        else:
            cache_dict = {}
        for i, layer in enumerate(self.layers):
            if use_cache:
                trg, cache_dict[i] = layer(trg, enc_src, trg_mask, src_mask, use_cache, cache_dict.get(i))
            else:
                trg = layer(trg, enc_src, trg_mask, src_mask, use_cache, cache)

        # pass to LM head
        output = self.linear(trg)
        if use_cache:
            return output, cache_dict
        else:
            return output
