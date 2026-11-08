"""SAC con temperatura automatica. Hiperparametros de la tabla 7 del articulo.

Solo cambia el ancho oculto del actor entre arquitecturas: el critico no se despliega y queda 256-256 en ambas,
para que la diferencia medida venga del actor.
"""
import copy

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

LOG_STD_MIN, LOG_STD_MAX = -5.0, 2.0
LOG_2PI = float(np.log(2 * np.pi))


class Actor(nn.Module):
    def __init__(self, hidden, obs_dim=36, act_dim=12):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(obs_dim, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU())
        self.mu = nn.Linear(hidden, act_dim)
        self.log_std = nn.Linear(hidden, act_dim)

    def init_output(self, action, log_std=-1.0, limit=0.95):
        """Arranca cerca de una accion dada: la formula q_ref pone la rodilla a -75 grados con a=0."""
        with torch.no_grad():
            self.mu.weight.mul_(0.01)
            self.mu.bias.copy_(torch.atanh(torch.as_tensor(np.clip(action, -limit, limit), dtype=torch.float32)))
            self.log_std.weight.mul_(0.01)
            self.log_std.bias.fill_(log_std)

    def forward(self, obs):
        h = self.net(obs)
        return self.mu(h), self.log_std(h).clamp(LOG_STD_MIN, LOG_STD_MAX)

    def sample(self, obs):
        # Gaussiana escrita a mano: torch.distributions sincroniza al validar y eso rompe la captura en CUDA Graph.
        mu, log_std = self(obs)
        eps = torch.randn_like(mu)
        a = torch.tanh(mu + log_std.exp() * eps)
        logp = -0.5 * eps.pow(2) - log_std - 0.5 * LOG_2PI - torch.log(1 - a.pow(2) + 1e-6)
        return a, logp.sum(-1, keepdim=True)

    def deterministic(self, obs):
        return torch.tanh(self(obs)[0])


def _q_net(obs_dim, act_dim, hidden):
    return nn.Sequential(nn.Linear(obs_dim + act_dim, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))


class Replay:
    """Buffer completo en el dispositivo: evita una copia CPU a GPU por actualizacion."""

    def __init__(self, size, obs_dim, act_dim, device):
        self.size, self.ptr, self.full = size, 0, False
        self.count = torch.zeros((), device=device)  # tensor: el muestreo vive dentro del grafo capturado
        self.s = torch.zeros(size, obs_dim, device=device)
        self.a = torch.zeros(size, act_dim, device=device)
        self.r = torch.zeros(size, 1, device=device)
        self.s2 = torch.zeros(size, obs_dim, device=device)
        self.d = torch.zeros(size, 1, device=device)

    def add_batch(self, s, a, r, s2, d):
        n = len(s)
        idx = (self.ptr + torch.arange(n, device=self.s.device)) % self.size
        self.s[idx], self.a[idx], self.r[idx], self.s2[idx], self.d[idx] = s, a, r, s2, d
        self.full = self.full or self.ptr + n >= self.size
        self.ptr = (self.ptr + n) % self.size
        self.count.fill_(len(self))

    def __len__(self):
        return self.size if self.full else self.ptr

    def sample(self, batch):
        i = (torch.rand(batch, device=self.s.device) * self.count).long()
        return self.s[i], self.a[i], self.r[i], self.s2[i], self.d[i]


class SAC:
    def __init__(self, actor_hidden, device, critic_hidden=256, lr=3e-4, tau=0.005, gamma=0.99, obs_dim=36, act_dim=12):
        self.device, self.tau, self.gamma, self.target_entropy = device, tau, gamma, -float(act_dim)
        self.actor = Actor(actor_hidden, obs_dim, act_dim).to(device)
        self.q1, self.q2 = (_q_net(obs_dim, act_dim, critic_hidden).to(device) for _ in range(2))
        self.q1_t, self.q2_t = copy.deepcopy(self.q1), copy.deepcopy(self.q2)
        self.log_alpha = torch.zeros(1, device=device, requires_grad=True)
        fused = str(device).startswith("cuda")
        self.opt_a = torch.optim.Adam(self.actor.parameters(), lr=lr, fused=fused, capturable=fused)
        self.opt_q = torch.optim.Adam([*self.q1.parameters(), *self.q2.parameters()], lr=lr, fused=fused, capturable=fused)
        self.opt_t = torch.optim.Adam([self.log_alpha], lr=lr, fused=fused, capturable=fused)
        self.graph = None

    @torch.no_grad()
    def act(self, obs):
        return self.actor.sample(torch.as_tensor(obs, device=self.device))[0].cpu().numpy()

    def update(self, replay, batch=256):
        """En CUDA replica un grafo capturado: lanzar ~100 kernels sueltos cuesta 17 ms en Windows."""
        if not str(self.device).startswith("cuda"):
            return self._step(replay, batch)
        if self.graph is None:
            for _ in range(3):  # calentar en el mismo stream: en un stream lateral backward rompe la captura
                self._step(replay, batch)
            torch.cuda.synchronize()
            self.graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(self.graph, capture_error_mode="thread_local"):
                self._step(replay, batch)
        self.graph.replay()

    def _step(self, replay, batch):
        s, a, r, s2, d = replay.sample(batch)
        alpha = self.log_alpha.exp().detach()
        with torch.no_grad():
            a2, lp2 = self.actor.sample(s2)
            sa2 = torch.cat([s2, a2], 1)
            y = r + (1 - d) * self.gamma * (torch.min(self.q1_t(sa2), self.q2_t(sa2)) - alpha * lp2)
        sa = torch.cat([s, a], 1)
        q_loss = F.mse_loss(self.q1(sa), y) + F.mse_loss(self.q2(sa), y)
        self.opt_q.zero_grad(set_to_none=False)
        q_loss.backward()
        self.opt_q.step()

        pa, lp = self.actor.sample(s)
        spa = torch.cat([s, pa], 1)
        a_loss = (alpha * lp - torch.min(self.q1(spa), self.q2(spa))).mean()
        self.opt_a.zero_grad(set_to_none=False)
        a_loss.backward()
        self.opt_a.step()

        t_loss = -(self.log_alpha * (lp.detach() + self.target_entropy)).mean()
        self.opt_t.zero_grad(set_to_none=False)
        t_loss.backward()
        self.opt_t.step()

        with torch.no_grad():
            for net, tgt in ((self.q1, self.q1_t), (self.q2, self.q2_t)):
                torch._foreach_lerp_(list(tgt.parameters()), list(net.parameters()), self.tau)
