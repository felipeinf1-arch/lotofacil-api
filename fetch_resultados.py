#!/usr/bin/env python3
# ============================================================================
#  fetch_resultados.py  —  roda no GitHub Actions.
#
#  A Caixa está atrás do WAF da Azion, que barra IP de datacenter (Google E
#  Azure deram 403 com requests comum). Este script usa curl_cffi, que IMITA
#  a impressão digital TLS do Chrome de verdade — muitos WAFs que barram o
#  requests deixam o curl_cffi passar, mesmo vindo de datacenter.
#
#  Pra cada loteria: olha o maior concurso no dados*.json, pergunta à Caixa
#  qual é o último e baixa o que faltar, gravando {concurso, numeros}.
#  Não commita — quem commita é o workflow (só quando muda algo).
# ============================================================================
import json
import sys
import time

# curl_cffi: cliente HTTP que impersona TLS de navegador real.
from curl_cffi import requests as cffi

# loteria -> (endpoint base da Caixa, arquivo no repo)
LOTERIAS = {
    "lotofacil": ("https://servicebus2.caixa.gov.br/portaldeloterias/api/lotofacil", "dados.json"),
    "quina":     ("https://servicebus2.caixa.gov.br/portaldeloterias/api/quina",     "dados_quina.json"),
    "mega":      ("https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena",  "dados_mega.json"),
}

# navegador imitado (TLS/JA3 do Chrome). Se um não existir na versão do
# curl_cffi, tenta o próximo.
IMPERSONATE = ["chrome124", "chrome120", "chrome110", "chrome"]

MAX_POR_RODADA = 30  # trava de segurança: baixa no máximo N por execução


def _sessao():
    """Sessão curl_cffi imitando Chrome, aquecida com um GET no portal."""
    ultimo_erro = None
    for alvo in IMPERSONATE:
        try:
            s = cffi.Session(impersonate=alvo, timeout=25)
            # aquecimento: pega cookies do WAF antes da API
            s.get("https://loterias.caixa.gov.br/")
            print(f"  (sessao curl_cffi impersonando '{alvo}')")
            return s
        except Exception as e:
            ultimo_erro = e
            continue
    print(f"  nao criei sessao curl_cffi: {ultimo_erro}")
    return None


def _get_json(s, url, rotulo):
    for tent in range(1, 4):
        try:
            r = s.get(url)
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

    inicio = maior_local + 1
    if maior_local == 0:
        inicio = ultimo_num  # arquivo vazio: baixa só o último, não o histórico
    fim = ultimo_num
    if fim - inicio + 1 > MAX_POR_RODADA:
        inicio = fim - MAX_POR_RODADA + 1
        print(f"  (limite: baixando so os ultimos {MAX_POR_RODADA})")

    novos = 0
    for numero in range(inicio, fim + 1):
        if numero in existentes:
            continue
        if numero == ultimo_num:
            data = ultimo
        else:
            data = _get_json(s, f"{url_base}/{numero}", f"{nome} {numero}")
        if not data or not data.get("listaDezenas"):
            print(f"  {numero}: sem dezenas, paro aqui.")
            break
        lista.append({"concurso": numero, "numeros": _dezenas(data)})
        existentes.add(numero)
        novos += 1
        time.sleep(0.5)

    if novos:
        _salvar(arquivo, lista)
        print(f"  +{novos} concurso(s). Agora vai ate {max(existentes)}.")
        return True
    print("  nada novo gravado.")
    return False


def main():
    s = _sessao()
    if s is None:
        print("RESULTADO: sem sessao")
        sys.exit(0)
    mudou = False
    for nome, (url_base, arquivo) in LOTERIAS.items():
        try:
            if atualizar(nome, url_base, arquivo, s):
                mudou = True
        except Exception as e:
            print(f"  ERRO inesperado em {nome}: {e}")
    print("RESULTADO:", "ATUALIZOU" if mudou else "sem novidades")
    sys.exit(0)


if __name__ == "__main__":
    main()
