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

st.title("🎬 Comercial 30s AI v9 (Turbo)")
st.caption("Anúncios verticais com locução de alta energia prontos para converter.")

with st.expander("🔑 Configuração Inicial (Chave Gratuita)", expanded=True):
    api_key = st.text_input("Cole sua Chave Gratuita do Google Gemini:", type="password")

url_produto = st.text_input("🔗 Cole o Link do Produto (Shopee, Mercado Livre, etc.):")
nome_produto = st.text_input("📦 Nome ou Detalhes do Produto (Ex: Fone Bluetooth Gamer à prova d'água):")

fotos_manuais = st.file_uploader(
    "📸 Suba fotos da galeria (Recomendado para Shopee/Mercado Livre)", 
    type=["jpg", "jpeg", "png", "webp"], 
    accept_multiple_files=True
)

col1, col2 = st.columns(2)
with col1:
    voz_escolhida = st.selectbox("🎙️ Voz do Locutor:", [
        "pt-BR-AntonioNeural (Masculina - Varejo)",
        "pt-BR-FabioNeural (Masculina - Jovem/Dinâmica)",
        "pt-BR-ThalitaNeural (Feminina - Super Animada)",
        "pt-BR-FranciscaNeural (Feminina - Firme)"
    ])
with col2:
    energia_voz = st.selectbox("⚡ Energia da Locução:", [
        "Super Animado (Estilo TikTok/Oferta)",
        "Vendedor Empolgado (Ritmo Rápido)",
        "Apresentador Seguro (Ritmo Moderado)"
    ])

def corrigir_pronuncia(texto):
    ajustes = {
        "Shopee": "Chopi",
        "shopee": "Chopi",
        "SHOPEE": "Chopi",
        "TikTok": "Tique Toque",
        "tiktok": "Tique Toque",
        "Smartwatch": "Ismárt Uótchi",
        "smartwatch": "ismárt uótchi",
        "Bluetooth": "Blutúfi",
        "bluetooth": "blutúfi",
        "Free": "Grátis"
    }
    texto_falado = texto
    for palavra, pronuncia in ajustes.items():
        texto_falado = texto_falado.replace(palavra, pronuncia)
    return texto_falado

async def gerar_audio(texto, voz, energia, arquivo_saida):
    texto_para_falar = corrigir_pronuncia(texto)
    
    # Define velocidade e tom para dar emoção e energia real de comercial
    if "Super Animado" in energia:
        velocidade = "+20%"
        tom = "+8Hz"
    elif "Vendedor Empolgado" in energia:
        velocidade = "+14%"
        tom = "+4Hz"
    else:
        velocidade = "+6%"
        tom = "+0Hz"
        
    comunicador = edge_tts.Communicate(texto_para_falar, voz, rate=velocidade, pitch=tom)
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

def baixar_imagens_do_link(texto_markdown):
    urls_imagens = re.findall(r'!\[.*?\]\((https?://[^\s\)]+)\)', texto_markdown)
    imagens_salvas = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for i, img_url in enumerate(urls_imagens):
        if len(imagens_salvas) >= 5:
            break
        try:
            resp = requests.get(img_url, headers=headers, timeout=6)
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            if img.width >= 300 and img.height >= 300:
                caminho = preparar_imagem_vertical(img, i)
                imagens_salvas.append(caminho)
        except:
            continue
    return imagens_salvas

def gerar_roteiro_seguro(api_key, prompt):
    genai.configure(api_key=api_key.strip())
    modelos = ['gemini-3.5-flash-lite', 'gemini-3.8-flash', 'gemini-2.5-flash-lite']
    for nome_modelo in modelos:
        try:
            model = genai.GenerativeModel(nome_modelo)
            return model.generate_content(prompt).text.strip()
        except Exception as e:
            if "429" in str(e):
                time.sleep(5)
                continue
            elif "404" in str(e):
                continue
            else:
                raise e
    model = genai.GenerativeModel('gemini-3.8-flash')
    return model.generate_content(prompt).text.strip()

if st.button("🔥 GERAR COMERCIAL ANIMADO AGORA", use_container_width=True):
    if not api_key:
        st.error("⚠️ Por favor, cole sua chave gratuita do Google Gemini acima.")
    elif not url_produto and not fotos_manuais:
        st.error("⚠️ Cole o link de um produto ou envie pelo menos uma foto!")
    else:
        try:
            imagens_finais = []
            texto_produto = ""

            with st.spinner("1/4 Lendo informações e preparando fotos..."):
                if url_produto:
                    link_limpo = url_produto.strip()
                    if not link_limpo.startswith("http"):
                        link_limpo = "https://" + link_limpo
                    
                    try:
                        r_redir = requests.head(link_limpo, allow_redirects=True, timeout=10)
                        link_final = r_redir.url
                    except:
                        link_final = link_limpo

                    base_link, _, _ = link_final.partition("?")
                    link_sem_http = base_link.replace("https://", "").replace("http://", "")
                    
                    try:
                        resp = requests.get(f"https://jina.ai{link_sem_http}", timeout=20)
                        texto_produto = resp.text[:4000]
                    except:
                        texto_produto = ""
                
                if fotos_manuais:
                    for idx, arquivo in enumerate(fotos_manuais[:5]):
                        img = Image.open(arquivo).convert("RGB")
                        imagens_finais.append(preparar_imagem_vertical(img, idx))
                elif url_produto:
                    imagens_finais = baixar_imagens_do_link(texto_produto)

                if not imagens_finais:
                    st.warning("🔒 Esse site bloqueou o download automático das fotos. Suba 2 ou 3 prints do produto no botão logo acima e clique em Gerar novamente!")
                    st.stop()

            with st.spinner("2/4 Criando roteiro de vendas explosivo..."):
                info_final = f"Nome/Detalhes informados: {nome_produto}. Dados extras do link: {texto_produto}"
                prompt = f"""
                Você é o locutor de comerciais mais animado, enérgico e persuasivo do Brasil!
                Crie um roteiro de locução comercial de 30 segundos (entre 75 e 85 palavras) para vender o produto abaixo.
                REGRAS IMPORTANTES PARA A VOZ FICAR EMPOLGADA:
                - Use frases curtas, diretas e impactantes!
                - Abuse de pontos de exclamação (!) para o locutor falar com entusiasmo e energia!
                - Comece com um gancho explosivo (Ex: "Para tudo e olha isso!", "Você não vai acreditar nessa oferta!").
                - Fale especificamente sobre o produto informado, destacando seus benefícios e terminando com uma chamada urgente para clicar no link.
                - Escreva APENAS o texto falado em português do Brasil, sem títulos, sem asteriscos e sem emojis.
                
                Produto:
                {info_final}
                """
                roteiro = gerar_roteiro_seguro(api_key, prompt)
                st.success("✍️ Roteiro de Vendas Criado:")
                st.info(roteiro)

            with st.spinner("3/4 Gravando locução com alta energia..."):
                voz_id, _, _ = voz_escolhida.partition(" ")
                asyncio.run(gerar_audio(roteiro, voz_id, energia_voz, "locucao.mp3"))

            with st.spinner("4/4 Renderizando vídeo MP4 para celular..."):
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
            st.success("✅ Comercial Pronto! Assista e baixe abaixo:")
            st.video("comercial_30s.mp4")
            
            with open("comercial_30s.mp4", "rb") as file:
                st.download_button(
                    label="📥 SALVAR VÍDEO NA GALERIA",
                    data=file,
                    file_name="comercial_produto_30s.mp4",
                    mime="video/mp4",
                    use_container_width=True
                )

        except Exception as e:
            if "429" in str(e):
                st.warning("⏳ Muitos pedidos seguidos no plano gratuito do Google! Aguarde 35 segundos e clique novamente no botão.")
            else:
                st.error(f"Erro ao gerar o vídeo: {e}")
