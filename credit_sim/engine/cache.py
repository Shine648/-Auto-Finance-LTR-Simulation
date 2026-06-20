"""Simulation result caching with MD5 key hashing."""
import hashlib
import json
import os
import joblib
from typing import Dict, Any, Optional
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / 'data' / 'cache'


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def make_cache_key(params: Dict[str, Any]) -> str:
    """Generate MD5 hash from sorted params dict."""
    raw = json.dumps(params, sort_keys=True, default=str).encode()
    return hashlib.md5(raw).hexdigest()


class SimulationCache:
    """In-memory + disk cache for simulation results."""

    def __init__(self, max_memory: int = 64, use_disk: bool = True):
        self._memory: Dict[str, Any] = {}
        self._max_memory = max_memory
        self._use_disk = use_disk
        self._hit_count = 0
        self._miss_count = 0

    def get(self, key: str) -> Optional[Any]:
        """Get cached result. Checks memory first, then disk."""
        # Memory check
        if key in self._memory:
            self._hit_count += 1
            return self._memory[key]

        # Disk check
        if self._use_disk:
            _ensure_cache_dir()
            disk_path = CACHE_DIR / f"{key}.joblib"
            if disk_path.exists():
                try:
                    result = joblib.load(disk_path)
                    self._memory[key] = result  # promote to memory
                    self._hit_count += 1
                    self._prune_memory()
                    return result
                except Exception:
                    pass

        self._miss_count += 1
        return None

    def set(self, key: str, result: Any):
        """Store result in memory and optionally on disk."""
        self._memory[key] = result
        self._prune_memory()

        if self._use_disk:
            _ensure_cache_dir()
            disk_path = CACHE_DIR / f"{key}.joblib"
            try:
                joblib.dump(result, disk_path)
            except Exception:
                pass

    def _prune_memory(self):
        """Keep memory cache within limit by removing oldest entries."""
        while len(self._memory) > self._max_memory:
            # Remove first (oldest) key
            first_key = next(iter(self._memory))
            del self._memory[first_key]

    def clear(self):
        """Clear memory cache."""
        self._memory.clear()

    def clear_disk(self):
        """Clear disk cache."""
        if CACHE_DIR.exists():
            import shutil
            shutil.rmtree(CACHE_DIR)

    @property
    def stats(self) -> Dict:
        return {
            'memory_entries': len(self._memory),
            'hit_count': self._hit_count,
            'miss_count': self._miss_count,
            'hit_rate': self._hit_count / max(self._hit_count + self._miss_count, 1),
        }

    def get_cache_key_for_scenario(self, method: str, gdp: float, unemp: float,
                                     house: float, n_sim: int,
                                     **extra) -> str:
        """Build a cache key from simulation parameters."""
        params = {
            'method': method,
            'gdp_growth': round(gdp, 4),
            'unemployment': round(unemp, 4),
            'house_price_change': round(house, 4),
            'n_simulations': n_sim,
            'seed': 42,  # fixed seed ensures reproducibility
        }
        params.update(extra)
        return make_cache_key(params)