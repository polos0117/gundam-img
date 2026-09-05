#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
건담 드래프트 → 도감 앱 생성기

게임 파일(gundam-draft-N.html)에서 카드 데이터 블록만 그대로 뽑아
독립 실행되는 도감 HTML(gundam-dex-N.html)을 만든다.
카드 데이터의 원본은 언제나 게임 파일 하나뿐이므로 어긋날 일이 없다.

사용법:  python3 build-dex.py gundam-draft-122.html
"""
import re, sys, os, json

import roster

# 로스터는 data/ 에서 만든다
DATA_BLOCKS = ["MECH", "PILOT", "SHIP", "CREW", "SER_NAME", "FAC", "IMG"]
# 규칙·표시에 딸린 것은 게임 파일에 그대로 있다
CODE_BLOCKS = ["IMG_BASE", "ASPECT", "STAT_LABEL"]
BLOCKS = DATA_BLOCKS + CODE_BLOCKS


def js(name, v):
    return "var %s=%s;" % (name, json.dumps(v, ensure_ascii=False,
                                            separators=(",", ":")))


def data_blocks():
    """예전에 게임 파일에서 통째로 베껴 오던 선언들을 data/ 로 다시 만든다."""
    ser = roster.series()
    return "\n".join([
        js("MECH", roster.rows("mech")),
        js("PILOT", roster.rows("pilot")),
        js("SHIP", roster.rows("ship")),
        js("CREW", roster.rows("crew")),
        js("SER_NAME", ser["name"]),
        js("FAC", ser["faction_color"]),
        js("IMG", roster.img()),
    ])


def prompts(path="image-list.html", ren=None):
    """이미지 목록에서 프롬프트와 비고만 뽑는다.
    진행 현황(f/m/c/e)은 게임 파일의 IMG에서 실시간으로 계산하므로 가져오지 않는다."""
    if not os.path.exists(path):
        print(f"[알림] {path} 없음 — 프롬프트 없이 생성한다.")
        return "var PROMPT={};var NOTE={};"
    src = open(path, encoding="utf-8").read()
    m = re.search(r"var DATA=(\[.*?\]);", src, re.S)
    if not m:
        raise SystemExit(f"[실패] {path} 에서 DATA를 찾지 못했다.")
    ren = ren or {}
    P, N = {}, {}
    for ser in json.loads(m.group(1)):
        for grp in ser["groups"]:
            for row in grp["rows"]:
                # 게임 파일의 RENAME_MAP 을 적용해 카드명 변경을 자동 반영한다
                name = ren.get(row["name"], row["name"])
                P[name] = row.get("prompt", "")
                if row.get("note"):
                    N[name] = row["note"]
    return ("var PROMPT=" + json.dumps(P, ensure_ascii=False) + ";\n"
            "var NOTE=" + json.dumps(N, ensure_ascii=False) + ";")


def extract(src, name):
    """`var NAME=` 부터 괄호 균형이 맞는 지점까지를 문자열 그대로 잘라낸다."""
    m = re.search(r'(?m)^var\s+' + name + r'\s*=', src)
    if not m:
        raise SystemExit(f"[실패] {name} 선언을 찾지 못했다.")
    i = m.end()
    depth, in_str, quote, esc = 0, False, "", False
    started = False
    while i < len(src):
        ch = src[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        elif ch in "\"'":
            in_str, quote = True, ch
        elif ch in "[{(":
            depth += 1
            started = True
        elif ch in "]})":
            depth -= 1
            if started and depth == 0:
                i += 1
                break
        elif ch == ";" and depth == 0:
            break
        i += 1
    body = src[m.end():i].strip()
    return f"var {name}={body};"


TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex, nofollow, noarchive, noimageindex">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#151A21">
<title>건담 도감</title>
<style>
:root{
  --void:#0F1318;      /* 격납고 바닥 */
  --deck:#151A21;      /* 기본 배경 */
  --panel:#1D242D;     /* 카드/패널 */
  --rule:#2C3742;      /* 괘선 */
  --ink:#E4E9EF;       /* 본문 */
  --dim:#8794A3;       /* 보조 */
  --plate:#C9D2DC;     /* 스텐실 흰색 */
  --cc:#79849A;        /* 소속색 — 카드마다 갈아끼운다 */
  --gap:10px;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;padding:0}
body{
  background:var(--deck);color:var(--ink);
  font-family:'Pretendard','Apple SD Gothic Neo','Noto Sans KR',system-ui,sans-serif;
  font-size:15px;line-height:1.5;
  padding-bottom:env(safe-area-inset-bottom);
}
.mono{font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace}

/* ── 상단 ── */
header{
  position:sticky;top:0;z-index:30;background:var(--deck);
  border-bottom:1px solid var(--rule);
  padding:calc(10px + env(safe-area-inset-top)) 12px 0;
}
.brand{display:flex;align-items:baseline;gap:8px;margin-bottom:8px}
.brand h1{
  margin:0;font-size:17px;font-weight:800;letter-spacing:.22em;
}
.brand .n{font-size:11px;color:var(--dim);letter-spacing:.1em}

/* 탭 — 소속색 대신 활성 표식만, 조용하게 */
.tabs{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{
  flex:0 0 auto;background:none;border:0;color:var(--dim);
  font:inherit;font-size:13px;font-weight:700;letter-spacing:.05em;
  padding:9px 12px 10px;border-bottom:2px solid transparent;cursor:pointer;
}
.tab b{font-weight:500;font-size:11px;opacity:.65;margin-left:4px}
.tab.on{color:var(--ink);border-bottom-color:var(--plate)}

.ctl{display:flex;gap:6px;padding:7px 0 0;flex-wrap:wrap}
.ctl:last-of-type{padding-bottom:9px}
.sw.grow{flex:1 1 auto}
.sw.grow button{flex:1 1 0;padding:7px 4px}
.sw[hidden]{display:none}
.ctl input,.ctl select{
  background:var(--panel);border:1px solid var(--rule);color:var(--ink);
  font:inherit;font-size:13px;border-radius:6px;padding:7px 9px;min-width:0;
}
.ctl input{flex:1 1 auto}
.ctl select{flex:0 1 40%}
.ctl input:focus,.ctl select:focus{outline:2px solid var(--plate);outline-offset:-1px}
.sw{display:flex;flex:0 0 auto;border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.sw button{
  background:var(--panel);border:0;color:var(--dim);font:inherit;font-size:12px;
  font-weight:700;padding:0 10px;cursor:pointer;
}
.sw button.on{background:var(--plate);color:var(--void)}

/* ── 격자 ── */
main{padding:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:var(--gap)}
.cell{
  background:var(--panel);border:1px solid var(--rule);border-radius:8px;
  overflow:hidden;cursor:pointer;position:relative;
  border-left:3px solid var(--cc);
}
.cell:focus-visible{outline:2px solid var(--plate);outline-offset:2px}
.face{display:block;width:100%;aspect-ratio:2/3;background:#11161C center top/cover no-repeat}
.ph{display:flex;align-items:center;justify-content:center;height:100%;
  color:var(--dim);font-size:10px;letter-spacing:.1em}
.pg{position:absolute;top:5px;right:5px;background:rgba(15,19,24,.86);
  color:var(--plate);font-size:10px;font-weight:700;line-height:1;
  padding:4px 6px;border-radius:4px;border:1px solid rgba(255,255,255,.16);
  cursor:pointer;letter-spacing:.02em}
.pg:active{background:var(--plate);color:var(--void)}
.cell .face{transition:opacity .12s linear}
.cell.turn .face{opacity:.55}
.cap{padding:6px 7px 7px;font-size:11.5px;font-weight:600;line-height:1.3;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.empty{padding:40px 0;text-align:center;color:var(--dim);font-size:13px}

/* ── 작업 목록 ── */
.prog{height:3px;background:var(--rule);border-radius:99px;overflow:hidden;margin:0 0 8px}
.prog i{display:block;height:100%;background:var(--plate);transition:width .2s}
.rows{display:flex;flex-direction:column;gap:6px}
.row{background:var(--panel);border:1px solid var(--rule);border-left:3px solid var(--cc);
  border-radius:7px;padding:9px 11px;cursor:pointer}
.row:active{background:#232B36}
.row.done{opacity:.5}
.row .top{display:flex;align-items:center;gap:7px}
.row .nm{font-weight:700;font-size:14px;flex:1;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tag{font-size:10px;font-weight:700;line-height:1;padding:3px 5px;border-radius:3px;
  border:1px solid var(--rule);color:var(--dim);flex:0 0 auto}
.tag.hit{border-color:var(--cc);color:var(--plate)}
.row .pr{color:var(--dim);font-size:11.5px;margin-top:4px;line-height:1.45;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.row .nt{color:#9AA7B6;font-size:11px;margin-top:3px;font-style:italic}
.row .tk{color:#8FB4D9;font-size:11px;margin-top:5px;line-height:1.5;
  border-left:2px solid rgba(143,180,217,.45);padding-left:7px}
.lnk{margin-top:6px}
.lnk a{color:#8FB4D9;font-size:11px;text-decoration:none}
.lnk a:hover{text-decoration:underline}
.dt-tk{margin-top:10px;padding:9px 10px;border-radius:9px;background:rgba(143,180,217,.09);
  border:1px solid rgba(143,180,217,.25);font-size:11.5px;line-height:1.55;color:#B7CDE4}
.dt-tk b{display:block;color:#DCE7F2;font-size:11px;margin-bottom:3px}
.dt-tk a{color:#8FB4D9;text-decoration:none}
.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);z-index:80;
  background:var(--plate);color:var(--void);font-size:13px;font-weight:700;
  padding:9px 16px;border-radius:99px;pointer-events:none}

/* ── 상세 ── */
.sheet{position:fixed;inset:0;z-index:50;background:var(--void);overflow-y:auto;
  -webkit-overflow-scrolling:touch}
.sheet .bar{
  position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:10px;
  background:var(--void);border-bottom:1px solid var(--rule);
  padding:calc(8px + env(safe-area-inset-top)) 12px 8px;
}
.sheet .bar button{background:none;border:0;color:var(--ink);font:inherit;
  font-size:20px;line-height:1;padding:4px 6px;cursor:pointer}
.sheet .bar .t{font-weight:800;font-size:15px;letter-spacing:.02em;flex:1;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.wrap{max-width:560px;margin:0 auto;padding:12px 12px 60px}

/* 시그니처: 소속색 스텐실 명판 */
.plate{
  border:1px solid var(--rule);border-top:4px solid var(--cc);
  border-radius:4px;background:var(--panel);padding:12px 14px;margin-bottom:12px;
}
.plate .desig{font-size:10px;letter-spacing:.3em;color:var(--cc);font-weight:700}
.plate h2{margin:3px 0 8px;font-size:21px;font-weight:800;letter-spacing:-.01em}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{font-size:11px;padding:3px 8px;border-radius:99px;border:1px solid var(--rule);
  color:var(--dim);letter-spacing:.02em}
.chip.mono{font-family:var(--mono,ui-monospace,monospace);letter-spacing:.04em;opacity:.75}
.terr{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;margin:2px 0 4px}
.terr u{text-decoration:none;color:var(--dim);margin-right:5px;
  font-family:var(--mono,ui-monospace,monospace);font-size:10px}
.chip.f{border-color:var(--cc);color:var(--plate)}

.art{position:relative;border:1px solid var(--rule);border-radius:6px;overflow:hidden;
  background:#11161C;margin-bottom:12px}
.art img{display:block;width:100%;height:auto;cursor:zoom-in}
.art .vs{position:absolute;top:8px;right:8px;display:flex;border-radius:6px;
  overflow:hidden;border:1px solid rgba(0,0,0,.4)}
.art .vs button{background:rgba(15,19,24,.82);border:0;color:var(--dim);
  font:inherit;font-size:12px;font-weight:700;padding:6px 11px;cursor:pointer}
.art .vs button.on{background:var(--plate);color:var(--void)}

.sec{margin:16px 0 8px;font-size:10px;letter-spacing:.28em;color:var(--dim);font-weight:700}
.bar2{display:grid;grid-template-columns:42px 1fr 34px;align-items:center;gap:8px;
  margin-bottom:6px;font-size:12px}
.bar2 u{grid-column:2;text-decoration:none;display:block;height:6px;border-radius:99px;
  background:var(--rule);overflow:hidden}
.bar2 u i{display:block;height:100%;background:var(--cc)}
.bar2 b{text-align:right;font-weight:700}
.bar2 span{color:var(--dim)}

.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px}
.gal img{display:block;width:100%;height:auto;border-radius:6px;border:1px solid var(--rule);
  cursor:pointer;background:#11161C}
.gal img.on{border-color:var(--cc);box-shadow:0 0 0 2px var(--cc) inset}

.stylesw{margin-bottom:10px}
.stylesw select{width:100%;background:var(--panel);border:1px solid var(--rule);color:var(--ink);
  font:inherit;font-size:13px;border-radius:6px;padding:8px 10px}
.zoom{position:fixed;inset:0;z-index:70;background:rgba(8,10,13,.95);
  display:flex;align-items:center;justify-content:center;padding:16px;cursor:zoom-out}
.zoom img{max-width:100%;max-height:100%;border-radius:4px}

@media (prefers-reduced-motion:no-preference){
  .sheet{animation:rise .18s ease-out}
  @keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
}
</style>
</head>
<body>

<header>
  <div class="brand"><h1>건담 도감</h1><span class="n mono" id="tot"></span></div>
  <div class="tabs" id="tabs"></div>
  <div class="ctl">
    <div class="sw grow" id="msw">
      <button data-m="p" class="on">의인화</button><button data-m="c">일상</button><button data-m="x">특별</button><button data-m="w">작업</button>
    </div>
    <div class="sw" id="vsw">
      <button data-v="m">남</button><button data-v="f" class="on">여</button>
    </div>
    <div class="sw" id="fsw" hidden>
      <button data-w="0" class="on">남은 것</button><button data-w="1">전체</button>
    </div>
  </div>
  <div class="ctl">
    <input type="search" id="q" placeholder="이름 검색" autocomplete="off">
    <select id="ser"></select>
    <select id="styleSel" hidden></select>
  </div>
</header>

<main><div class="prog" id="prog" hidden><i></i></div><div class="grid" id="grid"></div><div class="empty" id="empty" hidden>해당하는 카드가 없다.</div></main>
<div id="ovl"></div>

<script>
/* ══ 게임 파일에서 추출한 데이터 (build-dex.py 자동 생성) ══ */
__DATA__
/* ══ 도감 전용 코드 ══ */
var POOL={"기체":MECH,"파일럿":PILOT,"지휘관":CREW,"함":SHIP};
var TABS=["기체","파일럿","지휘관","함"];
var tab="기체", ser="", q="", vari="f", mode="p";   /* p 의인화 · c 일상 · x 특별 컷 */
var styleSel="";   /* 화풍 탭에서 고른 화풍 키, 빈 값이면 전체 */
var MODE_NAME={p:"의인화",c:"일상",x:"특별 컷",w:"작업"};
var onlyLeft=true;   /* 작업 모드: 남은 것만 볼지 */

function imgURL(p){return IMG_BASE+encodeURIComponent(p)}

/* ══ 저장소 파일 목록으로 IMG 자동 보강 ══
   배열을 손대지 않아도, 규칙에 맞는 이름으로 올리기만 하면 잡힌다.
     카드명_m.webp / _f.webp / _casualN.webp / _extraN.webp
   공백은 밑줄로 바꿔 써도 인식한다. 목록을 못 받아오면 기존 IMG 로만 동작한다. */
var GH=(function(){
  var m=/^https?:\/\/([^.]+)\.github\.io\/([^\/]+)\//.exec(IMG_BASE);
  return m?{user:m[1],repo:m[2]}:null;
})();
var LIST_KEY="dex_filelist_v1", LIST_TTL=6e5;   /* 10분 */

function norm(s){return s.replace(/ /g,"_")}
function mergeFiles(names){
  var key={},t,i;                                /* 정규화 카드명 → 실제 카드명 */
  for(t in POOL)for(i=0;i<POOL[t].length;i++)key[norm(POOL[t][i][0])]=POOL[t][i][0];
  var added=0;
  for(i=0;i<names.length;i++){
    var n=names[i];
    if(!/\.webp$/i.test(n))continue;
    var m=/^(.+)_(m|f|casual(\d+)|extra(\d+))\.webp$/i.exec(n);
    if(!m)continue;
    var card=key[norm(m[1])]; if(!card)continue;
    var s=IMG[card]||(IMG[card]={});
    var kind=m[2].toLowerCase();
    if(kind==="m"||kind==="f"){ if(!s[kind]){s[kind]=n;added++} continue}
    var arr=kind.indexOf("casual")===0?"casual":"extra";
    var idx=parseInt(m[3]||m[4],10)-1;
    s[arr]=s[arr]||[];
    if(s[arr].indexOf(n)<0){s[arr][idx>=0?idx:s[arr].length]=n;added++}
  }
  /* 빈 칸 정리 후 파일명 순으로 */
  for(var c in IMG)["casual","extra"].forEach(function(a){
    if(!IMG[c][a])return;
    IMG[c][a]=IMG[c][a].filter(Boolean);
    if(!IMG[c][a].length)delete IMG[c][a];
  });
  return added;
}
function loadFileList(force){
  if(!GH)return Promise.resolve(0);
  if(!force){
    try{
      var c=JSON.parse(localStorage.getItem(LIST_KEY));
      if(c&&Date.now()-c.t<LIST_TTL)return Promise.resolve(mergeFiles(c.n));
    }catch(e){}
  }
  return fetch("https://api.github.com/repos/"+GH.user+"/"+GH.repo+"/contents/")
    .then(function(r){if(!r.ok)throw 0;return r.json()})
    .then(function(j){
      var n=j.filter(function(x){return x.type==="file"}).map(function(x){return x.name});
      try{localStorage.setItem(LIST_KEY,JSON.stringify({t:Date.now(),n:n}))}catch(e){}
      return mergeFiles(n);
    })
    .catch(function(){return 0});
}
function flip(v){return v==="m"?"f":"m"}
function fc(f){return FAC[f]||"#79849A"}
function ccOf(c){return fc(c[1][c[1].length-1])}
function esc(s){return String(s).replace(/[&<>"]/g,function(x){
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[x]})}
/* 한 기체가 여러 화풍 이미지를 가질 수 있다.
   기본 화풍은 IMG[이름] 그대로(기존 자료 무변화), 추가 화풍은 IMG[이름].byStyle[화풍키]에 얹는다.
   화풍 탭에서 특정 화풍을 고른 상태면 그 버킷을, 아니면 기본 버킷을 쓴다. */
function styleBucket(c){
  var s=IMG[c[0]]; if(!s)return null;
  if(tab==="기체"&&styleSel&&s.byStyle&&s.byStyle[styleSel])return s.byStyle[styleSel];
  return s;
}
function picOf(c,v){var s=styleBucket(c); if(!s)return null; return s[v]||s[flip(v)]||null}

/* 현재 보기 모드에서 이 카드가 내놓을 그림들 */
function shots(c){
  var s=styleBucket(c); if(!s)return [];
  if(mode==="c")return s.casual||[];
  if(mode==="x")return s.extra||[];
  var p=picOf(c,vari); return p?[p]:[];
}
/* 타일마다 몇 번째 그림을 보고 있는지 기억한다 (모드별로 따로) */
var page={};
function pkey(n){return mode+"|"+(mode==="p"?vari+"|":"")+n}
function pageOf(c){
  var ss=shots(c); if(ss.length<2)return 0;
  return ((page[pkey(c[0])]||0)%ss.length+ss.length)%ss.length;
}
function shotOf(c){var ss=shots(c);return ss.length?ss[pageOf(c)]:null}

/* ── 툴킷 설정 읽기 ──
   prompt.html 이 남긴 기록을 그대로 읽는다. 저장소 파일(toolkit-data.json)이 기반이고
   같은 브라우저의 localStorage 가 그 위를 덮는다. 쓰지는 않는다. */
var TK={base:{},local:{},baseUsed:{},localUsed:{},baseStyle:{},localStyle:{}};
function tkLoad(){
  try{
    var o=JSON.parse(localStorage.getItem("atelier_toolkit_v1")||"null");
    if(o&&o.anthro)TK.local=o.anthro;
    if(o&&o.used)TK.localUsed=o.used;
    if(o&&o.style)TK.localStyle=o.style;
  }catch(e){}
  return fetch("toolkit-data.json",{cache:"no-cache"})
    .then(function(r){return r.ok?r.json():null})
    .then(function(j){if(j){if(j.mechs)TK.base=j.mechs; if(j.used)TK.baseUsed=j.used;
      if(j.style)TK.baseStyle=j.style;}})
    .catch(function(){});
}
function tkReady(){ /* 기록이 도착하면 현재 화면을 다시 그린다 */
  if(typeof draw==="function")draw();
}
function tkOf(name){
  var a=TK.local[name],b=TK.base[name];
  if(!a)return b||null;
  if(!b)return a;
  return (a.t||0)>=(b.t||0)?a:b;
}
/* 콜라주로 어떤 카테고리를 뽑아봤는지 — 채택이 아니라 복사 기록이다 */
function tkUsed(name){
  var m={},add=function(arr){(arr||[]).forEach(function(r){
    if(!r.cat)return; m[r.cat]=(m[r.cat]||0)+(r.n||1);})};
  add((TK.baseUsed||{})[name]); add((TK.localUsed||{})[name]);
  return Object.keys(m).map(function(k){
    return (TK_CAT[k]||k)+(m[k]>1?" "+m[k]+"회":"")});
}
/* 화풍 — 기본값(세미리얼 시네마틱)은 기록에 안 남으므로 없으면 기본값으로 본다 */
var TK_ART={cinematic_semi_real:"세미리얼 시네마틱",game_keyart:"게임 키아트 2.5D",glossy_kr_game:"한국형 글로시 게임 일러스트",game_cgi:"게임 시네마틱 CGI",semi_real_paint:"세미리얼 유화",
  photoreal:"사진풍",anime_illust:"애니 일러스트",cel_anime:"셀화 애니",
  painterly:"회화적 컨셉아트",retro_anime:"레트로 애니",ink_wash:"수묵 담채"};
function tkStyleKey(name){
  return TK.localStyle[name]||TK.baseStyle[name]||"cinematic_semi_real";
}
/* 기본 화풍 + IMG[이름].byStyle에 실제로 이미지가 있는 추가 화풍들 전부 */
function tkStyleKeys(name){
  var out=[tkStyleKey(name)];
  var extra=(IMG[name]&&IMG[name].byStyle)||{};
  for(var k in extra)if(out.indexOf(k)<0)out.push(k);
  return out;
}
function tkStyle(name){
  var v=tkStyleKey(name);
  return TK_ART[v]||v;
}
var TK_CAT={adult_roleplay:"성인 역할극",occupation_basic:"직업(기본)",occupation_sensual:"직업(섹시)",
  everyday_basic:"일상(기본)",everyday_sensual:"일상(섹시)",swimwear:"수영복",active:"액티브",
  source_editorial:"SOURCE 에디토리얼",homewear:"홈웨어",private_evening:"프라이빗 이브닝",
  lingerie:"란제리",everyday:"일상",wildcard:"와일드카드",auto_random:"자동/랜덤"};
var TK_LABEL={"facial ethnicity":"계통","apparent age":"나이","body type":"체형",
  "hair color":"머리색","hair length":"머리길이","hairstyle":"헤어","eye color":"눈색",
  "facial hair":"수염","face shape":"얼굴형","facial character":"인상","skin tone":"피부"};
function tkSummary(name){
  var r=tkOf(name); if(!r)return "";
  var out=[];
  ["female","male"].forEach(function(g){
    var sel=r[g]&&r[g].sel; if(!sel)return;
    var bits=[];
    for(var k in TK_LABEL)if(sel[k])bits.push(TK_LABEL[k]+" "+sel[k]);
    if(r[g].ub)bits.push("언더부스트");
    if(bits.length)out.push((g==="female"?"여":"남")+" · "+bits.join(" / "));
  });
  return out.join("\n");
}

/* ── 작업 현황: image-list 의 f/m/c/e 를 대신해 IMG 에서 직접 센다 ── */
function stat(c){
  var s=styleBucket(c)||{};
  return {m:!!s.m, f:!!s.f,
          c:(s.casual||[]).length, x:(s.extra||[]).length,
          done:!!(s.m&&s.f)};
}

function serOf(c){return c[c.length-1] instanceof Array?c[c.length-1]:
  (c[8] instanceof Array?c[8]:[])}
function list(){
  var arr=POOL[tab]||[],out=[],i;
  for(i=0;i<arr.length;i++){
    var c=arr[i];
    if(ser&&serOf(c).indexOf(ser)<0)continue;
    if(styleSel&&tkStyleKeys(c[0]).indexOf(styleSel)<0)continue;
    if(q&&c[0].toLowerCase().indexOf(q)<0)continue;
    /* 일상·특별 컷은 그림이 있는 카드만 모아 보여준다 */
    if(mode==="c"||mode==="x"){if(!shots(c).length)continue}
    if(mode==="w"&&onlyLeft&&stat(c).done)continue;
    out.push(c);
  }
  return out;
}

function drawTabs(){
  var h="",i;
  for(i=0;i<TABS.length;i++){
    var t=TABS[i];
    h+='<button class="tab'+(t===tab?" on":"")+'" data-t="'+t+'">'+t+
       '<b class="mono">'+POOL[t].length+'</b></button>';
  }
  document.getElementById("tabs").innerHTML=h;
}
function drawSer(){
  var arr=POOL[tab]||[],cnt={},i,j;
  for(i=0;i<arr.length;i++){
    if((mode==="c"||mode==="x")&&!shots(arr[i]).length)continue;
    if(mode==="w"&&onlyLeft&&stat(arr[i]).done)continue;
    var ss=serOf(arr[i]);
    for(j=0;j<ss.length;j++)cnt[ss[j]]=(cnt[ss[j]]||0)+1}
  var h='<option value="">전체 시리즈</option>',k;
  for(k in SER_NAME)if(cnt[k])h+='<option value="'+k+'"'+(k===ser?" selected":"")+'>'+
    esc(SER_NAME[k])+" "+cnt[k]+"</option>";
  var sel=document.getElementById("ser");
  if(!cnt[ser])ser="";
  sel.innerHTML=h; sel.value=ser;
}
function drawStyleSel(){
  var sel=document.getElementById("styleSel");
  if(tab!=="기체"){sel.hidden=true;return}
  sel.hidden=false;
  var arr=POOL[tab]||[],cnt={},i;
  for(i=0;i<arr.length;i++){
    if((mode==="c"||mode==="x")&&!shots(arr[i]).length)continue;
    if(mode==="w"&&onlyLeft&&stat(arr[i]).done)continue;
    if(ser&&serOf(arr[i]).indexOf(ser)<0)continue;
    var ks=tkStyleKeys(arr[i][0]),j;
    for(j=0;j<ks.length;j++)cnt[ks[j]]=(cnt[ks[j]]||0)+1;
  }
  var h='<option value="">전체 화풍</option>',k;
  for(k in TK_ART)if(cnt[k])h+='<option value="'+k+'"'+(k===styleSel?" selected":"")+'>'+
    esc(TK_ART[k])+" "+cnt[k]+"</option>";
  if(!cnt[styleSel])styleSel="";
  sel.innerHTML=h; sel.value=styleSel;
}
function draw(){
  drawTabs(); drawSer(); drawStyleSel();
  if(mode==="w"){drawWork();return}
  document.getElementById("prog").hidden=true;
  document.getElementById("fsw").hidden=true;
  var arr=list(),h="",i,shown=0;
  for(i=0;i<arr.length;i++){
    var c=arr[i],ss=shots(c),pic=shotOf(c);
    if(pic)shown+=ss.length;
    h+='<div class="cell" tabindex="0" data-n="'+esc(c[0])+'" style="--cc:'+ccOf(c)+'">'+
       '<span class="face"'+(pic?' style="background-image:url(\''+imgURL(pic)+'\')"':"")+'>'+
       (pic?"":'<span class="ph">그림 없음</span>')+'</span>'+
       (ss.length>1?'<button class="pg mono" data-pg="1" aria-label="다음 그림">'+
         (pageOf(c)+1)+'/'+ss.length+'</button>':"")+
       '<div class="cap">'+esc(c[0])+'</div></div>';
  }
  var g=document.getElementById("grid");
  g.className="grid"; g.innerHTML=h;
  document.getElementById("empty").hidden=arr.length>0;
  document.getElementById("empty").textContent=
    mode==="p"?"해당하는 카드가 없다.":MODE_NAME[mode]+" 그림이 있는 카드가 아직 없다.";
  document.getElementById("tot").textContent=
    mode==="p"?arr.length+" / "+POOL[tab].length:arr.length+"장 · 그림 "+shown;
  document.getElementById("vsw").hidden=(mode!=="p");
}

/* ── 작업 모드: 초상 잔여 + 프롬프트 ── */
function drawWork(){
  document.getElementById("vsw").hidden=true;
  document.getElementById("fsw").hidden=false;

  /* 진척은 필터에 걸린 전체 모집단 기준으로 센다 */
  var all=POOL[tab]||[],pool=[],i;
  for(i=0;i<all.length;i++){
    var c=all[i];
    if(ser&&serOf(c).indexOf(ser)<0)continue;
    if(styleSel&&tkStyleKeys(c[0]).indexOf(styleSel)<0)continue;
    if(q&&c[0].toLowerCase().indexOf(q)<0)continue;
    pool.push(c);
  }
  var done=0;
  for(i=0;i<pool.length;i++)if(stat(pool[i]).done)done++;

  var pb=document.getElementById("prog");
  pb.hidden=false;
  pb.firstChild.style.width=(pool.length?done/pool.length*100:0).toFixed(1)+"%";

  var arr=onlyLeft?pool.filter(function(c){return !stat(c).done}):pool,h="";
  for(i=0;i<arr.length;i++){
    var c=arr[i],st=stat(c),nt=NOTE[c[0]]||"",pr=PROMPT[c[0]]||"",tk=tkSummary(c[0]);
    h+='<div class="row'+(st.done?" done":"")+'" tabindex="0" data-n="'+esc(c[0])+
       '" style="--cc:'+ccOf(c)+'"><div class="top"><span class="nm">'+esc(c[0])+'</span>'+
       '<span class="tag'+(st.m?" hit":"")+'">남</span>'+
       '<span class="tag'+(st.f?" hit":"")+'">여</span>'+
       (st.c?'<span class="tag hit mono">일상 '+st.c+'</span>':"")+
       (st.x?'<span class="tag hit mono">특별 '+st.x+'</span>':"")+
       '</div>'+
       (pr?'<div class="pr">'+esc(pr)+'</div>':"")+
       (nt?'<div class="nt">'+esc(nt)+'</div>':"")+
       (tk?'<div class="tk">'+esc(tk).replace(/\n/g,"<br>")+'</div>':"")+
       '<div class="tk" style="border-left-color:rgba(143,180,217,.25)">화풍 · '+esc(tkStyle(c[0]))+'</div>'+
       '<div class="lnk"><a href="prompt.html?mech='+encodeURIComponent(c[0])+
       '" target="_blank" rel="noopener">툴킷에서 열기 →</a></div>'+
       '</div>';
  }
  var g=document.getElementById("grid");
  g.className="rows"; g.innerHTML=h;
  document.getElementById("empty").hidden=arr.length>0;
  document.getElementById("empty").textContent=
    onlyLeft?"이 범위는 초상이 전부 채워졌다.":"해당하는 카드가 없다.";
  document.getElementById("tot").textContent="완료 "+done+" / "+pool.length+
    (onlyLeft?" · 남은 "+(pool.length-done):"");
}

/* 프롬프트 복사 */
function toast(msg){
  var t=document.createElement("div");
  t.className="toast"; t.textContent=msg;
  document.body.appendChild(t);
  setTimeout(function(){t.remove()},1400);
}
function copyPrompt(name){
  var p=PROMPT[name]; if(!p){toast("프롬프트가 없다");return}
  function ok(){toast("복사했다 · "+name)}
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(p).then(ok,fallback);
  }else fallback();
  function fallback(){
    var ta=document.createElement("textarea");
    ta.value=p; ta.style.position="fixed"; ta.style.opacity="0";
    document.body.appendChild(ta); ta.select();
    try{document.execCommand("copy");ok()}catch(e){toast("복사 실패")}
    ta.remove();
  }
}

/* ── 상세 ── */
function find(n){var arr=POOL[tab],i;for(i=0;i<arr.length;i++)if(arr[i][0]===n)return arr[i];return null}
function open(n,start){
  var c=find(n); if(!c)return;
  var cc=ccOf(c), t=tab;
  var labels=STAT_LABEL[t]||["","","",""];
  var v=vari;
  /* 이 기체가 가진 화풍 전부. 시트 안에서 독립적으로 넘겨볼 수 있다(밖의 필터와 별개). */
  var styleKeys=(t==="기체")?tkStyleKeys(c[0]):[];
  var curStyle=(styleSel&&styleKeys.indexOf(styleSel)>=0)?styleSel:(styleKeys[0]||"");
  function bucketFor(key){
    var base=IMG[c[0]]; if(!base)return null;
    if(key&&key!==styleKeys[0]&&base.byStyle&&base.byStyle[key])return base.byStyle[key];
    return base;
  }
  var s=bucketFor(curStyle);
  function localPicOf(vv){return (s&&(s[vv]||s[flip(vv)]))||null}
  /* 리스트에서 고른 그림을 그대로 대표 그림으로 띄운다 */
  var cur=start||localPicOf(v)||null;
  if(start&&s){if(s.m&&imgURL(s.m)===imgURL(start))v="m";
               else if(s.f&&imgURL(s.f)===imgURL(start))v="f"}

  function isPortrait(u){return !!(s&&u&&(u===s.m||u===s.f))}

  function body(){
    var h="";
    h+='<div class="plate" style="--cc:'+cc+'">'+
       '<div class="desig mono">'+esc(t)+'</div><h2>'+esc(c[0])+'</h2><div class="chips">';
    c[1].forEach(function(f){h+='<span class="chip f">'+esc(f)+'</span>'});
    serOf(c).forEach(function(k){h+='<span class="chip">'+esc(SER_NAME[k]||k)+'</span>'});
    if(t==="기체"){if(c[6])h+='<span class="chip">'+esc(c[6])+'</span>';
                   if(c[7])h+='<span class="chip">'+esc(c[7])+'</span>';
                   /* 형식번호 — 이름이 갈려도 같은 기체인지는 이걸로 가린다 */
                   if(c[9])h+='<span class="chip mono">'+esc(c[9])+'</span>'}
    if(t==="파일럿"){if(c[6])h+='<span class="chip">'+esc(c[6])+'</span>';
                     if(c[9])h+='<span class="chip">'+esc(c[9])+'</span>'}
    h+='</div></div>';

    if(styleKeys.length>1){
      h+='<div class="stylesw"><select id="sheetStyleSel">';
      styleKeys.forEach(function(k){
        h+='<option value="'+k+'"'+(k===curStyle?' selected':'')+'>'+esc(TK_ART[k]||k)+'</option>';
      });
      h+='</select></div>';
    }

    if(cur){
      h+='<div class="art"><img src="'+imgURL(cur)+'" alt="" data-z="'+esc(imgURL(cur))+'">';
      if(s&&s.m&&s.f&&isPortrait(cur))
        h+='<div class="vs"><button data-v="m"'+(v==="m"?' class="on"':"")+
           '>남</button><button data-v="f"'+(v==="f"?' class="on"':"")+'>여</button></div>';
      h+='</div>';
    }

    if(t==="기체"){
      var tk=tkSummary(c[0]);
      h+='<div class="dt-tk"><b>툴킷 설정</b>'+
         '<div style="margin-bottom:3px">화풍 · '+esc(TK_ART[curStyle]||curStyle||tkStyle(c[0]))+'</div>'+
         (tk?esc(tk).replace(/\n/g,"<br>"):"저장된 설정이 없다.")+
         (function(){var u=tkUsed(c[0]);return u.length?
           '<div style="margin-top:6px;opacity:.85">일상컷 복사 기록 · '+esc(u.join(", "))+'</div>':""})()+
         '<div style="margin-top:6px"><a href="prompt.html?mech='+encodeURIComponent(c[0])+
         '" target="_blank" rel="noopener">툴킷에서 열기 →</a></div></div>';
    }

    if(t==="기체"&&c[10]){
      /* 지형 적성 — 게임 쪽은 판마다 전장을 하나 뽑아 이 값으로 점수를 깎는다 */
      h+='<div class="sec">지형</div><div class="terr">';
      var TW=["","부적합","보통","적합"],tk;
      for(tk in c[10])h+='<span><u>'+esc(tk)+'</u>'+TW[c[10][tk]]+'</span>';
      h+='</div>';
    }

    h+='<div class="sec">능력</div>';
    for(var i=0;i<4;i++){
      var val=c[2+i],w=(t==="함"&&i===3)?val*14:val;
      h+='<div class="bar2" style="--cc:'+cc+'"><span>'+labels[i]+'</span>'+
         '<u><i style="width:'+Math.min(100,w)+'%"></i></u>'+
         '<b class="mono">'+val+'</b></div>';
    }

    function gal(l,label){
      if(!l||!l.length)return "";
      var g='<div class="sec">'+label+' '+l.length+'</div><div class="gal">',i;
      for(i=0;i<l.length;i++)g+='<img src="'+imgURL(l[i])+'" alt="" loading="lazy"'+
        (l[i]===cur?' class="on"':"")+' data-s="'+esc(l[i])+'">';
      return g+"</div>";
    }
    if(s){h+=gal(s.extra,"다른 그림"); h+=gal(s.casual,"일상")}
    if(!s){
      var qn=encodeURIComponent(c[0]);
      h+='<div class="sec">그림</div><p style="color:var(--dim);font-size:13px">'+
        '아직 그림이 없는 카드다. 참고용으로 외부에서 원본 디자인을 찾아볼 수 있다 '+
        '(이미지를 가져오지 않는다 — 검색 결과 페이지로 이동만 한다).</p>'+
        '<div class="lnk"><a href="https://www.google.com/search?tbm=isch&q='+qn+'+건담" '+
        'target="_blank" rel="noopener">구글 이미지에서 찾아보기 →</a></div>'+
        '<div class="lnk"><a href="https://www.google.com/search?q=site%3Agundam.fandom.com+'+qn+'+건담" '+
        'target="_blank" rel="noopener">건담 위키에서 찾아보기 →</a></div>';
    }
    return h;
  }

  var sh=document.createElement("div");
  sh.className="sheet";
  function render(keep){
    var y=keep?sh.scrollTop:0;
    sh.innerHTML='<div class="bar"><button data-x="1" aria-label="닫기">&times;</button>'+
      '<span class="t">'+esc(c[0])+'</span></div><div class="wrap">'+body()+'</div>';
    sh.scrollTop=y;
    var ssEl=sh.querySelector("#sheetStyleSel");
    if(ssEl)ssEl.onchange=function(){
      curStyle=this.value; s=bucketFor(curStyle); cur=localPicOf(v);
      render(true);
    };
  }
  render(false);
  sh.addEventListener("click",function(e){
    var b=e.target.closest("button"),
        pick=e.target.closest("img[data-s]"),
        z=e.target.closest(".art img");
    if(b&&b.dataset.x){close();return}
    if(b&&b.dataset.v){v=b.dataset.v;cur=localPicOf(v);render(true);return}
    if(pick){cur=pick.dataset.s;render(true);sh.scrollTop=0;return}
    if(z){zoom(z.dataset.z);return}
  });
  document.getElementById("ovl").appendChild(sh);
  document.body.style.overflow="hidden";
  history.pushState({dex:1},"");
}
function close(){
  document.getElementById("ovl").innerHTML="";
  document.body.style.overflow="";
}
function zoom(u){
  var z=document.createElement("div");
  z.className="zoom"; z.innerHTML='<img src="'+esc(u)+'" alt="">';
  z.onclick=function(){z.remove()};
  document.getElementById("ovl").appendChild(z);
}

/* ── 이벤트 ── */
document.getElementById("tabs").onclick=function(e){
  var b=e.target.closest(".tab"); if(!b)return;
  tab=b.dataset.t; ser=""; styleSel=""; draw(); scrollTo(0,0);
};
/* ── 격자 안에서 그림 넘기기 ── */
var grid=document.getElementById("grid");

/* 상세로 들어가지 않고 타일 그림만 교체한다 */
function step(cell,d){
  var c=find(cell.dataset.n); if(!c)return;
  var ss=shots(c); if(ss.length<2)return;
  var k=pkey(c[0]);
  page[k]=(((page[k]||0)+d)%ss.length+ss.length)%ss.length;
  var face=cell.querySelector(".face"),pgb=cell.querySelector(".pg");
  face.style.backgroundImage="url('"+imgURL(ss[page[k]])+"')";
  if(pgb)pgb.textContent=(page[k]+1)+"/"+ss.length;
  cell.classList.add("turn");
  setTimeout(function(){cell.classList.remove("turn")},120);
}
function curURL(cell){
  var c=find(cell.dataset.n); return c?shotOf(c):null;
}

var swiped=false;
grid.onclick=function(e){
  if(swiped){swiped=false;return}
  var pgb=e.target.closest(".pg");
  if(pgb){step(pgb.closest(".cell"),1);return}
  var r=e.target.closest(".row");
  if(r){copyPrompt(r.dataset.n);return}
  var c=e.target.closest(".cell");
  if(c)open(c.dataset.n,curURL(c));
};
grid.onkeydown=function(e){
  var r=e.target.closest(".row");
  if(r&&(e.key==="Enter"||e.key===" ")){e.preventDefault();copyPrompt(r.dataset.n);return}
  var c=e.target.closest(".cell"); if(!c)return;
  if(e.key==="Enter"||e.key===" "){e.preventDefault();open(c.dataset.n,curURL(c));return}
  if(e.key==="ArrowRight"){e.preventDefault();step(c,1)}
  if(e.key==="ArrowLeft"){e.preventDefault();step(c,-1)}
};

/* 좌우로 밀면 다음·이전 그림 */
var tx=0,ty=0,tc=null;
grid.addEventListener("touchstart",function(e){
  var t=e.touches[0]; tx=t.clientX; ty=t.clientY;
  tc=e.target.closest(".cell"); swiped=false;
},{passive:true});
grid.addEventListener("touchend",function(e){
  if(!tc)return;
  var t=e.changedTouches[0],dx=t.clientX-tx,dy=t.clientY-ty;
  if(Math.abs(dx)>28&&Math.abs(dx)>Math.abs(dy)*1.4){
    step(tc,dx<0?1:-1); swiped=true;
  }
  tc=null;
},{passive:true});
document.getElementById("q").oninput=function(){q=this.value.trim().toLowerCase();draw()};
document.getElementById("ser").onchange=function(){ser=this.value;draw()};
document.getElementById("styleSel").onchange=function(){styleSel=this.value;draw()};
document.getElementById("msw").onclick=function(e){
  var b=e.target.closest("button"); if(!b)return;
  mode=b.dataset.m;
  [].forEach.call(this.children,function(x){x.classList.toggle("on",x===b)});
  draw(); scrollTo(0,0);
};
document.getElementById("fsw").onclick=function(e){
  var b=e.target.closest("button"); if(!b)return;
  onlyLeft=(b.dataset.w==="0");
  [].forEach.call(this.children,function(x){x.classList.toggle("on",x===b)});
  draw(); scrollTo(0,0);
};
document.getElementById("vsw").onclick=function(e){
  var b=e.target.closest("button"); if(!b)return;
  vari=b.dataset.v;
  [].forEach.call(this.children,function(x){x.classList.toggle("on",x===b)});
  draw();
};
addEventListener("popstate",close);
addEventListener("keydown",function(e){
  if(e.key!=="Escape")return;
  var z=document.querySelector(".zoom");
  if(z)z.remove(); else if(document.querySelector(".sheet"))history.back();
});

draw();
loadFileList(false).then(function(n){if(n)draw()});
tkLoad().then(tkReady);
document.getElementById("tot").onclick=function(){
  var el=this; el.textContent="…";
  loadFileList(true).then(function(n){draw();toast(n?n+"장 새로 잡았다":"새 그림 없음")});
};
</script>
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        raise SystemExit("사용법: python3 build-dex.py gundam-draft-N.html [image-list.html]")
    path = sys.argv[1]
    src = open(path, encoding="utf-8").read()

    data = data_blocks() + "\n" + "\n".join(extract(src, b) for b in CODE_BLOCKS)
    ren = json.loads(re.search(r"var RENAME_MAP=(\{.*?\});", src, re.S).group(1))
    data += "\n" + prompts(sys.argv[2] if len(sys.argv) > 2 else "image-list.html", ren)
    out = TEMPLATE.replace("__DATA__", data)

    m = re.search(r"(\d+)\.html$", os.path.basename(path))
    ver = m.group(1) if m else "x"
    dest = f"gundam-dex-{ver}.html"
    open(dest, "w", encoding="utf-8").write(out)

    print(f"생성: {dest}  ({len(out):,} bytes)")
    for b in BLOCKS + ["PROMPT", "NOTE"]:
        print(f"  - {b}")


if __name__ == "__main__":
    main()
