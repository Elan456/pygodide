import json


def load_waves() -> dict:
    with open("data/configs/waves.json", encoding="utf-8") as handle:
        return json.load(handle)


def load_title() -> str:
    with open("data/strings/title.txt", encoding="utf-8") as handle:
        return handle.read().strip()
