"""
まーぴーと話せる音声カスタマーサポート(OpenAI Realtime API × Streamlit × WebRTC)

まーぴー = 青い小鳥のマスコット。JMC役員ハンズオン「生成AI」パートのベースアプリ。
参加者はこの動くまーぴーを、Claude Code に話し言葉で頼んで自分流にアレンジする
(方言・多言語・動き 等＝バイブコーディング)。

仕組み:
  1. Streamlit(サーバ側)が OpenAI の API キーで「短命トークン(ephemeral key)」
     を発行する。API キー自体はブラウザに渡さない。
  2. ブラウザ内の JavaScript が WebRTC で Realtime API に直接接続し、マイク音声を
     送って AI の音声応答を受け取る。
  3. AI の音声波形を Web Audio で解析し、まーぴーの画像を声に合わせて動かす。

起動:
  streamlit run main.py
"""

import os
import json
import base64
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---- 設定 -------------------------------------------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = "gpt-realtime"      # GA モデル。必要に応じて変更可
CHARACTER_IMAGE = "img_bird.png"      # まーぴー(青い小鳥)の立ち絵

# 声の候補(かわいい系を上に)。サイドバーで選べる。
VOICE_OPTIONS = ["marin", "shimmer", "coral", "sage", "alloy", "cedar"]
DEFAULT_VOICE = "marin"

# まーぴーのキャラクター設定(かわいい口調)
# ★ アレンジしたい時はこの SYSTEM_PROMPT を変える(口調・言語・性格など)
SYSTEM_PROMPT = """あなたは「まーぴー」という名前の、青い小鳥のキャラクターのカスタマーサポートです。
性格と話し方:
- 明るく元気で、人懐っこくてかわいい話し方をしてください。声は弾むように、少し高めのテンションで。
- 一人称は「まーぴー」。語尾に時々「〜だよ」「〜だね」と親しみを込めますが、失礼にはならないように。
- でも中身はしっかり者。お客様の困りごとは正確に理解して、丁寧に助けてください。
サポートのルール:
- まず相手の困りごとを理解するため、必要なら短く確認の質問をする。
- 回答は簡潔に、要点から先に。長く話しすぎない。
- 分からないこと・確証がないことは推測で答えず、「確認して折り返すね」と案内する。
- 個人情報やパスワードなど機微な情報は口頭で求めない。
- 会話の区切りで「ほかにも気になることある?」と優しく添える。
最初の一言は「こんにちは!まーぴーだよ。今日はどうしたの?」のように元気にあいさつしてください。
"""

# ---- 画像を data URI 化(iframe 内から参照するため) ------------------------


def img_data_uri(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    ext = path.rsplit(".", 1)[-1].lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return f"data:image/{mime};base64,{b64}"


# ---- 短命トークンの発行 ------------------------------------------------------


def create_ephemeral_token(voice: str) -> dict:
    resp = requests.post(
        "https://api.openai.com/v1/realtime/client_secrets",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "session": {
                "type": "realtime",
                "model": REALTIME_MODEL,
                "instructions": SYSTEM_PROMPT,
                "audio": {
                    "input": {
                        "turn_detection": {"type": "server_vad"},
                        "transcription": {"model": "gpt-4o-mini-transcribe"},
                    },
                    "output": {"voice": voice},
                },
            }
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---- WebRTC + まーぴーアニメーション(ブラウザ側 HTML/JS) -------------------


def realtime_widget_html(ephemeral_key: str, model: str, bird_uri: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8" />
<style>
  body {{ font-family: -apple-system, "Hiragino Sans", sans-serif; margin: 0; }}
  #wrap {{ text-align: center; }}

  /* まーぴーのステージ */
  #stage {{
    position: relative; height: 280px; display: flex;
    align-items: center; justify-content: center;
    background: radial-gradient(circle at 50% 60%, #eaf4ff 0%, #f7fbff 60%, #ffffff 100%);
    border-radius: 16px; overflow: hidden;
  }}
  #ring {{
    position: absolute; width: 180px; height: 180px; border-radius: 50%;
    background: rgba(59,130,246,0.18); opacity: 0; transform: scale(0.6);
  }}
  #floater {{ }}
  #bird {{
    width: 200px; height: auto; display: block;
    filter: drop-shadow(0 8px 12px rgba(0,0,0,0.12));
  }}
  /* 待機中はグレーアウト気味 */
  #stage.idle #floater {{ opacity: 0.55; filter: grayscale(0.3); }}
  /* 聞いている間は柔らかいリング */
  #stage.listening #ring {{ opacity: 0.5; }}

  .controls {{ margin: 14px 0; }}
  button {{
    font-size: 16px; padding: 10px 22px; border: none; border-radius: 999px;
    cursor: pointer; margin: 0 6px; font-weight: bold;
  }}
  #connect {{ background: #2563eb; color: white; }}
  #hangup  {{ background: #dc2626; color: white; }}
  button:disabled {{ opacity: 0.4; cursor: default; }}
  #status {{ margin: 6px 0 12px; color: #444; }}
  #log {{
    height: 160px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 10px;
    padding: 10px 14px; background: #fafafa; line-height: 1.6; text-align: left;
    font-size: 14px;
  }}
  .you {{ color: #1d4ed8; }}
  .ai  {{ color: #166534; }}
  .meta {{ color: #999; font-size: 12px; }}
</style>
</head>
<body>
<div id="wrap">
  <div id="stage" class="idle">
    <div id="ring"></div>
    <div id="floater"><img id="bird" src="{bird_uri}" alt="まーぴー" /></div>
  </div>

  <div class="controls">
    <button id="connect">🎤 まーぴーと話す</button>
    <button id="hangup" disabled>■ おわり</button>
  </div>
  <div id="status">「まーぴーと話す」を押してね</div>
  <div id="log"></div>
  <audio id="aiAudio" autoplay></audio>
</div>

<script>
const EPHEMERAL_KEY = {json.dumps(ephemeral_key)};
const MODEL = {json.dumps(model)};

let pc = null, micStream = null;
let audioCtx = null, analyser = null, dataArray = null, rafId = null;

const stage = document.getElementById("stage");
const bird = document.getElementById("bird");
const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const connectBtn = document.getElementById("connect");
const hangupBtn = document.getElementById("hangup");

function setStatus(t) {{ statusEl.textContent = t; }}
function setMode(m) {{ stage.className = m; }}  // idle / listening / speaking

function addLine(speaker, text, cls) {{
  const div = document.createElement("div");
  div.className = cls;
  div.innerHTML = "<b>" + speaker + ":</b> " + text;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
  return div;
}}

let currentAiLine = null, currentAiText = "";

function handleServerEvent(ev) {{
  if (ev.type === "response.output_audio_transcript.delta" ||
      ev.type === "response.audio_transcript.delta") {{
    if (!currentAiLine) {{ currentAiText = ""; currentAiLine = addLine("まーぴー", "", "ai"); }}
    currentAiText += ev.delta || "";
    currentAiLine.innerHTML = "<b>まーぴー:</b> " + currentAiText;
    logEl.scrollTop = logEl.scrollHeight;
  }}
  if (ev.type === "response.output_audio_transcript.done" ||
      ev.type === "response.audio_transcript.done") {{
    currentAiLine = null; currentAiText = "";
  }}
  if (ev.type === "conversation.item.input_audio_transcription.completed") {{
    if (ev.transcript) addLine("あなた", ev.transcript, "you");
  }}
  if (ev.type === "error") {{
    addLine("エラー", JSON.stringify(ev.error || ev), "meta");
  }}
}}

// AI 音声の音量を解析して、まーぴーを動かす
function setupAnalyser(stream) {{
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const src = audioCtx.createMediaStreamSource(stream);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  src.connect(analyser);  // destination には繋がない(再生は <audio> 側が担当)
  dataArray = new Uint8Array(analyser.frequencyBinCount);
  tick();
}}

function tick() {{
  analyser.getByteTimeDomainData(dataArray);
  let sum = 0;
  for (let i = 0; i < dataArray.length; i++) {{
    const v = (dataArray[i] - 128) / 128;
    sum += v * v;
  }}
  const rms = Math.sqrt(sum / dataArray.length);
  // 声の大きさで 1.0〜1.4 倍にスケール
  const scale = 1 + Math.min(rms * 3.0, 0.4);
  bird.style.setProperty("--talk", scale.toFixed(3));
  if (rms > 0.025) {{ setMode("speaking"); }}
  else if (pc) {{ setMode("listening"); }}
  rafId = requestAnimationFrame(tick);
}}

async function connect() {{
  try {{
    connectBtn.disabled = true;
    setStatus("マイクを準備中...");
    micStream = await navigator.mediaDevices.getUserMedia({{ audio: true }});

    pc = new RTCPeerConnection();
    pc.ontrack = (e) => {{
      document.getElementById("aiAudio").srcObject = e.streams[0];
      setupAnalyser(e.streams[0]);
    }};
    micStream.getTracks().forEach((t) => pc.addTrack(t, micStream));

    const dc = pc.createDataChannel("oai-events");
    dc.addEventListener("message", (e) => {{
      try {{ handleServerEvent(JSON.parse(e.data)); }} catch (_) {{}}
    }});

    setStatus("接続中...");
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const sdpResp = await fetch(
      "https://api.openai.com/v1/realtime/calls?model=" + encodeURIComponent(MODEL),
      {{ method: "POST", body: offer.sdp,
         headers: {{ "Authorization": "Bearer " + EPHEMERAL_KEY,
                     "Content-Type": "application/sdp" }} }}
    );
    if (!sdpResp.ok) {{
      throw new Error("SDP 交換に失敗: " + sdpResp.status + " " + (await sdpResp.text()));
    }}
    await pc.setRemoteDescription({{ type: "answer", sdp: await sdpResp.text() }});

    setStatus("🟢 つながったよ — 話しかけてね!");
    setMode("listening");
    hangupBtn.disabled = false;
  }} catch (err) {{
    setStatus("接続エラー: " + err.message);
    addLine("エラー", err.message, "meta");
    setMode("idle");
    connectBtn.disabled = false;
  }}
}}

function hangup() {{
  if (rafId) cancelAnimationFrame(rafId), rafId = null;
  if (audioCtx) {{ audioCtx.close(); audioCtx = null; }}
  if (pc) {{ pc.close(); pc = null; }}
  if (micStream) {{ micStream.getTracks().forEach((t) => t.stop()); micStream = null; }}
  bird.style.setProperty("--talk", 1);
  setMode("idle");
  setStatus("バイバイ!また話そうね");
  connectBtn.disabled = false;
  hangupBtn.disabled = true;
}}

connectBtn.addEventListener("click", connect);
hangupBtn.addEventListener("click", hangup);
</script>
</body>
</html>
"""


# ---- Streamlit 画面 ---------------------------------------------------------

st.set_page_config(page_title="まーぴーサポート", page_icon="🐦")
st.title("🐦 まーぴーと話そう")
st.caption("OpenAI Realtime API(WebRTC)で、まーぴーがリアルタイム音声でお手伝い")

if not OPENAI_API_KEY:
    st.error(".env に OPENAI_API_KEY を設定してください。")
    st.stop()

with st.sidebar:
    st.subheader("設定")
    voice = st.selectbox("まーぴーの声", VOICE_OPTIONS,
                         index=VOICE_OPTIONS.index(DEFAULT_VOICE))
    st.caption("声を変えたら「セッション開始」を押し直してね")
    st.write(f"モデル: `{REALTIME_MODEL}`")

if st.button("セッション開始 / 再発行", type="primary"):
    try:
        with st.spinner("まーぴーを呼んでいます..."):
            token_data = create_ephemeral_token(voice)
        ephemeral_key = (
            token_data.get("value")
            or token_data.get("client_secret", {}).get("value")
        )
        if not ephemeral_key:
            st.error("トークンの取得に失敗しました。レスポンス: "
                     + json.dumps(token_data)[:500])
        else:
            st.session_state["ephemeral_key"] = ephemeral_key
            st.success("準備OK!下の「🎤 まーぴーと話す」を押してね")
    except requests.HTTPError as e:
        st.error(f"OpenAI API エラー: {e.response.status_code}\n{e.response.text[:500]}")
    except Exception as e:
        st.error(f"エラー: {e}")

if "ephemeral_key" in st.session_state:
    st.components.v1.html(
        realtime_widget_html(
            st.session_state["ephemeral_key"],
            REALTIME_MODEL,
            img_data_uri(CHARACTER_IMAGE),
        ),
        height=620,
    )
else:
    st.info("まず「セッション開始」を押してね。")
