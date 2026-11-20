# -*- coding: utf-8 -*-
"""Example 04 (Advanced): Mobile-Safe ConfigStore + Cross-Platform TaskPool."""
from pyaudiogaming.storage import ConfigStore
from pyaudiogaming.worker import TaskPool


def heavy_sum(n):
    return sum(i * i for i in range(n))


def main():
    cfg = ConfigStore("demo_game", defaults={"volume": 80, "level": 1}, portable=True)
    cfg.load()
    cfg["level"] += 1
    cfg.save()
    print("Config:", cfg.to_dict())
    with TaskPool(mode="auto") as pool:
        job = pool.submit(heavy_sum, 200_000, on_done=lambda r: print("Worker result:", r))
        pool.wait(job)


if __name__ == "__main__":
    main()
