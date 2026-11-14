"""Download the 40 CWRU .mat files (12 kHz drive end, 10 classes x 4 loads) and check them."""
import _bootstrap  # noqa: F401
import argparse
import os
import time

from irf_repro.config import load_config, save_json
from irf_repro.cwru import file_table, load_de_signal


def download(url, dest, retries=4):
    import requests

    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                tmp = dest + ".part"
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                os.replace(tmp, dest)
                return
        except Exception as exc:
            print(f"  attempt {attempt} failed: {exc}")
            time.sleep(3 * attempt)
    raise RuntimeError(f"could not download {url}; download it manually into {os.path.dirname(dest)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    out_dir = cfg["paths"]["raw_mat_dir"]
    inventory = []
    for row in file_table(cfg["data"]["loads_hp"]):
        dest = os.path.join(out_dir, f"{row['file_id']}.mat")
        if args.force or not os.path.exists(dest):
            print(f"downloading {row['url']}")
            download(row["url"], dest)
        sig = load_de_signal(dest, row["file_id"])
        inventory.append({**row, "n_samples": int(sig.size), "bytes": os.path.getsize(dest)})
        print(f"  {row['class_name']:<8} load={row['load']} file={row['file_id']:<4} samples={sig.size}")
    save_json(inventory, os.path.join(cfg["paths"]["results_dir"], "cwru_inventory.json"))
    print(f"{len(inventory)} files ready, {sum(r['bytes'] for r in inventory) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
