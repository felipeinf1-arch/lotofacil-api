#!/usr/bin/env python3
# ============================================================================
#  fetch_resultados.py  —  roda no GitHub Actions (IP da Azure, fora do
#  bloqueio da Azion que barra o Google Cloud).
#
#  O que faz: pra cada loteria, olha o maior concurso que já está no
#  dados*.json, pergunta à Caixa qual é o último, e BAIXA tudo que faltar
#  (preenche buracos), gravando no mesmo formato do app: {concurso, numeros}.
#
#  NÃO commita nada sozinho — quem faz o commit é o workflow (resultados.yml),
#  só quando algum arquivo muda.
#
#  Mesmo formato/URLs do main.py (Cloud Function), pra bater 100%.
# ============================================================================
import json
import sys
import time
import requests

# loteria -> (endpoint base da Caixa, arquivo no repo)
LOTERIAS = {
    "lotofacil": ("https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil", "dados.json"),
    "quina":     ("https://servicebus2.caixa.gov.br/portaldeloterias/api/quina",     "dados_quina.json"),
    "mega":      ("https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena",  "dados_mega.json"),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://loterias.caixa.gov.br/",
    "Origin": "https://loterias.caixa.gov.br",
}

# limite de segurança: no máximo N concursos por execução (evita baixar o
# histórico inteiro por engano se um arquivo vier vazio).
MAX_POR_RODADA = 30


def _sessao():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://loterias.caixa.gov.br/", timeout=15)  # aquece cookies
    except Exception as e:
        print(f"  aquecimento falhou (segue): {e}")
    return s


def _get_json(s, url, rotulo):
    """GET com 3 tentativas. Retorna dict ou None (loga status real)."""
    for tent in range(1, 4):
        try:
            r = s.get(url, timeout=25)
            if r.status_code == 200:
                try:
                    return r.json()
                except Exception:
                    print(f"  {rotulo}: 200 nao-JSON (inicio: {r.text[:80]!r})")
                    return None
            print(f"  {rotulo}: HTTP {r.status_code} (tent {tent})")
        except Exception as e:
            print(f"  {rotulo}: erro (tent {tent}): {e}")
        time.sleep(2 * tent)
    return None


def _carregar(arquivo):
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"  {arquivo}: nao existe ainda, comeca vazio.")
        return []
    except Exception as e:
        print(f"  {arquivo}: erro ao ler ({e}), comeca vazio.")
        return []


def _salvar(arquivo, lista):
    lista.sort(key=lambda x: x["concurso"])
    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False)


def _dezenas(data):
    """Extrai as dezenas como lista de int, ordenada."""
    bruto = data.get("listaDezenas") or []
    return sorted(int(x) for x in bruto)


def atualizar(nome, url_base, arquivo, s):
    print(f"== {nome} ({arquivo}) ==")
    lista = _carregar(arquivo)
    existentes = {item.get("concurso") for item in lista}
    maior_local = max(existentes) if existentes else 0

    ultimo = _get_json(s, url_base, f"{nome} ultimo")
    if not ultimo or not ultimo.get("numero"):
        print(f"  nao consegui o ultimo da Caixa — pulando {nome}.")
        return False

    ultimo_num = int(ultimo["numero"])
    print(f"  local={maior_local}  caixa={ultimo_num}")

    if ultimo_num <= maior_local:
        print("  ja esta em dia.")
        return False

    # baixa do (maior_local+1) ate o ultimo — mas no maximo MAX_POR_RODADA
    inicio = maior_local + 1
    if maior_local == 0:
        # arquivo vazio: nao baixa historico inteiro, so o ultimo
        inicio = ultimo_num
    fim = ultimo_num
    if fim - inicio + 1 > MAX_POR_RODADA:
        inicio = fim - MAX_POR_RODADA + 1
        print(f"  (limite: baixando so os ultimos {MAX_POR_RODADA})")

    novos = 0
    for numero in range(inicio, fim + 1):
        if numero in existentes:
            continue
        if numero == ultimo_num:
            data = ultimo  # ja temos o ultimo em maos
        else:
            data = _get_json(s, f"{url_base}/{numero}", f"{nome} {numero}")
        if not data or not data.get("listaDezenas"):
            print(f"  {numero}: sem dezenas, paro aqui.")
            break
        lista.append({"concurso": numero, "numeros": _dezenas(data)})
        existentes.add(numero)
        novos += 1
        time.sleep(0.5)  # gentil com a Caixa

    if novos:
        _salvar(arquivo, lista)
        print(f"  +{novos} concurso(s). Agora vai ate {max(existentes)}.")
        return True
    print("  nada novo gravado.")
    return False


def main():
    s = _sessao()
    mudou = False
    for nome, (url_base, arquivo) in LOTERIAS.items():
        try:
            if atualizar(nome, url_base, arquivo, s):
                mudou = True
        except Exception as e:
            print(f"  ERRO inesperado em {nome}: {e}")
    print("RESULTADO:", "ATUALIZOU" if mudou else "sem novidades")
    # exit 0 sempre (o workflow decide o commit pelo git status)
    sys.exit(0)


if __name__ == "__main__":
    main()
