import streamlit as st
import streamlit.components.v1 as components
import requests
import time
import base64
import google.generativeai as genai
import edge_tts
import asyncio
from PIL import Image, ImageOps
from io import BytesIO

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

st.set_page_config(page_title="Comercial 30s AI", page_icon="🎬", layout="centered")

st.markdown("<style>.stButton>button { background: linear-gradient(90deg, #ff416c 0%, #ff4b2b 100%); color: white; font-weight: bold; border-radius: 12px; height: 55px; font-size: 18px; border: none; }</style>", unsafe_allow_html=True)

st.title("🎬 Comercial 30s AI v26")
st.caption("Sistema antibloqueio para celular: escolha as fotos e gere seu vídeo.")

chave_cofre = ""
try:
    chave_cofre = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    chave_cofre = ""

if chave_cofre:
    api_key = chave_cofre
    with st.expander("🔑 Chave API (Conectada via Secrets)", expanded=False):
        chave_manual = st.text_input("Ou cole outra chave aqui para substituir:", type="password")
        if chave_manual:
            api_key = chave_manual
else:
    with st.expander("🔑 Chave API do Google Gemini", expanded=True):
        api_key = st.text_input("Cole sua Chave API:", type="password")

url_produto = st.text_input("🔗 Cole o Link do Produto (Opcional):")
nome_produto = st.text_input("📦 Nome ou Oferta do Produto (Opcional):")

st.write("📸 **Selecione até 3 Prints/Fotos (Sistema Antibloqueio):**")

html_seletor = '''
<div style="background:#1e1e26; padding:15px; border-radius:12px; border:1px dashed #ff4b2b; text-align:center; font-family:sans-serif; color:white;">
    <label for="imgInput" style="background:#2575fc; color:white; padding:12px 20px; border-radius:8px; font-weight:bold; cursor:pointer; display:inline-block;">
        📂 TOCAR PARA ESCOLHER PRINTS DA GALERIA
    </label>
    <input type="file" id="imgInput" accept="image/*" multiple style="display:none;" />
    <p id="status" style="margin-top:10px; font-size:14px; color:#ccc;">Nenhuma foto selecionada ainda.</p>
    <div id="preview" style="display:flex; gap:8px; justify-content:center; margin-top:10px; flex-wrap:wrap;"></div>
</div>
<script>
const input = document.getElementById('imgInput');
const status = document.getElementById('status');
const preview = document.getElementById('preview');
input.addEventListener('change', async (e) => {
    const files = Array.from(e.target.files).slice(0, 3);
    if (!files.length) return;
    status.innerText = "Processando " + files.length + " foto(s)...";
    preview.innerHTML = "";
    let resultados = [];
    for (let file of files) {
        const b64 = await comprimirImagem(file);
        resultados.push(b64);
        const img = document.createElement('img');
        img.src = b64;
        img.style.height = "70px";
        img.style.borderRadius = "6px";
        preview.appendChild(img);
    }
    const textoFinal = resultados.join("|||");
    await navigator.clipboard.writeText(textoFinal).catch(() => {});
    const textareas = window.parent.document.querySelectorAll('textarea');
    for (let ta of textareas) {
        if (ta.getAttribute('aria-label') === 'DADOS_FOTOS_CELULAR') {
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
            nativeSetter.call(ta, textoFinal);
            ta.dispatchEvent(new Event('input', { bubbles: true }));
            break;
        }
    }
    status.innerHTML = "✅ <b>" + files.length + " foto(s) carregada(s)!</b> Clique no botão vermelho abaixo.";
    status.style.color = "#4ade80";
});
function comprimirImagem(file) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (event) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const maxDim = 800;
                let w = img.width;
                let h = img.height;
                if (w > h && w > maxDim) { h *= maxDim / w; w = maxDim; }
                else if (h > maxDim) { w *= maxDim / h; h = maxDim; }
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);
                resolve(canvas.toDataURL('image/jpeg', 0.8));
            };
            img.src = event.target.result;
        };
        reader.readAsDataURL(file);
    });
}
</script>
'''

components.html(html_seletor, height=210)
dados_fotos_b64 = st.text_area("DADOS_FOTOS_CELULAR", height=68, label_visibility="collapsed", placeholder="As fotos aparecem automaticamente aqui (ou segure e cole aqui)...")

col1, col2 = st.columns(2)
with col1:
    voz_escolhida = st.selectbox("🎙️ Voz do Locutor:", ["pt-BR-AntonioNeural (Masculina)", "pt-BR-FranciscaNeural (Feminina)"])
with col2:
    energia_voz = st.selectbox("⚡ Ritmo da Locução:", ["Super Animado (Ritmo Rápido)", "Vendedor Empolgado (Ritmo Ágil)", "Apresentador (Ritmo Normal)"])

def corrigir_pronuncia(texto):
    ajustes = {"Shopee": "Chopi", "shopee": "Chopi", "SHOPEE": "Chopi", "TikTok": "Tique Toque", "tiktok": "Tique Toque", "Bluetooth": "Blutúfi", "bluetooth": "blutúfi", "Smartwatch": "Ismárt Uótchi", "smartwatch": "ismárt uótchi"}
    texto_falado = texto
    for palavra, pronuncia in ajustes.items():
        texto_falado = texto_falado.replace(palavra, pronuncia)
    return texto_falado

async def gerar_audio(texto, voz, energia, arquivo_saida):
    texto_para_falar = corrigir_pronuncia(texto)
    velocidade = "+18%" if "Super Animado" in energia else ("+12%" if "Vendedor" in energia else "+0%")
    try:
        comunicador = edge_tts.Communicate(texto_para_falar, voz, rate=velocidade)
        await comunicador.save(arquivo_saida)
    except Exception:
        comunicador = edge_tts.Communicate(texto_para_falar, voz)
        await comunicador.save(arquivo_saida)

def preparar_imagem_vertical(img_pil, index):
    largura_alvo, altura_alvo = 720, 1280
    fundo = Image.new("RGB", (largura_alvo, altura_alvo), (18, 18, 24))
    img_ajustada = ImageOps.contain(img_pil, (largura_alvo - 40, altura_alvo - 200))
    pos_x = (largura_alvo - img_ajustada.width) // 2
    pos_y = (altura_alvo - img_ajustada.height) // 2
    fundo.paste(img_ajustada, (pos_x, pos_y))
    caminho = f"frame_{index}.jpg"
    fundo.save(caminho, quality=90)
    return caminho

def gerar_roteiro_com_visao(api_key, prompt, lista_imagens_pil):
    genai.configure(api_key=api_key.strip())
    modelos = ['gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-2.5-flash-lite']
    conteudo_envio = [prompt] + lista_imagens_pil[:3]
    for nome_modelo in modelos:
        try:
            model = genai.GenerativeModel(nome_modelo)
            return model.generate_content(conteudo_envio).text.strip()
        except Exception as e:
            if "429" in str(e):
                time.sleep(5)
                continue
            elif "404" in str(e):
                continue
            else:
                raise e
    model = genai.GenerativeModel('gemini-3.8-flash')
    return model.generate_content(conteudo_envio).text.strip()

if st.button("🔥 GERAR COMERCIAL ANIMADO AGORA", use_container_width=True):
    if not api_key:
        st.error("⚠️ Chave API não encontrada nos Secrets do Streamlit.")
    elif not dados_fotos_b64.strip() and not url_produto:
        st.warning("⚠️ Toque no botão azul acima para escolher os prints ou cole o link!")
    else:
        try:
            imagens_finais = []
            imagens_para_ia = []
            texto_produto = ""
            aviso_status = st.empty()

            aviso_status.info("⏳ 1/4 Preparando fotos e lendo informações...")
            if url_produto:
                link_limpo = url_produto.strip()
                if not link_limpo.startswith("http"):
                    link_limpo = "https://" + link_limpo
                try:
                    r_redir = requests.head(link_limpo, allow_redirects=True, timeout=8)
                    link_final = r_redir.url
                except Exception:
                    link_final = link_limpo
                base_link, _, _ = link_final.partition("?")
                link_sem_http = base_link.replace("https://", "").replace("http://", "")
                try:
                    resp = requests.get(f"https://jina.ai{link_sem_http}", timeout=10)
                    texto_produto = resp.text[:3000]
                except Exception:
                    texto_produto = ""

            if "data:image" in dados_fotos_b64:
                pedacos = dados_fotos_b64.strip().split("|||")
                for idx, pedaco in enumerate(pedacos[:3]):
                    if "," in pedaco:
                        _, b64_limpo = pedaco.split(",", 1)
                        img_bytes = base64.b64decode(b64_limpo)
                        img_pil = Image.open(BytesIO(img_bytes)).convert("RGB")
                        imagens_finais.append(preparar_imagem_vertical(img_pil, idx))
                        imagens_para_ia.append(img_pil)

            if not imagens_finais:
                aviso_status.empty()
                st.warning("⚠️ Nenhuma imagem carregada. Toque no botão azul acima e selecione suas fotos.")
                st.stop()

            aviso_status.info("⏳ 2/4 A IA está olhando suas fotos e criando o roteiro...")
