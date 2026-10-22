"""The explicitly supported wheel targets."""
import json
import os
from pathlib import Path


def get_target(name=None):
    name = name or os.environ.get('BUILD_TARGET', 'cp310-aarch64')
    targets = json.loads(Path(__file__).with_name('toolchain.json').read_text())
    if name not in targets:
        raise ValueError(f'Unsupported wheel target: {name}')
    return {'id': name, **targets[name]}


def wheel_tag(target):
    return f"{target['python_tag']}-{target['python_tag']}-{target['platform']}"


def artifact_suffix(target):
    return target["python_tag"] + "-" + target["platform"].replace("_", "-", 3)
