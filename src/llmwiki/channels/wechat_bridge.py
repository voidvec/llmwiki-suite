# -*- coding: utf-8 -*-
"""
wechat_bridge.py -- LlmWiki 微信问答桥接（FastAPI 服务 + 通道编排）

重新梳理后的分层架构
--------------------
  通道层 ChannelAdapter ──► 应答编排层 KbAssistant ──► 召回层 KbRetriever（kb_core 铁律）
   ├─ WeComAdapter   (Webhook 驱动：企业微信回调验签/加解密)
   └─ IlinkAdapter   (轮询驱动：腾讯 iLink Bot API，个人微信免 puppet)

本文件只做「装配 + 生命周期 + 对外 HTTP 端点」，不含任何业务/加解密细节：

  POST /chat          召回 + LLM 生成（受 BRIDGE_TOKEN 保护）
  POST /recall        仅召回候选（受 BRIDGE_TOKEN 保护）
  GET  /healthz       通道与网关状态聚合
  GET  /ilink/qrcode  拉取 iLink 绑定二维码（图片 base64）
  POST /ilink/activate 拉码并在后台等待扫码激活、保存会话
  GET/POST /wechat/callback  企业微信回调（仅 WeComAdapter 注册）

安全（沿用第二次评审 R3）：
  - 默认绑定 127.0.0.1；/wechat/callback 经内网穿透面向公网；
  - /chat、/recall 加 BRIDGE_TOKEN 网关令牌保护，避免隧道暴露后被任意查询知识库。

依赖：fastapi + uvicorn（对外服务）——**必须**通过 extra 安装：
      pip install "llmwiki-suite[serve]"
      （普通 `pip install llmwiki-suite` 只装核心，不含 fastapi/uvicorn；
       本模块只被 serve / 显式 import 时加载，未装 extras 不影响其它命令）
      通道适配器按需再引 wecom_crypto / 标准库。
运行：uvicorn llmwiki.channels.wechat_bridge:app --host 127.0.0.1 --port 8000
       或 llmwiki serve（CLI 封装，见 llmwiki/cli.py）
"""
import os
import sys
import threading

from fastapi import FastAPI, Depends, Query, Header, HTTPException
from fastapi.responses import HTMLResponse

from ..assistant import KbAssistant
from ..config import load_config, resolve_repo
from .. import _env
from .ilink_adapter import IlinkAdapter
from .wecom_adapter import WeComAdapter
from .feishu_adapter import FeishuAdapter
from .telegram_adapter import TelegramAdapter

app = FastAPI(title="LlmWiki WeChat Bridge")

# --------------------------------------------------------------------------
# 装配：索引 + 应答编排层 + 已启用的通道
# --------------------------------------------------------------------------
# 索引路径解析（pip 化后无 REPO_DEFAULT）：KB_INDEX 环境变量 > D3 解析链
# （--repo / CWD 向上找 .git / CWD 含 .md）。
def _resolve_index() -> str:
    env = _env.getenv("KB_INDEX")
    if env:
        return env
    try:
        return str(load_config(resolve_repo(None)).index_path)
    except BaseException as e:
        # RepoNotFoundError 是 SystemExit 子类，须用 BaseException 捕获；
        # 定位不到知识库时回退默认名，让首次召回抛出可读错误。
        print(f"[bridge] 未能定位知识库（{e}），索引回退默认名 kb-index.json",
              file=sys.stderr)
        return "kb-index.json"

# 检测索引缺失：serve 应能启动并返回可读错误，而不是 import 即崩。
# 用一个带缺失标记的空适配器替身，等真正请求时给出明确指引。
INDEX = _resolve_index()
assistant = KbAssistant(INDEX)

BRIDGE_TOKEN = _env.getenv("BRIDGE_TOKEN", "")

# 实例化通道：统一注册路由，通道实际启用状态由 adapter 内运行时读 env 判断
# （serve 进程内改 env 即可热启停单通道；/healthz 显示 configured/enabled）。
adapters = []
adapters.append(WeComAdapter(assistant))
if _env.getenv("ENABLE_ILINK", "1") != "0":
    adapters.append(IlinkAdapter(assistant))
adapters.append(FeishuAdapter(assistant))
adapters.append(TelegramAdapter(assistant))

for ad in adapters:
    ad.register_routes(app)

ilink = next((a for a in adapters if isinstance(a, IlinkAdapter)), None)


# --------------------------------------------------------------------------
# 安全：BRIDGE_TOKEN 网关守卫
# --------------------------------------------------------------------------
def require_bridge_token(token: str = Query(None),
                         x_token: str = Header(None, alias="X-Bridge-Token")):
    if not BRIDGE_TOKEN:
        return  # 未配置：本地/开发模式放行
    if token == BRIDGE_TOKEN or x_token == BRIDGE_TOKEN:
        return
    raise HTTPException(status_code=401, detail="missing or invalid BRIDGE_TOKEN")


# --------------------------------------------------------------------------
# 通用问答接口（受 BRIDGE_TOKEN 保护）
# --------------------------------------------------------------------------
from pydantic import BaseModel


class QueryReq(BaseModel):
    query: str
    top_k: int = 4
    categories: list = []
    tags: list = []


def _stale_warning():
    """P3：索引过期告警（None = 一致）。旧版索引（无指纹）返回提示重建。"""
    fr = assistant.retriever.check_freshness()
    if fr.unknown:
        return "索引由旧版生成（无过期指纹），建议重建：llmwiki index"
    if fr.stale:
        return fr.summary() + "；建议重建：llmwiki index"
    return None


@app.post("/chat", dependencies=[Depends(require_bridge_token)])
def chat(req: QueryReq):
    answer, candidates = assistant.answer(req.query, req.top_k, req.categories, req.tags)
    return {"answer": answer, "candidates": candidates,
            "index_stale": _stale_warning()}


@app.post("/recall", dependencies=[Depends(require_bridge_token)])
def recall(req: QueryReq):
    hits = assistant.recall(req.query, req.top_k,
                            categories=req.categories or None, tags=req.tags or None)
    return {
        "query": req.query,
        "count": len(hits),
        "candidates": [
            {"path": h.path, "title": h.title, "score": round(h.score, 2),
             "matched_headings": h.matched_headings, "summary": h.summary}
            for h in hits
        ],
        # P3：索引过期告警（None = 与磁盘一致；~11 ms/188 篇，按请求复查，
        # 覆盖长驻进程启动后文件继续变化的场景）
        "index_stale": _stale_warning(),
    }


# --------------------------------------------------------------------------
# iLink 个人微信：管理端点
# --------------------------------------------------------------------------
@app.get("/ilink/qrcode")
def ilink_qrcode():
    if not ilink:
        return {"error": "iLink 未启用（设置 ENABLE_ILINK=1）"}
    qr, link, svg = ilink.get_qrcode()
    if not qr:
        return {"error": "无法获取二维码（请确认拥有 iLink Bot API 权限）"}
    return {"qrcode": qr, "activation_link": link, "qrcode_img_svg": svg}


@app.post("/ilink/activate")
def ilink_activate(timeout: int = Query(180)):
    """拉取绑定二维码并在后台等待扫码激活（不阻塞请求）。
    返回二维码图片 base64 与激活链接；扫码后后台线程自动保存会话并进入轮询。
    页面刷新时复用同一二维码（start_activation）。可用 GET /ilink/status 轮询 connected。"""
    if not ilink:
        return {"error": "iLink 未启用"}
    qr, link, svg = ilink.start_activation(timeout=timeout)
    if not qr:
        return {"error": "无法获取二维码（请确认拥有 iLink Bot API 权限）"}
    return {"qrcode": qr, "activation_link": link, "qrcode_img_svg": svg,
            "detail": "waiting for scan; poll GET /ilink/status for connected status"}


@app.get("/ilink/status")
def ilink_status():
    """轻量激活状态（供 WebUI 前端轮询），含当前 pending 二维码。"""
    if not ilink:
        return {"enabled": False, "has_token": False, "connected": False,
                "session_valid": False, "qrcode": ""}
    h = ilink.health()
    h["qrcode"] = getattr(ilink, "_pending_qrcode", "")
    return h


# 可视化扫码 WebUI（参考 cc-go：其 webview 窗口把激活链接渲染成二维码图形）。
# 本端点的二维码由 ilink_adapter 用 qrcode 库把 activation_link 本地编码成 SVG 生成，
# 不依赖 iLink 返回图片；页面自包含，无外部依赖。
_ILINK_WEBUI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>iLink 微信绑定</title>
<style>
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background:#f5f6f8; color:#222; display:flex; align-items:center;
         justify-content:center; min-height:100vh; margin:0; }
  .card { background:#fff; border-radius:14px; padding:28px 32px; width:360px;
          box-shadow:0 8px 30px rgba(0,0,0,.08); text-align:center; }
  h2 { margin:0 0 6px; font-size:20px; }
  .sub { color:#888; font-size:13px; margin-bottom:18px; }
  .qr { width:220px; height:220px; margin:0 auto 10px; border:1px solid #eee; border-radius:8px; }
  .qr svg { width:220px; height:220px; display:block; }
  .link { display:inline-block; margin-top:14px; font-size:13px; color:#07c160;
          text-decoration:none; word-break:break-all; }
  .status { margin-top:16px; font-size:14px; padding:8px; border-radius:8px; }
  .wait { background:#eef7ff; color:#1677ff; }
  .ok { background:#e8f8ef; color:#07c160; }
  .err { background:#fdeeee; color:#e34; }
  .hint { margin-top:18px; font-size:12px; color:#999; line-height:1.6; }
</style>
</head>
<body>
<div class="card">
  <h2>iLink 微信绑定</h2>
  <div class="sub">用微信扫描下方二维码并确认，即可把当前微信绑定为知识库 Bot</div>
  <div id="box"><div class="status wait">正在生成二维码…</div></div>
  <div class="hint">
    方式一：用手机微信「扫一扫」扫描上方二维码<br>
    方式二：点击下方链接在微信内打开并确认<br>
    绑定成功后会自动开始应答，页面将提示已激活
  </div>
</div>
<script>
const box = document.getElementById('box');
async function load(){
  try{
    const r = await fetch('/ilink/activate', {method:'POST'});
    const d = await r.json();
    if(d.error){ box.innerHTML = '<div class="status err">'+d.error+'</div>'; return; }
    let html = '';
    if(d.qrcode_img_svg){
      // 后端已把激活链接编码成二维码 SVG，直接注入即可（无需外部图片）
      html += '<div class="qr" id="qr">'+d.qrcode_img_svg+'</div>';
    }else if(d.activation_link){
      html += '<div class="status err">未能生成二维码图片。请用下方链接在微信内打开。</div>';
    }
    if(d.activation_link){
      html += '<a class="link" href="'+d.activation_link+'" target="_blank">'
            + d.activation_link+'</a>';
    }
    html += '<div class="status wait" id="st">等待扫码确认…</div>';
    box.innerHTML = html;
    poll();
  }catch(e){ box.innerHTML = '<div class="status err">请求失败：'+e+'</div>'; }
}
function poll(){
  const t = setInterval(async ()=>{
    try{
      const r = await fetch('/ilink/status'); const d = await r.json();
      if(d.connected){
        clearInterval(t);
        document.getElementById('box').innerHTML =
          '<div class="status ok">✅ 已激活，微信端发消息即可查询知识库</div>';
      }
    }catch(e){}
  }, 2000);
}
load();
</script>
</body>
</html>"""


@app.get("/ilink/webui", response_class=HTMLResponse)
def ilink_webui():
    """可视化扫码 WebUI：渲染二维码图片供微信扫，并自动轮询激活状态。
    浏览器打开 http://127.0.0.1:8000/ilink/webui 即可。"""
    return HTMLResponse(_ILINK_WEBUI_HTML)


# --------------------------------------------------------------------------
# 网页问答（P0：/webui/chat）与工作台（P1：/dashboard）
# 设计见 docs/llmwiki-webui-dashboard-design.md（本地评审稿，未提交远程）。
# 两者都是零外部依赖的自包含 HTML，复用现有 /chat /healthz 后端。
# --------------------------------------------------------------------------
_CHAT_WEBUI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LlmWiki 知识库问答</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background:#f5f6f8; color:#222; margin:0; height:100vh;
         display:flex; flex-direction:column; }
  header { background:#fff; border-bottom:1px solid #e6e8eb; padding:10px 20px;
           display:flex; align-items:center; gap:10px; }
  header h1 { font-size:16px; margin:0; font-weight:600; }
  header .sub { font-size:12px; color:#999; }
  .stale { background:#fff7e6; color:#b25e09; font-size:12px; padding:8px 20px;
           border-bottom:1px solid #ffe1a8; display:none; }
  #msgs { flex:1; overflow-y:auto; padding:14px 16px; }
  .msg { max-width:760px; margin:2px auto 10px; padding:10px 14px; border-radius:8px;
         white-space:pre-wrap; word-wrap:break-word; line-height:1.65; font-size:14px; }
  .user { background:#eef4ff; margin-left:auto; }
  .bot  { background:#fff; border:1px solid #e6e8eb; }
  .refs { max-width:560px; margin:-4px auto 14px; }
  .ref { background:#fff; border:1px solid #e6e8eb; border-radius:6px;
         padding:8px 12px; margin-top:6px; font-size:12px; line-height:1.5; }
  .ref .t { font-weight:600; }
  .ref .p { color:#666; word-break:break-all; }
  .ref .s { color:#1677ff; }
  .ref code { background:#f2f3f5; border-radius:3px; padding:0 4px; font-size:11px; }
  .toolbar { background:#fff; border-top:1px solid #e6e8eb; padding:8px 16px;
             display:flex; gap:12px; align-items:center; font-size:12px; }
  .toolbar label { color:#666; }
  .toolbar input, .toolbar select { border:1px solid #ccd0d6; border-radius:4px;
                                    padding:3px 6px; font-size:12px; width:110px; }
  .toolbar input.wide { width:170px; }
  #composer { background:#fff; border-top:1px solid #e6e8eb; padding:10px 16px 14px;
              display:flex; gap:10px; align-items:flex-end; }
  #input { flex:1; resize:none; border:1px solid #ccd0d6; border-radius:8px;
           padding:9px 12px; font-size:14px; line-height:1.5; min-height:42px;
           max-height:140px; font-family:inherit; }
  #input:focus { outline:none; border-color:#1677ff; }
  #send { background:#1677ff; color:#fff; border:none; border-radius:8px;
          padding:10px 24px; font-size:14px; cursor:pointer; }
  #send:disabled { background:#a8c4f7; cursor:not-allowed; }
  .err { color:#e34; font-size:13px; }
</style>
</head>
<body>
<header>
  <h1>LlmWiki 知识库问答</h1>
  <span class="sub" id="svc">…</span>
</header>
<div class="stale" id="stale"></div>
<div id="msgs"></div>
<div class="toolbar">
  <label>top_k <select id="topk">
    <option value="3">3</option><option value="4" selected>4</option>
    <option value="6">6</option><option value="8">8</option>
  </select></label>
  <label>categories <input id="cats" class="wide" placeholder="逗号分隔，可留空"></label>
  <label>tags <input id="tags" class="wide" placeholder="逗号分隔，可留空"></label>
</div>
<div id="composer">
  <textarea id="input" placeholder="向知识库提问…（Enter 发送，Shift+Enter 换行）"></textarea>
  <button id="send" disabled>发送</button>
</div>
<script>
const msgs=document.getElementById('msgs'), input=document.getElementById('input'),
      send=document.getElementById('send'), staleEl=document.getElementById('stale');
let token = localStorage.getItem('llmwiki_token') || '';
const esc = s => String(s).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function addEl(cls, html){ const d=document.createElement('div'); d.className=cls;
  d.innerHTML=html; msgs.appendChild(d); msgs.scrollTop=msgs.scrollHeight; return d; }
async function api(body){
  const url = '/chat' + (token ? '?token='+encodeURIComponent(token) : '');
  const r = await fetch(url, {method:'POST',
    headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  if(r.status === 401){
    const t = prompt('服务端配置了 BRIDGE_TOKEN，请输入提问口令：');
    if(!t) throw new Error('缺少提问口令（BRIDGE_TOKEN）');
    token = t; localStorage.setItem('llmwiki_token', t); return api(body);
  }
  if(!r.ok) throw new Error('请求失败：HTTP '+r.status);
  return r.json();
}
function renderRefs(data){
  if(data.index_stale){ staleEl.style.display='block';
    staleEl.textContent='⚠️ '+data.index_stale; }
  if(!data.candidates || !data.candidates.length) return;
  const box=document.createElement('div'); box.className='refs';
  box.innerHTML = '<div style="font-size:12px;color:#999;margin-top:8px">引用</div>' +
    data.candidates.map(c=>'<div class="ref"><div class="t">'+esc(c.title||c.path)+
      '</div><div class="p"><code>'+esc(c.path)+'</code></div>'+
      '<div class="s">score '+Number(c.score).toFixed(2)+'</div></div>').join('');
  msgs.appendChild(box); msgs.scrollTop=msgs.scrollHeight;
}
async function sendMsg(){
  const q=input.value.trim(); if(!q) return;
  addEl('msg user', esc(q)); input.value='';
  send.disabled=true;
  const pending=addEl('msg bot', '思考中…');
  try{
    const cats=document.getElementById('cats').value.split(',').map(s=>s.trim()).filter(Boolean);
    const tgs =document.getElementById('tags').value.split(',').map(s=>s.trim()).filter(Boolean);
    const d = await api({query:q, top_k:parseInt(document.getElementById('topk').value,10)||4,
                         categories:cats, tags:tgs});
    pending.textContent = d.answer || '（无回答）';
    renderRefs(d);
  }catch(e){ pending.className='msg bot err'; pending.textContent='请求失败：'+e.message; }
  send.disabled=false; input.focus();
}
input.addEventListener('keydown', ev=>{
  if(ev.key==='Enter' && !ev.shiftKey){ ev.preventDefault(); sendMsg(); }
});
send.addEventListener('click', sendMsg);
input.addEventListener('input', ()=>{ send.disabled = !input.value.trim(); });
fetch('/healthz').then(r=>r.json()).then(d=>{
  document.getElementById('svc').textContent =
    d && d.bridge_token ? '已启用提问口令' : '本地模式（未配置口令）';
}).catch(()=>{});
input.focus();
</script>
</body>
</html>"""

_DASHBOARD_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LlmWiki 工作台</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background:#f5f6f8; color:#222; margin:0; padding:24px 16px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:#999; font-size:13px; margin-bottom:18px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
          gap:14px; max-width:1080px; margin:0 auto; }
  .card { background:#fff; border-radius:10px; padding:16px 18px;
          box-shadow:0 2px 10px rgba(0,0,0,.04); }
  .card h3 { margin:0 0 10px; font-size:14px; color:#444; }
  .row { font-size:13px; line-height:1.8; display:flex; justify-content:space-between; gap:12px; }
  .row .k { color:#888; }
  .row .v { font-weight:500; }
  .badge { display:inline-block; padding:1px 8px; border-radius:10px; font-size:11px; }
  .b-ok { background:#e8f8ef; color:#07c160; }
  .b-off{ background:#f2f3f5; color:#999; }
  .b-warn{ background:#fff7e6; color:#b25e09; }
  .btn { display:inline-block; margin-top:10px; background:#1677ff; color:#fff;
         border:none; border-radius:6px; padding:7px 16px; font-size:13px;
         text-decoration:none; }
  .btn.ghost { background:transparent; color:#1677ff; border:1px solid #1677ff; }
  .ch { display:flex; align-items:center; justify-content:space-between;
        padding:6px 0; border-bottom:1px dashed #eee; font-size:13px; }
  .ch:last-child { border-bottom:none; }
  .ch .nm { font-weight:500; }
  .err { color:#e34; font-size:13px; }
</style>
</head>
<body>
<h1>LlmWiki 工作台</h1>
<div class="sub">serve 状态总览 · 各功能入口统一从这里出发</div>
<div class="grid" id="grid"></div>
<script>
const esc = s => String(s==null?'':s).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const badge = (ok, t) => '<span class="badge '+(ok?'b-ok':'b-off')+'" >'+t+'</span>';
async function load(){
  const g=document.getElementById('grid');
  let d;
  try{ d = await (await fetch('/dashboard/status')).json(); }
  catch(e){ g.innerHTML='<div class="card"><h3>状态不可用</h3><div class="err">'
    + esc(e)+'</div></div>'; return; }
  let html='';
  // 入口卡片
  html+='<div class="card"><h3>入口</h3>'+
    '<div class="row"><span class="k">网页问答</span><span class="v"><a href="/webui/chat" target="_blank" class="btn">打开问答</a></span></div>'+
    (d.index && !d.index.error
      ? '<div class="row"><span class="k">iLink 绑定</span><span class="v"><a class="btn ghost" href="/ilink/webui" target="_blank">扫码绑定</a></span></div>':'')+
    '</div>';
  // 索引卡片
  if(d.index && !d.index.error){
    html+='<div class="card"><h3>索引</h3>'+
      '<div class="row"><span class="k">文档数</span><span class="v">'+esc(d.index.doc_count)+'</span></div>'+
      '<div class="row"><span class="k">来源</span><span class="v">'+esc(d.index.source||'-')+'</span></div>'+
      '<div class="row"><span class="k">生成时间</span><span class="v">'+esc(d.index.generated_at||'-')+'</span></div>'+
      '<div class="row"><span class="k">新鲜度</span><span class="v">'+
        (d.index.stale ? badge('b-warn','过期') : badge(true,'正常'))+'</span></div>'+
      (d.index.stale ? '<div class="err">'+esc(d.index.stale)+'</div>' : '')+
      '<div class="row"><span class="k">索引路径</span><span class="v" style="word-break:break-all">'+esc(d.index.root||'-')+'</span></div>'+
      '</div>';
  }else if(d.index){
    html+='<div class="card"><h3>索引</h3><div class="err">'+esc(d.index.error)+'</div></div>';
  }
  // 通道卡片
  html+='<div class="card"><h3>通道</h3>';
  (d.channels||[]).forEach(c=>{
    html+='<div class="ch"><span class="nm">'+esc(c.name||c.channel||'?')+'</span>'+
      '<span class="badge '+(c.state_cls||'b-off')+'">'+esc(c.state||(c.connected?'已连接':'未配置'))+'</span></div>';
  });
  if(!d.channels || !d.channels.length) html+='<div class="row"><span class="k">无通道</span></div>';
  html+='<div class="ch"><span class="nm">提问口令</span>'+(d.bridge_token
    ? '<span class="badge b-off">已启用</span>'
    : '<span class="badge b-off">未配置</span>')+'</div></div>';
  // API 卡片
  html+='<div class="card"><h3>API</h3>'+
    '<div class="row"><span class="k">/chat</span><span class="v"><code>POST</code> JSON</span></div>'+
    '<div class="row"><span class="k">/recall</span><span class="v"><code>POST</code> JSON</span></div>'+
    '<div class="row"><span class="k">/healthz</span><span class="v"><code>GET</code></span></div>'+
    '<div class="row"><span class="k">文档</span><span class="v"><a class="ghost" href="/docs" target="_blank">/docs</a></span></div>'+
    '</div>';
  g.innerHTML=html;
}
load();
</script>
</body>
</html>"""


@app.get("/webui/chat", response_class=HTMLResponse)
def webui_chat():
    """网页问答页（P0）：自包含单页，浏览器打开即用，复用 POST /chat。
    定位：人对浏览器的问答界面；/chat 保持纯 JSON API 不变。
    浏览器打开 http://127.0.0.1:8000/webui/chat 即可。"""
    return HTMLResponse(_CHAT_WEBUI_HTML)


@app.get("/dashboard/status")
def dashboard_status():
    """工作台状态聚合（P3 复用）：索引信息 + 通道状态 + 口令配置，
    一次性返回给 /dashboard 渲染，避免页面多次打 /healthz。
    通道 health() 字段不一致（ilink 用 connected/has_token，wecom/feishu/telegram
    用 configured），这里统一归一化为 state 视图，语义：已连接 > 已配置 > 未配置。"""
    def _channel_view(h):
        connected = bool(h.get("connected"))
        configured = bool(h.get("configured")) or bool(h.get("has_token"))
        if connected:
            state, st_cls = "已连接", "b-ok"
        elif configured:
            state, st_cls = "已配置", "b-off"
        else:
            state, st_cls = "未配置", "b-off"
        return {"name": h.get("name", "?"), "state": state, "state_cls": st_cls,
                "connected": connected, "configured": configured}
    idx = {}
    try:
        r = assistant.retriever  # 惰性构造，索引缺失时抛可读错误
        try :
            fr = r.check_freshness()
            if fr.unknown:
                stale = "索引由旧版生成（无过期指纹），建议重建：llmwiki index"
            elif fr.stale:
                stale = fr.summary() + "；建议重建：llmwiki index"
            else:
                stale = None
        except Exception as e:
            stale = "新鲜度检测失败：%s" % e
        idx = {
            "root": r.root,
            "source": r.index.get("source"),
            "doc_count": len(r.docs),
            "generated_at": r.index.get("generated_at"),
            "schema_version": r.index.get("schema_version"),
            "stale": stale,
        }
    except Exception as e:
        idx = {"error": "%s: %s" % (type(e).__name__, e)}
    return {"ok": True, "bridge_token": bool(BRIDGE_TOKEN),
            "index": idx, "channels": [_channel_view(a.health()) for a in adapters]}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """导航工作台（P1）：聚合入口 + 状态总览，各功能保持独立端点。
    浏览器打开 http://127.0.0.1:8000/dashboard 即可。"""
    return HTMLResponse(_DASHBOARD_HTML)


# --------------------------------------------------------------------------
# 健康检查
# --------------------------------------------------------------------------
@app.get("/healthz")
def healthz():
    return {"ok": True, "bridge_token": bool(BRIDGE_TOKEN),
            "channels": [a.health() for a in adapters]}


# --------------------------------------------------------------------------
# 生命周期：启动/停止轮询驱动通道
# --------------------------------------------------------------------------
@app.on_event("startup")
def _startup():
    for ad in adapters:
        try:
            ad.start()
        except Exception as e:
            print("[bridge] 启动通道失败 %s: %s" % (ad.name, e))


@app.on_event("shutdown")
def _shutdown():
    for ad in adapters:
        try:
            ad.stop()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
