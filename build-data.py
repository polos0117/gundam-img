#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기체 카드에 형식번호(models)와 G 제네레이션 이터널 id(gge)를 붙인다.

카드 자료는 data/*.json 에 있다. 이 스크립트는 거기에 바깥 자료를 얹는
일만 한다 — 능력치나 이름은 건드리지 않는다.

형식번호가 왜 필요한가. 예전에는 카드를 이름으로만 구분해서, 표기가 한 글자
갈리면 같은 기체가 두 장이 됐다. 건담 칼리번/캘리번, 건담 DX/더블 엑스,
V건담/빅토리 건담 처럼 열 장이 그렇게 생겼다. 형식번호가 있으면 이름이
아무리 달라도 LM312V04 하나로 같은 기체임이 드러난다.

출처는 둘이다.
  공식 사이트 상세 (official/pilot/relations.json)  — 배리에이션까지 구분해 적는다
  소샤지 G 제네레이션 API (id-map.json)             — 수록 범위가 넓다
둘이 엇갈리면 공식을 따른다. 공식이 여러 카드를 한 항목에 몰아 적은 자리에서는
소샤지가 더 정확하므로, 그런 자리는 data-overrides.json 에 사람이 적어 둔다.

사용법:
    python3 build-data.py            # data/mech.json · pilot.json 을 고친다
    python3 build-data.py --check    # 쓰지 않고 달라지는 것만 보여준다
    python3 build-data.py --report   # 두 출처가 엇갈리는 자리를 전부 찍는다
"""
import argparse
import collections
import importlib.util
import json
import os
import re
import statistics

import roster
from gundam_match import norm, affixes

OVERRIDES = "data-overrides.json"

# ── 소샤지 태그 중 남길 것 ─────────────────────────────────────────────
# 100 종 가운데 대부분은 버린다. 시리즈·진영 태그는 카드가 이미 series 와
# factions 로 들고 있어 겹치고, 돌파력·일격필살·견고 같은 것은 G 제네레이션
# 전투 안에서만 뜻이 있는 값이라 여기 가져와도 가리키는 데가 없다.
# 남기는 것은 '이 기체가 작품에서 어떤 자리에 있었나' 를 말해 주는 것들이다.
TAG_MECH = {
    # 자리
    "주인공", "라이벌", "에이스기", "지휘관기", "전용기", "양산기", "시작기",
    # 형태
    "가변기", "모빌아머", "탱크", "대형기", "공중용", "지상용", "수중용", "모노아이",
    # 색 — 게임은 흰·빨강·검정·금 넷으로만 나눈다. 저장소의 color 보다 거칠다
    "흰색", "빨간색", "검은색", "금색",
    # 계통 — 저장소의 system 과 겹치는 데가 있어 대조에 쓸 수 있다
    "사이코뮤", "뉴타입 전용기", "NT-D", "제로 시스템", "플래시 시스템",
    "모빌 트레이스 시스템", "아라야식 시스템", "아라야식 Type E", "AGE 시스템",
    "건드 암", "신경 접속 시스템", "나노스킨", "리유즈 사이코 디바이스", "ALICE",
    # 혈통
    "건담", "짐", "자쿠",
}
TAG_PILOT = {
    "주인공", "라이벌", "군인", "용병", "민간인", "루키", "베테랑", "리더", "마스크",
    "건담 파일럿", "모노아이 파일럿", "모빌아머 파일럿", "가변기 파일럿",
    "뉴타입", "코디네이터", "X라운더", "신체 강화", "가희",
}
# 지형 적성 — 1 부적합 · 2 보통 · 3 적합
TERRAIN = {"space": "우주", "atmospheric": "대기권", "ground": "지상",
           "surface": "수상", "underwater": "수중"}

IDMAP = "id-map.json"
CACHE = ".cache/soshage"
REL = "official/pilot/relations.json"


def index(names):
    """이름 → 카드 이름. build-bond 와 같은 규칙을 쓴다."""
    idx = {}
    for n in names:
        idx.setdefault(norm(n), n)
    for n in names:
        for v in affixes(norm(n)):
            idx.setdefault(v, n)
    return idx


def clean(m):
    """소샤지는 형식번호가 없는 기체에 '-' 를 넣어 둔다. 그건 값이 아니다."""
    m = (m or "").strip()
    return m if m.strip("-—–·. ") else ""


def from_soshage():
    if not os.path.exists(IDMAP):
        return {}, {}, {}
    d = json.load(open(IDMAP, encoding="utf-8"))
    return ({e["dex"]: clean(e.get("models")) for e in d["mech"] if clean(e.get("models"))},
            {e["dex"]: e["ids"] for e in d["mech"] if e.get("ids")},
            {e["dex"]: e["ids"] for e in d["pilot"] if e.get("ids")})


def api(entity):
    """build-idmap.py 가 받아 둔 캐시를 그대로 읽는다."""
    p = os.path.join(CACHE, entity + ".json")
    if not os.path.exists(p):
        return {}
    return {x["id"]: x for x in json.load(open(p, encoding="utf-8"))}


def base_of(ids, rec):
    """한 카드에 통상판과 (EX) 판이 같이 붙는다. 기체 자체를 말하는 건 통상판이다."""
    here = [rec[i] for i in ids if i in rec]
    plain = [x for x in here if "(EX)" not in x["name"]]
    return (plain or here or [None])[0]


def extras(ids, rec, keep):
    """레어도·지형은 통상판에서, 태그는 판을 통틀어 모은다."""
    b = base_of(ids, rec)
    if not b:
        return {}
    out = {"rarity": b["rarity"]}
    if b.get("terrain"):
        out["terrain"] = {v: b["terrain"][k] for k, v in TERRAIN.items()}
    if b.get("area") == 2:
        out["large"] = True
    tags = set()
    for i in ids:
        for t in rec.get(i, {}).get("tags") or []:
            n = t["tag"]["name"]
            if n in keep:
                tags.add(n)
    if tags:
        out["tags"] = sorted(tags)
    return out


def from_official(idx):
    """공식 상세의 형식번호를 카드 이름으로 옮긴다."""
    if not os.path.exists(REL):
        return {}
    spec = importlib.util.spec_from_file_location("_bb", "build-bond.py")
    bb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bb)
    out = {}
    for ms in json.load(open(REL, encoding="utf-8")).values():
        for oname, e in ms.items():
            if not clean(e.get("models")):
                continue
            d = bb.find_mech(oname, idx)
            if d:
                out.setdefault(d, clean(e["models"]))
    return out


def fill_terrain(mech, override=None):
    """지형 적성이 없는 카드를 메운다.

    소샤지에 실린 466 기는 그쪽 값을 쓰고, 나머지 322 기는 세 단계로 메운다.
    형식번호가 같은 카드 → 이름 계보가 이어지는 카드 → 계열 중앙값.

    계열 중앙값이 그럴듯한 것은 실제로 갈리기 때문이다. UC 계열(양산·시작기·
    사이코뮤)은 대기권 1 이라 날지 못하고, GN드라이브·핵동력·GUND 는 대기권 3 이다.
    작품이 바뀌면서 기체가 날게 된 것이 수치에 그대로 남아 있다.

    메운 카드에는 terrain_src 를 남긴다. 아는 값과 지어낸 값은 구분해 두어야 한다."""
    known = [c for c in mech if "terrain" in c]
    if not known:
        return {}
    axes = list(TERRAIN.values())
    by_model, by_name = {}, {}
    for c in known:
        if c.get("models"):
            by_model.setdefault(re.sub(r"[^a-z0-9]", "", c["models"].lower()), c["terrain"])
        by_name[c["name"]] = c["terrain"]
    by_system = {}
    for sys_ in {c["system"] for c in known}:
        rows = [c["terrain"] for c in known if c["system"] == sys_]
        by_system[sys_] = {k: int(statistics.median(t[k] for t in rows)) for k in axes}
    whole = {k: int(statistics.median(c["terrain"][k] for c in known)) for k in axes}

    src = collections.Counter()
    for c in mech:
        if c["name"] in (override or {}):
            c["terrain"], c["terrain_src"] = dict(override[c["name"]]), "사람"
            src["사람"] += 1
            continue
        if "terrain" in c:
            src["gge"] += 1
            c.pop("terrain_src", None)
            continue
        got = how = None
        key = re.sub(r"[^a-z0-9]", "", (c.get("models") or "").lower())
        if key and key in by_model:
            got, how = by_model[key], "형식번호"
        if not got:
            kin = [n for n in by_name
                   if len(n) >= 3 and n != c["name"]
                   and (c["name"].startswith(n) or n.startswith(c["name"]))]
            if kin:
                got, how = by_name[sorted(kin, key=len)[-1]], "이름"
        if not got:
            got, how = by_system.get(c["system"], whole), "계열"
        c["terrain"], c["terrain_src"] = dict(got), how
        src[how] += 1
    return src


def crosscheck(mech, pilot):
    """새로 들어온 태그와 손으로 적어 둔 값이 어긋나는 곳을 짚는다.

    고치지는 않는다. 소샤지 태그는 게임이 편하려고 거칠게 나눈 것이라
    (색이 흰·빨강·검정·금 넷뿐이다) 그대로 믿을 값이 아니고, 반대로
    손으로 적은 쪽이 틀린 적도 있다. 어디를 봐야 하는지만 알려 준다."""
    COLOR = {"흰색": "백색", "빨간색": "적색", "검은색": "흑색", "금색": "금색"}
    ROLE = {"주인공": "주역기", "라이벌": "숙적기"}
    LINE = {"뉴타입": "뉴타입", "코디네이터": "코디네이터", "X라운더": "X라운더"}
    out = {"색 어긋남": [], "색 빈칸": [], "역할 어긋남": [], "역할 빈칸": [],
           "계통 어긋남": [], "감응계통 어긋남": [], "감응 등급 0인데 게임은 감응자": []}
    for c in mech:
        t = set(c.get("tags", []))
        col = {COLOR[x] for x in t if x in COLOR}
        rol = {ROLE[x] for x in t if x in ROLE}
        if col:
            (out["색 어긋남"] if "color" in c and c["color"] not in col
             else out["색 빈칸"] if "color" not in c else []).append(
                (c["name"], c.get("color"), "·".join(sorted(col))))
        if rol:
            (out["역할 어긋남"] if "role" in c and c["role"] not in rol
             else out["역할 빈칸"] if "role" not in c else []).append(
                (c["name"], c.get("role"), "·".join(sorted(rol))))
        if "사이코뮤" in t and c["system"] != "사이코뮤":
            out["계통 어긋남"].append((c["name"], c["system"], "사이코뮤"))
    for c in pilot:
        line = {LINE[x] for x in c.get("tags", []) if x in LINE}
        if not line:
            continue
        if c.get("line") and c["line"] not in line:
            out["감응계통 어긋남"].append((c["name"], c["line"], "·".join(sorted(line))))
        elif not c.get("line"):
            # 감응 등급이 0 이면 계통이 비는 게 맞다. 등급을 줄지 말지가 판단이다
            out["감응 등급 0인데 게임은 감응자"].append(
                (c["name"], "등급 %s" % c.get("psy"), "·".join(sorted(line))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    mech, pilot = roster.cards("mech"), roster.cards("pilot")
    ov = json.load(open(OVERRIDES, encoding="utf-8")) if os.path.exists(OVERRIDES) else {}
    ov_models = ov.get("models", {})

    idx = index([c["name"] for c in mech])
    soshage, gge_m, gge_p = from_soshage()
    official = from_official(idx)

    clash = []
    for n in sorted(set(soshage) & set(official)):
        if soshage[n].replace(" ", "").lower() != official[n].replace(" ", "").lower():
            clash.append((n, official[n], soshage[n], n in ov_models))

    def model_of(n):
        return ov_models.get(n) or official.get(n) or soshage.get(n) or ""

    units, chars = api("unit"), api("character")
    moved = []

    def put(c, key, val):
        if val:
            if c.get(key) != val:
                moved.append((c["name"], key, c.get(key), val))
            c[key] = val
        elif key in c:
            moved.append((c["name"], key, c[key], None))
            del c[key]

    for c in mech:
        put(c, "models", model_of(c["name"]))
        ids = gge_m.get(c["name"])
        put(c, "gge", ids)
        got = extras(ids, units, TAG_MECH) if ids else {}
        for k in ("rarity", "large", "tags"):
            put(c, k, got.get(k))
        # 지형은 아래 fill_terrain 이 도맡는다. 여기서 지웠다 채우는 것은
        # 바뀐 것이 아니라 다시 세우는 것이라 moved 에 세지 않는다
        c.pop("terrain", None)
        if got.get("terrain"):
            c["terrain"] = got["terrain"]
    for c in pilot:
        ids = gge_p.get(c["name"])
        put(c, "gge", ids)
        got = extras(ids, chars, TAG_PILOT) if ids else {}
        for k in ("rarity", "tags"):
            put(c, k, got.get(k))

    # 소샤지에 없는 카드의 지형은 여기서 지어 낸다. 자리 차례를 잡기 전에 해야
    # terrain_src 가 제자리에 들어간다
    tsrc = fill_terrain(mech, ov.get("terrain"))

    # 자리 차례를 지킨다 — name, models, gge 가 앞에 오게
    order = ["name", "models", "gge", "rarity", "factions", "stats", "temper",
             "system", "psy", "series", "line", "weight", "color", "role", "gundam",
             "large", "terrain", "terrain_src", "tags", "lore"]
    key = lambda k: (order.index(k) if k in order else len(order))   # noqa: E731
    mech = [{k: c[k] for k in sorted(c, key=key)} for c in mech]
    pilot = [{k: c[k] for k in sorted(c, key=key)} for c in pilot]

    if not a.check:
        roster.put_cards("mech", mech)
        roster.put_cards("pilot", pilot)

    def cover(cards, key):
        n = sum(1 for c in cards if key in c)
        return "%d/%d (%d%%)" % (n, len(cards), round(100 * n / len(cards)))

    print("[%s] data/ 의 바깥 자료 칸" % ("대조" if a.check else "완료"))
    print("  기체 %d — 형식번호 %s · G제네 id %s · 레어도 %s"
          % (len(mech), cover(mech, "models"), cover(mech, "gge"), cover(mech, "rarity")))
    print("         지형적성 %s · 태그 %s · 대형기 %d"
          % (cover(mech, "terrain"), cover(mech, "tags"),
             sum(1 for c in mech if c.get("large"))))
    print("         지형 출처 — " + " · ".join("%s %d" % (k, v) for k, v in tsrc.items()))
    print("  파일럿 %d — G제네 id %s · 레어도 %s · 태그 %s"
          % (len(pilot), cover(pilot, "gge"), cover(pilot, "rarity"), cover(pilot, "tags")))
    print("  바뀐 항목 %d" % len(moved))
    for n, k, was, now in moved[:20] if a.report else []:
        print("     %-28s %-6s %s → %s" % (n, k, was, now))

    cc = crosscheck(mech, pilot)
    print("  손으로 적은 값과 대조 — " + " · ".join(
        "%s %d" % (k, len(v)) for k, v in cc.items() if v))
    if a.report:
        for k, v in cc.items():
            if not v:
                continue
            print("   ── %s" % k)
            for n, was, now in v:
                print("      %-30s 저장소 %-8s 소샤지 %s" % (n, was or "(없음)", now))

    left = [c for c in clash if not c[3]]
    print("  두 출처가 엇갈린 것 %d (사람이 정한 %d 제외하면 %d — 전부 공식을 따랐다)"
          % (len(clash), len(clash) - len(left), len(left)))
    if a.report:
        for n, o, s, fixed in clash:
            print("     %-30s 공식 %-18s 소샤지 %-24s %s"
                  % (n, o, s, "← " + ov_models[n] if fixed else ""))


if __name__ == "__main__":
    main()
