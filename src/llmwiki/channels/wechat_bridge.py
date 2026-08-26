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
