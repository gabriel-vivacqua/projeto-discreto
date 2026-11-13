"""ETL: converte data/chess_games.csv (Kaggle) nas bases de conhecimento Prolog
base.pl e base_mini.pl.

Dataset: "Chess Games" (6,2 milhões de partidas do Lichess, 2016)
https://www.kaggle.com/datasets/arevel/chess-games

Cada partida vira um fato

    partida(Tipo, EloBrancas, EloPretas, Vencedor, ECO, Abertura, Termino, Lances).

Uso:
    python3 etl.py                       # lê data/chess_games.csv, escreve base.pl e base_mini.pl
    python3 etl.py entrada.csv saida.pl  # escreve saida.pl e saida_mini.pl
"""

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ENTRADA_PADRAO = Path("data/chess_games.csv")
SAIDA_PADRAO = Path("base.pl")

COLUNAS = ["Event", "Result", "WhiteElo", "BlackElo", "ECO", "Opening", "Termination", "AN"]
RITMOS = ("bullet", "blitz", "rapid", "classical", "correspondence")
VENCEDOR = {"1-0": "white", "0-1": "black", "1/2-1/2": "draw"}

TIPO = "blitz"          # ritmo mantido na base
MIN_LANCES = 2          # partidas mais curtas não chegaram a jogar a abertura
TOP_ABERTURAS = 40      # famílias de abertura mantidas (as mais jogadas)
POR_FAIXA = 15_000      # máximo de partidas por faixa de rating em base.pl
POR_FAIXA_MINI = 500    # idem em base_mini.pl (para o SWISH)
SEMENTE = 42            # sorteio reprodutível
TAM_BLOCO = 500_000     # linhas lidas por vez (o CSV tem 4,1 GB)

CABECALHO = """\
:- encoding(utf8).

% =====================================================================
% Base de conhecimento: partidas {tipo} do Lichess (2016)
% Fonte: https://www.kaggle.com/datasets/arevel/chess-games
% Arquivo gerado automaticamente por etl.py. Não edite à mão.
% =====================================================================
%
% Domínio (universo de discurso):
%   - {n} partidas {tipo} do Lichess, sorteadas com até {por_faixa}
%     partidas por faixa de 200 pontos de rating.
%   - Ratings (Elo) das brancas e das pretas, resultados, aberturas
%     e formas de término.
%
% Predicado (axiomas não lógicos da teoria):
%   partida(Tipo, EloBrancas, EloPretas, Vencedor, ECO, Abertura, Termino, Lances)
%     "Houve uma partida de ritmo Tipo entre brancas de rating
%      EloBrancas e pretas de rating EloPretas, vencida por Vencedor,
%      aberta com a variante ECO da família Abertura, que terminou
%      por Termino depois de Lances lances."
%
%   Tipo       : átomo, sempre {tipo} nesta base
%   EloBrancas : inteiro, {elo_brancas}
%   EloPretas  : inteiro, {elo_pretas}
%   Vencedor   : white, black ou draw
%   ECO        : átomo, código ECO da variante em minúsculo (ex.: b90)
%   Abertura   : átomo, uma das {n_aberturas} famílias de abertura mais jogadas
%                (ex.: sicilian_defense)
%   Termino    : {terminos}
%   Lances     : inteiro, {lances} (lances completos: brancas + pretas)
%
% Propriedades garantidas pelo ETL (verificadas em etl.py):
%   ∀p (Lances(p) ≥ {min_lances})
%   ∀p (Vencedor(p) ∈ {{white, black, draw}})
%   ∀f (|{{p | faixa(p) = f}}| ≤ {por_faixa})
%   aberturas com nomes distintos no CSV geram átomos distintos
%
% Exemplo de consulta (área Query do SWISH):
%   ?- partida(_, _, _, Vencedor, b90, _, _, _).
% =====================================================================

"""


def para_atomo(texto: str) -> str:
    """Normaliza um texto para um átomo Prolog: minúsculo, ASCII, com underscores.

    "Queen's Gambit Accepted" vira queen_s_gambit_accepted.
    """
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")
    if not t or not t[0].isalpha():
        raise ValueError(f"não foi possível gerar um átomo válido a partir de {texto!r}")
    return t


def ritmo(event: str):
    """"Blitz tournament https://..." -> "blitz"."""
    e = str(event).lower()
    for r in RITMOS:
        if r in e:
            return r
    return None


def faixa(elo_medio: pd.Series) -> pd.Series:
    """Mesma regra de faixa/2 em regras.pl: faixas de 200 pontos, pontas em 800 e 2400."""
    return ((elo_medio // 200) * 200).clip(800, 2400).astype(int)


def contar_lances(an: pd.Series) -> pd.Series:
    """Nº de lances completos = quantidade de "1.", "2.", ... no texto dos lances.

    Cerca de 10% das partidas foram analisadas e trazem comentários como
    "1. e4 { [%eval 0.27] } 1... e5": os {...} são apagados antes de contar,
    e "1..." (lance das pretas) e decimais como "0.27" não contam.
    """
    sem_comentarios = an.str.replace(r"\{[^}]*\}", "", regex=True)
    return sem_comentarios.str.count(r"(?<![\d.])\d+\.(?!\.)")


def familia(opening: pd.Series) -> pd.Series:
    """"Sicilian Defense: Najdorf Variation" -> "Sicilian Defense";
    "Philidor Defense #3" -> "Philidor Defense"."""
    return (opening.str.split(":").str[0]
            .str.replace(r"\s*#\d+", "", regex=True)
            .str.strip())


def ler_partidas(caminho: Path) -> pd.DataFrame:
    """Lê o CSV em blocos e devolve só as partidas do ritmo TIPO, já limpas."""
    blocos = []
    for bloco in pd.read_csv(caminho, usecols=COLUNAS, chunksize=TAM_BLOCO):
        bloco["tipo"] = bloco["Event"].map(ritmo)
        bloco["vencedor"] = bloco["Result"].map(VENCEDOR)
        bloco = bloco[(bloco["tipo"] == TIPO)
                      & bloco["vencedor"].notna()             # tira resultado "*"
                      & (bloco["Termination"] != "Abandoned")]
        bloco = bloco.dropna(subset=["WhiteElo", "BlackElo", "Opening", "AN"])
        bloco["lances"] = contar_lances(bloco["AN"])
        bloco = bloco[bloco["lances"] >= MIN_LANCES]
        bloco["abertura"] = familia(bloco["Opening"])
        blocos.append(bloco.drop(columns=["Event", "Result", "Opening", "AN"]))
    return pd.concat(blocos, ignore_index=True)


def embaralhar(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém as TOP_ABERTURAS famílias, calcula a faixa e embaralha (semente fixa).

    Pegar as N primeiras de cada faixa depois disso = sortear N por faixa.
    """
    top = df["abertura"].value_counts().head(TOP_ABERTURAS).index
    df = df[df["abertura"].isin(top)].copy()
    df["faixa"] = faixa((df["WhiteElo"] + df["BlackElo"]) // 2)
    return df.sample(frac=1, random_state=SEMENTE)


def validar(df: pd.DataFrame, por_faixa: int) -> None:
    # Dois nomes de abertura diferentes não podem virar o mesmo átomo.
    origem: dict[str, str] = {}
    for nome in df["abertura"].unique():
        anterior = origem.setdefault(para_atomo(nome), nome)
        if anterior != nome:
            raise ValueError(f"colisão de átomo: {anterior!r} e {nome!r}")
    if not set(df["vencedor"]) <= set(VENCEDOR.values()):
        raise ValueError("vencedor fora de white/black/draw")
    if (df["lances"] < MIN_LANCES).any():
        raise ValueError(f"partida com menos de {MIN_LANCES} lances")
    if ((df["WhiteElo"] <= 0) | (df["BlackElo"] <= 0)).any():
        raise ValueError("rating não positivo")
    if (df["faixa"].value_counts() > por_faixa).any():
        raise ValueError(f"faixa com mais de {por_faixa} partidas")


def formatar_fato(r) -> str:
    return (f"partida({r.tipo}, {int(r.WhiteElo)}, {int(r.BlackElo)}, {r.vencedor}, "
            f"{para_atomo(r.ECO)}, {para_atomo(r.abertura)}, {para_atomo(r.Termination)}, "
            f"{int(r.lances)}).")


def intervalo(coluna: pd.Series) -> str:
    return f"{int(coluna.min())}..{int(coluna.max())}"


def escrever_base(df: pd.DataFrame, caminho: Path, por_faixa: int) -> None:
    validar(df, por_faixa)
    terminos = sorted(para_atomo(t) for t in df["Termination"].unique())
    conteudo = CABECALHO.format(
        tipo=TIPO,
        n=len(df),
        por_faixa=por_faixa,
        elo_brancas=intervalo(df["WhiteElo"]),
        elo_pretas=intervalo(df["BlackElo"]),
        n_aberturas=df["abertura"].nunique(),
        terminos=", ".join(terminos[:-1]) + " ou " + terminos[-1],
        lances=intervalo(df["lances"]),
        min_lances=MIN_LANCES,
    )
    conteudo += "\n".join(formatar_fato(r) for r in df.itertuples(index=False)) + "\n"
    caminho.write_text(conteudo, encoding="utf-8")
    print(f"{len(df)} fatos partida/8 escritos em {caminho}")


def main() -> None:
    entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else ENTRADA_PADRAO
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else SAIDA_PADRAO
    saida_mini = saida.with_name(saida.stem + "_mini" + saida.suffix)

    partidas = ler_partidas(entrada)
    print(f"{len(partidas)} partidas {TIPO} após a limpeza")

    embaralhadas = embaralhar(partidas)
    base = embaralhadas.groupby("faixa").head(POR_FAIXA)
    escrever_base(base, saida, POR_FAIXA)
    print("partidas por faixa:", base["faixa"].value_counts().sort_index().to_dict())
    escrever_base(embaralhadas.groupby("faixa").head(POR_FAIXA_MINI), saida_mini, POR_FAIXA_MINI)


if __name__ == "__main__":
    main()
