import streamlit as st
import requests
import re
import time
import os
import google.generativeai as genai
import edge_tts
import asyncio
from PIL import Image, ImageOps
from io import BytesIO

if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

st.set_page_config(page_title="Comercial 30s AI", page_icon="🎬", layout="centered")

st.markdown("""
    <style>
    .stButton>button {
        background: linear-gradient(90deg, #ff416c 0%, #ff4b2b 100%);
        color: white;
        font-weight: bold;
        border-radius: 12px;
        height: 55px;
        font-size: 18px;
        border: none;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎬 Comercial 30s AI v24")
st.caption("Cole o link e envie os prints do produto para criar seu anúncio vertical.")

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

url_produto = st.text_input("🔗 Cole o Link do Produto (Shopee, Mercado Livre, etc.):")
nome_produto = st.text_input("📦 Nome ou Oferta do Produto (Opcional):")

st.write("📸 **Envie os Prints ou Fotos do Produto (1 em cada botão):**")
foto_1 = st.file_uploader("Print / Foto 1 (Obrigatória se o link bloquear):", key="f1")
foto_2 = st.file_uploader("Print / Foto 2 (Opcional):", key="f2")
foto_3 = st.file_uploader("Print / Foto 3 (Opcional):", key="f3")

col1, col2 = st.columns(2)
with col1:
    voz_escolhida = st.selectbox("🎙️ Voz do Locutor:", ["pt-BR-AntonioNeural (Masculina)", "pt-BR-FranciscaNeural (Feminina)"])
with col2:
    energia_voz = st.selectbox("⚡ Ritmo da Locução:", ["Super Animado (Ritmo Rápido)", "Vendedor Empolgado (Ritmo Ágil)", "Apresentador (Ritmo Normal)"])

def corrigir_pronuncia(texto):
    ajustes = {
        "Shopee": "Chopi",
        "shopee": "Chopi",
        "SHOPEE": "Chopi",
        "TikTok": "Tique Toque",
        "tiktok": "Tique Toque",
        "Bluetooth": "Blutúfi",
        "bluetooth": "blutúfi",
        "Smartwatch": "Ismárt Uótchi",
        "smartwatch": "ismárt uótchi"
    }
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

def otimizar_foto_celular(img_pil):
    img_corrigida = ImageOps.exif_transpose(img_pil)
    if img_corrigida.mode != "RGB":
        img_corrigida = img_corrigida.convert("RGB")
    img_corrigida.thumbnail((1080, 1080))
    return img_corrigida

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

def baixar_imagens_do_link(texto_markdown):
    urls_imagens = re.findall(r'!\[.*?\]\((https?://[^\s\)]+)\)', texto_markdown)
    imagens_salvas = []
    imagens_pil = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for i, img_url in enumerate(urls_imagens):
        if len(imagens_salvas) >= 5:
            break
        try:
            resp = requests.get(img_url, headers=headers, timeout=6)
            img = otimizar_foto_celular(Image.open(BytesIO(resp.content)))
            if img.width >= 250 and img.height >= 250:
                caminho = preparar_imagem_vertical(img, i)
                imagens_salvas.append(caminho)
                imagens_pil.append(img)
        except Exception:
            continue
    return imagens_salvas, imagens_pil

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
    fotos_enviadas = [f for f in [foto_1, foto_2, foto_3] if f is not None]
    
    if not api_key:
        st.error("⚠️ Cole sua Chave API acima ou salve nos Secrets do Streamlit.")
    elif not fotos_enviadas and not url_produto:
        st.warning("⚠️ Cole o link ou envie pelo menos 1 print do produto!")
    else:
        try:
            imagens_finais = []
            imagens_para_ia = []
            texto_produto = ""

            with st.spinner("1/4 Lendo informações e preparando fotos..."):
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
                        resp = requests.get(f"https://jina.ai{link_sem_http}", timeout=12)
                        texto_produto = resp.text[:3000]
                    except Exception:
                        texto_produto = ""

                if fotos_enviadas:
                    for idx, arquivo in enumerate(fotos_enviadas):
                        img_bruta = Image.open(arquivo)
                        img_leve = otimizar_foto_celular(img_bruta)
                        imagens_finais.append(preparar_imagem_vertical(img_leve, idx))
                        imagens_para_ia.append(img_leve)
                elif url_produto:
                    imagens_finais, imagens_para_ia = baixar_imagens_do_link(texto_produto)

                if not imagens_finais:
                    st.warning("⚠️ Este link não liberou imagens automaticamente. Envie pelo menos 1 print nos botões acima e clique em Gerar novamente.")
                    st.stop()

            with st.spinner("2/4 A IA está olhando suas fotos e criando o roteiro..."):
                prompt = f"""
                Você é o locutor de comerciais mais animado e persuasivo do Brasil!
                OLHE PARA AS IMAGENS ENVIADAS, identifique qual é o produto e crie um roteiro de 30 segundos (75 a 85 palavras) vendendo esse produto específico!
                Use frases curtas, abuse de pontos de exclamação (!) para dar entusiasmo e escreva APENAS o texto falado em português do Brasil, sem títulos, sem asteriscos e sem emojis.
                Link e detalhes: {url_produto} | {nome_produto} | {texto_produto[:800]}
                """
                roteiro = gerar_roteiro_com_visao(api_key, prompt, imagens_para_ia)
                st.success("✍️ Roteiro Criado:")
                st.info(roteiro)

            with st.spinner("3/4 Gravando locução animada..."):
                voz_id, _, _ = voz_escolhida.partition(" ")
                asyncio.run(gerar_audio(roteiro, voz_id, energia_voz, "locucao.mp3"))

            with st.spinner("4/4 Renderizando vídeo MP4..."):
                audio = AudioFileClip("locucao.mp3")
                duracao_por_foto = audio.duration / len(imagens_finais)
                clipes = []
                for img_path in imagens_finais:
                    clipe = ImageClip(img_path).set_duration(duracao_por_foto)
                    clipe = clipe.resize(lambda t: 1 + 0.05 * (t / duracao_por_foto))
                    clipes.append(clipe)
                video_final = concatenate_videoclips(clipes, method="compose").set_audio(audio)
                video_final.write_videofile("comercial_30s.mp4", fps=24, codec="libx264", audio_codec="aac", logger=None)
                audio.close()
                video_final.close()

            st.balloons()
            st.success("✅ Comercial Pronto!")
            st.video("comercial_30s.mp4")

            with open("comercial_30s.mp4", "rb") as f:
                video_bytes = f.read()
            st.download_button("📥 SALVAR VÍDEO NA GALERIA", video_bytes, "comercial_30s.mp4", "video/mp4")

        except Exception as e:
            st.error(f"Erro ao gerar o vídeo: {e}")

# FIM
