"""Gera assets/catalogo.js com as camisas montadas dos parceiros.

As imagens não são baixadas: o catálogo aponta direto para os servidores
de Janete Artes e Marccos Designer. Rodado diariamente pelo GitHub Actions.
"""
import html
import json
import re

import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (VertexCatalogo)"}
SAIDA = Path(__file__).resolve().parent.parent / "assets" / "catalogo.js"

# quantas camisas da Janete por categoria (as mais recentes)
COTA_JANETE = {"Interclasse": 220, "Terceirão": 130, "Nono Ano": 60,
               "Formatura & Escola": 60, "Times & Seleções": 130}
# categorias do Marccos cuja foto principal é a camisa montada
ESTUDANTIL_MARCCOS = {"Estudantil", "Interclasse", "Terceirão", "Nono Ano"}
# trechos da URL da imagem de modelos que não aparecem montados (remover à mão)
BLOQUEADOS = ["mancha-verde-local-personalizada-25795", "s-s-lazio-personalizada-16136",
              "onca-jersey-feras-amarela-18968"]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8")


def categoria_janete(slug):
    if "interclasse" in slug: return "Interclasse"
    if "terceirao" in slug: return "Terceirão"
    if "nono-ano" in slug: return "Nono Ano"
    if re.search(r"formatura|professora|crisma|quinto-ano|ensino", slug): return "Formatura & Escola"
    if re.search(r"(^|-)time(-|$)|futebol|selecao|brasil|argentina|manchester|barcelona|real-madrid|flamengo|corinthians|palmeiras|copa", slug):
        return "Times & Seleções"


def nome_janete(slug):
    n = re.sub(r"-?\d{4}-\d{4}$", "", slug)
    n = re.sub(r"^((vetor|arte|layout|modelo|template|design|grafica|digital)-)+(camisa|camiseta|blusa|uniforme|regata)-", "", n)
    n = n.replace("-", " ").strip().title()
    for a, b in {"Terceirao": "Terceirão", "Selecao": "Seleção", " E ": " e ", " De ": " de ", " Com ": " com ",
                 " Do ": " do ", " Da ": " da ", " Na ": " na ", " No ": " no "}.items():
        n = n.replace(a, b)
    return n


def janete():
    xml = get("https://www.janeteartes.com/sitemap.xml")
    ents = re.findall(r"<loc>https://www\.janeteartes\.com/shop/produto/([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>.*?<image:loc>([^<]+)</image:loc>", xml, re.S)
    ruim = re.compile(r"caneca|molde|pack|kit|fonte|template|estampa|short|bone|bandeira|caixa|squeeze|azulejo|chaveiro|almofada|mouse|copo|garrafa|avental|ecobag|adesivo|logo")
    camisa = re.compile(r"camisa|camiseta|blusa|uniforme|regata")
    ents = [e for e in ents if camisa.search(e[0]) and not ruim.search(e[0]) and categoria_janete(e[0])]
    ents.sort(key=lambda e: e[1], reverse=True)
    cota, vistos, out = dict(COTA_JANETE), set(), []
    for slug, _, img in ents:
        c = categoria_janete(slug)
        base = re.sub(r"-r\d+$", "", slug)
        if cota[c] <= 0 or base in vistos or any(b in img for b in BLOQUEADOS): continue
        vistos.add(base); cota[c] -= 1
        out.append({"n": nome_janete(base), "k": "", "c": c, "i": img})
    return out


def imagem_media(im):
    """Menor versão com pelo menos 500px de largura (o tamanho 600x600 nem sempre existe)."""
    opcoes = sorted((int(w), u) for u, w in re.findall(r"(\S+) (\d+)w", im.get("srcset", "")))
    return next((u for w, u in opcoes if w >= 500), im["src"])


def marccos():
    prods, pg = [], 1
    while True:
        d = json.loads(get(f"https://marccosdesigner.com/wp-json/wc/store/v1/products?per_page=100&page={pg}"))
        if not d: break
        prods += d; pg += 1
    out = []
    for p in prods:
        cats = {html.unescape(c["name"]) for c in p["categories"]}
        if not cats & ESTUDANTIL_MARCCOS or cats & {"Fontes", "Números Personalizados"} or not p["images"]: continue
        nome = html.unescape(p["name"])
        m = re.search(r"[–-]\s*(\w*\d+\w*)\s*$", nome)
        nome = re.sub(r"\s*[–-]\s*\w*\d+\w*\s*$", "", nome)
        nome = re.sub(r"^Arte( Vetor)?( Camisa)? ", "", nome)
        c = next((x for x in ("Interclasse", "Terceirão", "Nono Ano") if x in cats), "Formatura & Escola")
        img = imagem_media(p["images"][0])
        out.append({"n": nome, "k": m.group(1) if m else "", "c": c, "i": img})
    return out





if __name__ == "__main__":
    fontes = {}
    for fonte in (marccos, janete):
        try:
            fontes[fonte.__name__] = fonte()
        except Exception as e:  # se um parceiro cair, mantém o outro
            print(f"falha em {fonte.__name__}: {e}")
            fontes[fonte.__name__] = []
    m, j = fontes["marccos"], fontes["janete"]
    if len(m) + len(j) < 100:
        raise SystemExit(f"só {len(m) + len(j)} itens, catálogo mantido")
    # intercala 1 Marccos a cada 4 Janete para a vitrine não ficar agrupada por parceiro
    mix = []
    for n in range(max(len(m), (len(j) + 3) // 4)):
        mix += j[n * 4:n * 4 + 4] + m[n:n + 1]
    SAIDA.write_text("window.CATALOGO=" + json.dumps(mix, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"{len(mix)} modelos ({len(m)} Marccos, {len(j)} Janete)")
