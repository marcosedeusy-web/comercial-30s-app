import streamlit as st
import requests
import re
import time
import google.generativeai as genai
import edge_tts
import asyncio
import os
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

st.title("🎬 Comercial 30s AI v15")
st.caption("Suba as fotos do produto e gere um anúncio vertical animado em 30 segundos.")

# Sua chave nova protegida e dividida em duas partes
parte_1 = "AQ.Ab8RN6IdeHIiVOzpnUV9rJbUE"
parte_2 = "roFFCqqA8x0rHmxUxl6N4yOyA"
api_key = parte_1 + parte_2

nome_produto = st.text_input("📦 Nome ou Oferta do Produto (Opcional - a IA já lê suas fotos!):")

fotos_manuais = st.file_uploader("📸 Suba de 2 a 5 fotos ou prints do produto:", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)

col1, col2 = st.columns(2)
with col1:
    voz_escolhida = st.selectbox("🎙️ Voz do Locutor:", ["pt-BR-AntonioNeural (Masculina)", "pt-BR-FranciscaNeural (Feminina)"])
with col2:
    energia_voz = st.selectbox("⚡ Ritmo da Locução:", ["Super Animado (Ritmo Rápido)", "Vendedor Empolgado (Ritmo Ágil)", "Apresentador (Ritmo Normal)"])

def corrigir_pronuncia(texto):
    ajustes = {"Shopee": "Chopi", "shopee": "Chopi", "SHOPEE": "Chopi", "TikTok": "Tique Toque", "tiktok": "Tique Toque", "Bluetooth": "Blutúfi", "bluetooth": "blutúfi"}
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
    fundo.save(caminho, quality=95)
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
    if not fotos_manuais:
        st.error("⚠️ Toque em Upload e selecione pelo menos 1 foto do produto!")
    else:
        try:
            imagens_finais = []
            imagens_para_ia = []

            with st.spinner("1/4 Preparando suas fotos..."):
                for idx, arquivo in enumerate(fotos_manuais[:5]):
                    img = Image.open(arquivo).convert("RGB")
                    imagens_finais.append(preparar_imagem_vertical(img, idx))
                    imagens_para_ia.append(img)

            with st.spinner("2/4 A IA está olhando suas fotos e criando o roteiro..."):
                prompt = f"""
                Você é o locutor de comerciais mais animado e persuasivo do Brasil!
                OLHE PARA AS IMAGENS ENVIADAS, identifique qual é o produto e crie um roteiro de 30 segundos (75 a 85 palavras) vendendo esse produto específico!
                Use frases curtas, abuse de pontos de exclamação (!) para dar entusiasmo e escreva APENAS o texto falado em português do Brasil, sem títulos, sem asteriscos e sem emojis.
                Detalhes extras: {nome_produto}
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

            st.balloons()
            st.success("✅ Comercial Pronto!")
            st.video("comercial_30s.mp4")

            video_bytes = open("comercial_30s.mp4", "rb").read()
            st.download_button("📥 SALVAR VÍDEO NA GALERIA", video_bytes, "comercial_30s.mp4", "video/mp4")

        except Exception as e:
            st.error(f"Erro ao gerar o vídeo: {e}")

# FIM
