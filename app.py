import streamlit as st
import requests
import re
import google.generativeai as genai
import edge_tts
import asyncio
import os
from PIL import Image, ImageOps
from io import BytesIO
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

st.set_page_config(page_title="Comercial 30s AI", page_icon="🎬", layout="centered")

st.markdown("""
    <style>
    .stButton>button {
        background: linear-gradient(90deg, #6a11cb 0%, #2575fc 100%);
        color: white;
        font-weight: bold;
        border-radius: 12px;
        height: 55px;
        font-size: 18px;
        border: none;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎬 Comercial 30s AI v3")
st.caption("Transforme qualquer link de produto em um anúncio vertical pronto para vender.")

with st.expander("🔑 Configuração Inicial (Chave Gratuita)", expanded=True):
    api_key = st.text_input("Cole sua Chave Gratuita do Google Gemini:", type="password")

url_produto = st.text_input("🔗 Cole o Link do Produto (Shopee, Mercado Livre, etc.):")

fotos_manuais = st.file_uploader(
    "📸 Plano B: Suba fotos da galeria (Recomendado para Shopee/Mercado Livre)", 
    type=["jpg", "jpeg", "png", "webp"], 
    accept_multiple_files=True
)

col1, col2 = st.columns(2)
with col1:
    voz_escolhida = st.selectbox("🎙️ Voz do Locutor:", [
        "pt-BR-AntonioNeural (Masculina)",
        "pt-BR-FranciscaNeural (Feminina)"
    ])
with col2:
    estilo_texto = st.selectbox("🎯 Foco da Venda:", [
        "Urgência e Oferta",
        "Solução de Problema",
        "Curiosidade e Novidade"
    ])

async def gerar_audio(texto, voz, arquivo_saida):
    comunicador = edge_tts.Communicate(texto, voz, rate="+5%")
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

if st.button("🚀 GERAR COMERCIAL DE 30 SEGUNDOS", use_container_width=True):
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

                    link_sem_param = link_final.partition("?")[0].replace("https://", "").replace("http://", "")
                    
                    try:
                        resp = requests.get(f"https://jina.ai{link_sem_param}", timeout=20)
                        texto_produto = resp.text[:4000]
                    except:
                        texto_produto = f"Produto da loja {link_sem_param}"
                
                if fotos_manuais:
                    for idx, arquivo in enumerate(fotos_manuais[:5]):
                        img = Image.open(arquivo).convert("RGB")
                        imagens_finais.append(preparar_imagem_vertical(img, idx))
                elif url_produto:
                    imagens_finais = baixar_imagens_do_link(texto_produto)

                if not imagens_finais:
                    st.warning("🔒 A Shopee bloqueou o download automático das fotos. Suba 2 ou 3 prints do produto no botão 'Plano B' logo acima e clique em Gerar novamente!")
                    st.stop()

            with st.spinner("2/4 Criando roteiro persuasivo de 30 segundos..."):
                genai.configure(api_key=api_key.strip())
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = f"""
                Crie um roteiro de locução comercial de EXATAMENTE 30 segundos (entre 68 e 78 palavras) 
                com foco em: {estilo_texto}.
                Escreva APENAS o texto que será falado em voz alta pelo locutor. 
                Não coloque títulos, não coloque indicações de cena, não use asteriscos e não use emojis.
                
                Informações do produto:
                {texto_produto if texto_produto else "Produto incrível em oferta especial mostrado nas imagens."}
                """
                roteiro = model.generate_content(prompt).text.strip()
                st.success("✍️ Roteiro de Vendas Criado:")
                st.info(roteiro)

            with st.spinner("3/4 Gravando locução comercial..."):
                voz_id = voz_escolhida.partition(" ")[0]
                asyncio.run(gerar_audio(roteiro, voz_id, "locucao.mp3"))

            with st.spinner("4/4 Renderizando vídeo MP4 para celular..."):
                audio = AudioFileClip("locucao.mp3")
                duracao_por_foto = audio.duration / len(imagens_finais)
                
                clipes = []
                for img_path in imagens_finais:
                    clipe = ImageClip(img_path).set_duration(duracao_por_foto)
                    clipe = clipe.resize(lambda t: 1 + 0.04 * (t / duracao_por_foto))
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
            st.error(f"Erro ao gerar o vídeo: {e}")
