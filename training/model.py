"""Unchanged Tiny-2.1 Transformer and per-row int8 exporter (MIT)."""
import math, os, struct
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from tokenizer import VOCAB
CTX = 128

class Cfg:
    def __init__(self, D=96, L=4, H=4, HID=256):
        self.D, self.L, self.H, self.HID = D, L, H, HID

    def __repr__(self):
        return 'D=%d L=%d H=%d HID=%d' % (self.D, self.L, self.H, self.HID)


class Norm(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.g = nn.Parameter(torch.ones(d))

    def forward(self, x):
        return x * torch.rsqrt(x.float().pow(2).mean(-1, keepdim=True) + 1e-5).to(x.dtype) * self.g


class Block(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.c = c
        self.n1, self.n2 = Norm(c.D), Norm(c.D)
        self.q = nn.Linear(c.D, c.D, bias=False)
        self.k = nn.Linear(c.D, c.D, bias=False)
        self.v = nn.Linear(c.D, c.D, bias=False)
        self.o = nn.Linear(c.D, c.D, bias=False)
        self.f1 = nn.Linear(c.D, c.HID, bias=False)
        self.f2 = nn.Linear(c.HID, c.D, bias=False)

    def forward(self, x):
        B, T, D = x.shape
        H = self.c.H
        h = self.n1(x)
        sp = lambda t: t.view(B, T, H, D // H).transpose(1, 2)
        a = F.scaled_dot_product_attention(sp(self.q(h)), sp(self.k(h)), sp(self.v(h)), is_causal=True)
        x = x + self.o(a.transpose(1, 2).reshape(B, T, D))
        return x + self.f2(F.relu(self.f1(self.n2(x))))


class Model(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.c = c
        self.emb = nn.Embedding(VOCAB, c.D)
        self.pos = nn.Embedding(CTX, c.D)
        self.blocks = nn.ModuleList([Block(c) for _ in range(c.L)])
        self.nf = Norm(c.D)
        nn.init.normal_(self.emb.weight, std=0.05)
        nn.init.normal_(self.pos.weight, std=0.05)
        for b in self.blocks:
            for m in (b.q, b.k, b.v, b.o, b.f1, b.f2):
                nn.init.normal_(m.weight, std=0.5 / math.sqrt(m.in_features))

    def forward(self, idx):
        x = self.emb(idx) + self.pos(torch.arange(idx.shape[1]))
        for b in self.blocks:
            x = b(x)
        return self.nf(x) @ self.emb.weight.t()


def export(model, path):
    """Version-2 weight file. Header: 'TNY2', D, L, H, HID (int16 each).
    Each table: rows x (float32 scale + cols int8)  (one scale per row).
    Gains: D float32."""
    c = model.c
    sd = {k: v.float() for k, v in model.state_dict().items()}
    with open(path, 'wb') as f:
        f.write(b'TNY2' + struct.pack('<4h', c.D, c.L, c.H, c.HID))

        def table(w):
            w = w.numpy()
            for row in w:
                s = max(float(np.abs(row).max()) / 127.0, 1e-8)
                f.write(struct.pack('<f', s))
                f.write(np.clip(np.round(row / s), -127, 127).astype(np.int8).tobytes())

        def gains(g):
            f.write(g.numpy().astype('<f4').tobytes())

        table(sd['emb.weight'])
        table(sd['pos.weight'])
        for i in range(c.L):
            p = 'blocks.%d.' % i
            gains(sd[p + 'n1.g'])
            for n in 'qkvo':
                table(sd[p + n + '.weight'])
            gains(sd[p + 'n2.g'])
            table(sd[p + 'f1.weight'])
            table(sd[p + 'f2.weight'])
        gains(sd['nf.g'])
    return os.path.getsize(path)


def quantized_copy(model):
    """The same model with weights rounded exactly as export() does."""
    m = Model(model.c)
    m.load_state_dict(model.state_dict())
    with torch.no_grad():
        for n, p in m.named_parameters():
            if p.dim() == 2:
                s = (p.abs().amax(1, keepdim=True) / 127.0).clamp_min(1e-8)
                p.copy_(torch.clamp(torch.round(p / s), -127, 127) * s)
    return m
