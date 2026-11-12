import os
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
SITEMAP_URL = "https://jamildo.com/sitemap-artigos.xml"
ARQUIVO_HISTORICO = "postados.txt"
LIMITE_HISTORICO = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def carregar_historico():
    if not os.path.exists(ARQUIVO_HISTORICO):
        return []
    with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]

def salvar_historico(lista_links):
    # Mantém apenas os últimos 30 links registrados
    links_recentes = lista_links[-LIMITE_HISTORICO:]
    with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
        for link in links_recentes:
            f.write(f"{link}\n")

def buscar_links_sitemap():
    response = requests.get(SITEMAP_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    
    # Extrai todas as tags <loc> ignorando o namespace XML
    urls = [elem.text.strip() for elem in root.iter() if elem.tag.endswith("loc") and elem.text]
    return urls

def extrair_titulo(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Prioriza a meta tag og:title (título limpo da matéria)
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()
            
        if soup.title and soup.title.string:
            return soup.title.string.split(" - Jamildo")[0].strip()
    except Exception as e:
        print(f"Aviso ao extrair título de {url}: {e}")
    return ""

def postar_no_facebook():
    historico = carregar_historico()
    urls_sitemap = buscar_links_sitemap()
    
    if not urls_sitemap:
        print("Nenhuma URL encontrada no sitemap.")
        return

    # Pega as 5 primeiras URLs do sitemap (mais recentes) e inverte para postar em ordem cronológica
    ultimas_urls = list(reversed(urls_sitemap[:5]))

    for link in ultimas_urls:
        if link in historico:
            print(f"Já postado: {link}")
            continue

        titulo = extrair_titulo(link)
        mensagem = f"{titulo}\n\nLeia mais: {link}" if titulo else link

        api_url = f"https://graph.facebook.com/v21.0/{PAGE_ID}/feed"
        payload = {
            "message": mensagem,
            "link": link,
            "access_token": ACCESS_TOKEN
        }

        response = requests.post(api_url, data=payload, timeout=15)
        
        if response.status_code == 200:
            print(f"Publicado com sucesso: {titulo or link}")
            historico.append(link)
            salvar_historico(historico)
        else:
            print(f"Erro ao publicar '{link}': {response.json()}")

if __name__ == "__main__":
    postar_no_facebook()
