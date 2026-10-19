import os
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

SITEMAP_URL = "https://jamildo.com/sitemap-artigos.xml"
STATE_FILE = "last_posted_article.txt"

BUFFER_ACCESS_TOKEN = os.environ.get("BUFFER_ACCESS_TOKEN")
BUFFER_PROFILE_IDS_RAW = os.environ.get("BUFFER_PROFILE_IDS", "")
PROFILE_IDS = [pid.strip() for pid in BUFFER_PROFILE_IDS_RAW.split(",") if pid.strip()]

BUFFER_GRAPHQL_URL = "https://api.buffer.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_last_posted_url():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return file.read().strip()
    return ""

def save_last_posted_url(article_url):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        file.write(article_url)

def get_article_text(url):
    """
    Extrai preferencialmente a linha fina (og:description).
    Se não encontrar, usa o título principal como fallback.
    """
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # 1. Tenta pegar a Linha Fina (subtítulo)
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content") and og_desc["content"].strip():
                return og_desc["content"].strip()
            
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content") and meta_desc["content"].strip():
                return meta_desc["content"].strip()

            # 2. Se não tiver linha fina, pega o título principal
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                return og_title["content"].strip()
            if soup.title and soup.title.string:
                return soup.title.string.strip()
    except Exception as e:
        print(f"Erro ao capturar dados da página: {e}")
    return ""

def send_to_buffer(text):
    if not PROFILE_IDS:
        print("Erro: Nenhum ID de canal configurado na variável BUFFER_PROFILE_IDS.")
        return

    headers = {
        "Authorization": f"Bearer {BUFFER_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    mutation = """
    mutation CreateSinglePost($channelId: ChannelId!, $text: String!) {
      createPost(input: {
        channelId: $channelId
        text: $text
        schedulingType: automatic
        mode: shareNow
      }) {
        ... on PostActionSuccess {
          post {
            id
            status
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    for channel_id in PROFILE_IDS:
        payload = {
            "query": mutation,
            "variables": {
                "channelId": channel_id,
                "text": text
            }
        }
        response = requests.post(BUFFER_GRAPHQL_URL, json=payload, headers=headers)
        if response.status_code == 200:
            res_data = response.json()
            errors = res_data.get("errors")
            if errors:
                print(f"Erro GraphQL no canal {channel_id}: {errors}")
            else:
                data = res_data.get("data", {}).get("createPost", {})
                if "message" in data:
                    print(f"Erro retornado pelo Buffer no canal {channel_id}: {data['message']}")
                else:
                    print(f"Publicação enviada com sucesso ao canal {channel_id}.")
        else:
            print(f"Falha HTTP no canal {channel_id}: {response.status_code} - {response.text}")

def main():
    try:
        res = requests.get(SITEMAP_URL, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"Erro ao acessar sitemap: status {res.status_code}")
            return

        root = ET.fromstring(res.content)
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = root.findall("ns:url", namespace)

        if not urls:
            urls = root.findall("url")

        if not urls:
            print("Nenhuma URL encontrada no sitemap.")
            return

        first_url_el = urls[0].find("ns:loc", namespace)
        if first_url_el is None:
            first_url_el = urls[0].find("loc")

        if first_url_el is None or not first_url_el.text:
            print("Tag loc não encontrada no primeiro item.")
            return

        latest_url = first_url_el.text.strip()
        last_posted = get_last_posted_url()

        # Primeira execução: salva como referência e não dispara publicações antigas
        if not last_posted:
            print("Primeira execução: gravando a última matéria como referência.")
            save_last_posted_url(latest_url)
            return

        if latest_url != last_posted:
            print(f"Nova matéria detectada: {latest_url}")
            lead_text = get_article_text(latest_url)

            # Limite seguro para o post caber no X (280 chars) junto com o link
            if len(lead_text) > 200:
                lead_text = lead_text[:197] + "..."

            # Formato idêntico ao modelo: Linha Fina em cima + Link embaixo
            post_text = f"{lead_text}\n{latest_url}" if lead_text else latest_url

            send_to_buffer(post_text)
            save_last_posted_url(latest_url)
        else:
            print("Nenhuma matéria nova publicada desde a última checagem.")

    except Exception as e:
        print(f"Erro durante a execução: {e}")

if __name__ == "__main__":
    main()
