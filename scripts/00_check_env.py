"""Record the hardware/software environment (results/environment.json)."""
import _bootstrap  # noqa: F401
import os
import platform
import subprocess
import sys

from irf_repro.config import load_config, save_json


def cpu_model():
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def ram_gb():
    try:
        with open("/proc/meminfo") as fh:
            kb = int(fh.readline().split()[1])
        return round(kb / 1024 ** 2, 1)
    except OSError:
        return None


def java_version():
    try:
        out = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr
        return [l for l in out.splitlines() if "version" in l][0].strip()
    except Exception as exc:
        return f"not found ({exc})"


def pkg(name):
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", "installed")
    except Exception:
        return "missing"


def main():
    cfg = load_config()
    env = {
        "os": platform.platform(),
        "kernel": platform.release(),
        "cpu": cpu_model(),
        "logical_cores": os.cpu_count(),
        "ram_gb_visible": ram_gb(),
        "python": sys.version.split()[0],
        "java": java_version(),
        "pyspark": pkg("pyspark"),
        "numpy": pkg("numpy"),
        "pandas": pkg("pandas"),
        "pyarrow": pkg("pyarrow"),
        "scipy": pkg("scipy"),
        "pywt": pkg("pywt"),
        "sklearn": pkg("sklearn"),
        "spark_driver_memory": cfg["spark"]["driver_memory"],
    }
    try:
        import pyspark  # noqa: F401
        from irf_repro.spark_jobs import make_spark
        spark = make_spark(cfg, cores=2, app="env-check")
        env["spark_runtime"] = spark.version
        env["spark_smoke_test"] = spark.range(1000).selectExpr("sum(id) AS s").first()["s"] == 499500
        spark.stop()
    except Exception as exc:
        env["spark_smoke_test"] = f"FAILED: {exc!r}"
    save_json(env, os.path.join(cfg["paths"]["results_dir"], "environment.json"))
    for k, v in env.items():
        print(f"{k:22s}: {v}")


if __name__ == "__main__":
    main()
