#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data/*.json 을 읽고 쓴다. 로스터를 건드리는 스크립트는 전부 여기를 지난다.

카드 자료는 예전에 play.html 안에 자바스크립트 배열로 박혀 있었다. 그때는
스크립트마다 정규식으로 그 배열을 뜯어 읽었는데, 뜯는 방식이 조금씩 달라
같은 파일을 두고 서로 다른 것을 보는 일이 있었다. 지금은 자료가 data/ 에
있고 읽는 길은 여기 하나다.

레코드 꼴과 자리배열 꼴을 둘 다 낸다. 게임 규칙 쪽 코드는 아직 자리번호로
읽으므로(m[7] 은 계열) rows() 가 그 꼴을 만들어 준다.
"""
import json
import os

DIR = "data"
KINDS = ["mech", "pilot", "ship", "crew"]
STAT_N = 4


def path(name):
    return os.path.join(DIR, name if name.endswith(".json") else name + ".json")


def read(name):
    with open(path(name), encoding="utf-8") as f:
        return json.load(f)


def cards(kind):
    """레코드 꼴 — 카드 하나가 사전 하나."""
    return read(kind)["cards"]


def row(c, kind):
    """자리배열 꼴 — play.html 이 예전에 들고 있던 그 차례.

    기체만 뒤에 형식번호(9)와 지형 적성(10)이 붙는다. serAll 이 뒤에서부터
    배열을 찾아 시리즈를 잡으므로, 문자열과 사전은 그 자리를 가리지 않는다."""
    r = [c["name"], c["factions"]] + list(c["stats"]) + [c["temper"]]
    if kind == "mech":
        return r + [c["system"], c["series"], c.get("models", ""), c.get("terrain")]
    if kind == "pilot":
        return r + [c["psy"], c["series"], c.get("line", "")]
    return r + [c["series"]]


def rows(kind):
    return [row(c, kind) for c in cards(kind)]


def bonds():
    return read("bond")["bonds"]


def combos():
    return read("combo")["combos"]


def img():
    return read("img")["img"]


def series():
    return read("series")


def weights():
    """이름 → 드래프트 비중. 안 적힌 카드는 1.0 이다."""
    out = {}
    for k in KINDS:
        for c in cards(k):
            if c.get("weight", 1.0) != 1.0:
                out[c["name"]] = c["weight"]
    return out


def lore():
    out = {}
    for k in KINDS:
        for c in cards(k):
            if c.get("lore"):
                out[c["name"]] = c["lore"]
    return out


def _render(obj):
    """build-data.py 와 같은 모양으로 쓴다 — 카드 하나가 한 줄."""
    def one(v):
        return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))

    def val(v, pad):
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return "[\n" + ",\n".join(pad + " " + one(x) for x in v) + "\n" + pad + "]"
        if isinstance(v, dict) and len(v) > 8:
            return ("{\n" + ",\n".join('%s "%s": %s' % (pad, k, val(x, pad + " "))
                                       for k, x in v.items()) + "\n" + pad + "}")
        return one(v)

    return "{\n" + ",\n".join(' "%s": %s' % (k, val(v, " "))
                              for k, v in obj.items()) + "\n}\n"


def write(name, obj):
    open(path(name), "w", encoding="utf-8").write(_render(obj))


def put_cards(kind, cs):
    """카드 목록만 갈아 끼우고 머리말은 그대로 둔다."""
    d = read(kind)
    d["cards"] = cs
    d["count"] = len(cs)
    write(kind, d)


def index():
    """이름 → (종류, 레코드). 이름은 네 종류를 통틀어 유일하다."""
    out = {}
    for k in KINDS:
        for c in cards(k):
            out[c["name"]] = (k, c)
    return out
