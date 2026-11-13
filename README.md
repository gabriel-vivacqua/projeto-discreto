# Projeto MatDis: Knowledge Engine de Xadrez

Base de conhecimento em Prolog com 120.617 partidas blitz do Lichess, construída a partir de um dataset do Kaggle, com perguntas sobre aberturas e rating respondidas por inferência lógica. A pergunta central é: qual a melhor abertura em cada faixa de rating?

Projeto individual de Lógica e Matemática Discreta (2026/1), por Gabriel Vivacqua.

## Dataset

- Fonte: [Chess Games](https://www.kaggle.com/datasets/arevel/chess-games) (Kaggle)
- Arquivo usado: `data/chess_games.csv` (tabela única, ~6,2 milhões de linhas, 4,1 GB)
- Cada linha é uma partida jogada no Lichess em 2016.
- O CSV não está no repositório porque passa do limite do GitHub. Veja [Como rodar](#como-rodar) para baixá-lo.

| Campo CSV | Tipo | No Prolog |
|---|---|---|
| `Event` | qualitativo | `Tipo` |
| `WhiteElo` | quantitativo | `EloBrancas` |
| `BlackElo` | quantitativo | `EloPretas` |
| `Result` | qualitativo | `Vencedor` |
| `ECO` | qualitativo | `ECO` |
| `Opening` | qualitativo | `Abertura` |
| `Termination` | qualitativo | `Termino` |
| `AN` (lances da partida) | quantitativo | `Lances` |

São 8 campos: 5 qualitativos e 3 quantitativos.

## Estrutura

```
data/chess_games.csv   dataset original (não versionado)
etl.py                 ETL: CSV -> base.pl e base_mini.pl
base.pl                base de conhecimento (120.617 fatos partida/8)
base_mini.pl           base reduzida para o SWISH (4.500 fatos)
regras.pl              regras auxiliares
perguntas.pl           perguntas
requirements.txt       dependência do ETL (pandas)
```

## Construção

### 1. ETL (`etl.py`)

Lê o CSV em blocos de 500 mil linhas e gera um fato por partida:

```prolog
partida(Tipo, EloBrancas, EloPretas, Vencedor, ECO, Abertura, Termino, Lances).
partida(blitz, 2013, 2201, black, b01, scandinavian_defense, normal, 28).
```

- Só partidas blitz (`Event` contém "Blitz", o que inclui torneios). Misturar ritmos confundiria o efeito da abertura com o do relógio, e blitz é o ritmo com mais partidas.
- Descarta partidas abandonadas, sem resultado (`*`) ou com menos de 2 lances (não chegaram a jogar a abertura).
- `Result` vira `white`, `black` ou `draw`.
- `Opening` vira a família da abertura: o texto antes do `:`, sem o sufixo `#N` (`Sicilian Defense: Najdorf Variation` -> `sicilian_defense`). A variante fica no `ECO` (`b90`).
- `Lances` conta os lances completos (`1.`, `2.`, ...) no campo `AN`. Cerca de 10% das partidas trazem comentários de análise (`1. e4 { [%eval 0.27] } 1... e5`), que são apagados antes da contagem. Sem isso, essas partidas teriam ~4 vezes mais lances.
- Textos viram átomos: minúsculos, sem acento, com `_`.
- Mantém as 40 famílias de abertura mais jogadas e sorteia (semente 42) até 15.000 partidas por faixa de rating, para nenhuma faixa dominar a base. A `base_mini.pl` usa o mesmo sorteio com 500 por faixa.
- Validações: nenhum par de aberturas distintas gerando o mesmo átomo, `Vencedor` em `white`/`black`/`draw`, `Lances >= 2`, ratings positivos e no máximo 15.000 partidas por faixa.

O cabeçalho de `base.pl` descreve o domínio, o significado do predicado e o tipo de cada argumento.

Resultado: 2.794.463 partidas blitz após a limpeza; 120.617 fatos em `base.pl` e 4.500 em `base_mini.pl`. Rodar de novo gera arquivos idênticos.

A faixa de uma partida é a média dos dois ratings, em faixas de 200 pontos:

| Faixa | 800 | 1000 | 1200 | 1400 | 1600 | 1800 | 2000 | 2200 | 2400 |
|---|---|---|---|---|---|---|---|---|---|
| Rating médio | < 1000 | 1000–1199 | 1200–1399 | 1400–1599 | 1600–1799 | 1800–1999 | 2000–2199 | 2200–2399 | ≥ 2400 |
| Partidas | 1.202 | 15.000 | 15.000 | 15.000 | 15.000 | 15.000 | 15.000 | 15.000 | 14.415 |

As pontas têm menos partidas porque o dataset tem poucas nesses níveis.

### 2. Regras auxiliares (`regras.pl`)

| Regra | Significado |
|---|---|
| `faixa/2`, `faixa_partida/3` | faixa de um rating / de uma partida (média dos dois ratings) |
| `faixas/1`, `aberturas/1` | domínio, sem repetição (`setof` + `table`, calculado uma vez) |
| `faixa_existe/1`, `abertura_existe/1`, `cor/1` | geradores do domínio, para não deixar variáveis livres no `findall` |
| `jogos_faixa/2` | número de partidas da faixa |
| `conta/3` | quantos elementos de uma lista são iguais a `X` |
| `min_jogos/1` | mínimo de 50 jogos para uma taxa ser considerada |
| `taxa_vitoria/5` | taxa de vitória de uma cor com uma abertura numa faixa |
| `taxa_geral/4` | mesma taxa, somando todas as aberturas |
| `zebra/2` | 1 se o jogador de rating menor venceu, 0 se o maior venceu |
| `margem/3` | margem de erro de 95% de uma proporção |
| `primeiros/3`, `arredonda/3`, `percentual/2`, `positivo/1` | utilidades |

### 3. Perguntas (`perguntas.pl`)

Todas usam agregação, ordenação, comparação ou composição de regras. Resultados na base completa (`base.pl`); `Pct` é uma taxa em %, `Margem` é a margem de erro de 95% em pontos percentuais.

**1. Qual a melhor abertura, para cada cor, em cada faixa de rating?**

Maior taxa de vitória entre as aberturas com pelo menos 50 jogos na faixa.

```prolog
?- melhor_abertura(white, Faixa, Abertura, Pct, Margem, N).
Faixa = 800, Abertura = french_defense, Pct = 50.6, Margem = 11.2, N = 77 ;
Faixa = 1000, Abertura = queen_s_gambit_accepted, Pct = 62.1, Margem = 7.5, N = 161 ;
Faixa = 1200, Abertura = queen_s_gambit_refused, Pct = 58.9, Margem = 6.5, N = 219 ;
Faixa = 1400, Abertura = nimzo_indian_defense, Pct = 65.7, Margem = 11.4, N = 67 ;
Faixa = 1600, Abertura = queen_s_gambit_accepted, Pct = 60.7, Margem = 6.2, N = 239 ;
Faixa = 1800, Abertura = queen_s_gambit_accepted, Pct = 65.2, Margem = 8.0, N = 135 ;
Faixa = 2000, Abertura = owen_defense, Pct = 56.7, Margem = 8.9, N = 120 ;
Faixa = 2200, Abertura = owen_defense, Pct = 67.6, Margem = 11.1, N = 68 ;
Faixa = 2400, Abertura = nimzo_larsen_attack, Pct = 60.0, Margem = 6.5, N = 220.

?- melhor_abertura(black, Faixa, Abertura, Pct, Margem, N).
Faixa = 800, Abertura = queen_s_pawn_game, Pct = 54.3, Margem = 8.7, N = 127 ;
Faixa = 1000, Abertura = bird_opening, Pct = 60.2, Margem = 10.5, N = 83 ;
Faixa = 1200, Abertura = bird_opening, Pct = 57.8, Margem = 10.2, N = 90 ;
Faixa = 1400, Abertura = van_t_kruijs_opening, Pct = 55.6, Margem = 4.9, N = 396 ;
Faixa = 1600, Abertura = four_knights_game, Pct = 59.4, Margem = 7.5, N = 165 ;
Faixa = 1800, Abertura = queen_s_pawn, Pct = 58.9, Margem = 8.5, N = 129 ;
Faixa = 2000, Abertura = bishop_s_opening, Pct = 52.5, Margem = 10.9, N = 80 ;
Faixa = 2200, Abertura = bishop_s_opening, Pct = 54.0, Margem = 13.8, N = 50 ;
Faixa = 2400, Abertura = polish_opening, Pct = 55.9, Margem = 12.7, N = 59.
```

O nome da família descreve a posição criada pelos dois lados, então a melhor "para as brancas" pode ser uma defesa escolhida pelas pretas (`owen_defense` é 1.e4 b6). As margens de ±4,9 a ±13,8 pp mostram que a P1 aponta candidatas, não um ranking firme.

**2. Qual a abertura mais jogada em cada faixa? A popularidade muda com o nível?**

`Pct` é a fatia das partidas da faixa.

```prolog
?- mais_jogada(Faixa, Abertura, N, Pct).
Faixa = 800, Abertura = king_s_pawn_game, N = 266, Pct = 22.1 ;
Faixa = 1000, Abertura = king_s_pawn_game, N = 2700, Pct = 18.0 ;
Faixa = 1200, Abertura = king_s_pawn_game, N = 1805, Pct = 12.0 ;
Faixa = 1400, Abertura = sicilian_defense, N = 1904, Pct = 12.7 ;
Faixa = 1600, Abertura = sicilian_defense, N = 2379, Pct = 15.9 ;
Faixa = 1800, Abertura = sicilian_defense, N = 2780, Pct = 18.5 ;
Faixa = 2000, Abertura = sicilian_defense, N = 2939, Pct = 19.6 ;
Faixa = 2200, Abertura = sicilian_defense, N = 3226, Pct = 21.5 ;
Faixa = 2400, Abertura = sicilian_defense, N = 3003, Pct = 20.8.
```

Muda: `king_s_pawn_game` lidera até 1200 e, a partir de 1400, a Siciliana assume e só cresce (12,7% -> 21,5%).

**3. Quais aberturas "funcionam no iniciante, mas não no avançado"?**

Queda da taxa de vitória das brancas da faixa 1000 para a 2000. O ranking é por `Z` (queda dividida pelo erro-padrão), e não pela queda bruta, que favoreceria aberturas com poucos jogos. Cada item é `Z-Abertura-QuedaEmPP`.

```prolog
?- ranking_queda(white, 1000, 2000, Top).
Top = [4.33-pirc_defense-17.5, 3.48-alekhine_defense-14.1, 2.98-scandinavian_defense-7.6, 2.95-queen_s_pawn-17.5, 2.42-nimzowitsch_defense-10.8].

?- resumo_queda(white, 1000, 2000, Total, ComQueda, QuedaGeral).
Total = 33, ComQueda = 22, QuedaGeral = 2.3.
```

Das 33 aberturas comparáveis, 22 caem, mas a taxa geral das brancas cai só 2,3 pp. Com 33 comparações, o corte de Bonferroni é |z| > 3,17: só `pirc_defense` (1.e4 d6) e `alekhine_defense` (1.e4 Nf6) passam. As duas deixam as brancas ocuparem o centro para atacá-lo depois, o que pune mais o iniciante (hipótese, não testada).

**4. Com que frequência o jogador de rating menor vence ("zebra"), conforme a diferença de rating aumenta?**

`Diferenca` em degraus de 100 pontos (`0` = 1 a 99, `500` = 500 ou mais). Empates e ratings iguais ficam de fora.

```prolog
?- taxa_zebra(Diferenca, Pct, N).
Diferenca = 0, Pct = 44.5, N = 57254 ;
Diferenca = 100, Pct = 33.0, N = 31195 ;
Diferenca = 200, Pct = 23.1, N = 14565 ;
Diferenca = 300, Pct = 15.7, N = 6429 ;
Diferenca = 400, Pct = 10.8, N = 2986 ;
Diferenca = 500, Pct = 6.8, N = 2136.
```

A chance de zebra cai a cada degrau, de 44,5% para 6,8%. Como a base tem o mesmo número de partidas por faixa, cada faixa pesa igual nessa média.

**5. Como empates, derrotas por tempo e tamanho das partidas mudam com o nível?**

`PctTempo` conta só as derrotas por tempo (com vencedor).

```prolog
?- perfil_faixa(Faixa, PctEmpate, PctTempo, MediaLances).
Faixa = 800, PctEmpate = 4.2, PctTempo = 35.1, MediaLances = 25.2 ;
Faixa = 1000, PctEmpate = 3.3, PctTempo = 29.9, MediaLances = 27.5 ;
Faixa = 1200, PctEmpate = 3.0, PctTempo = 27.0, MediaLances = 29.7 ;
Faixa = 1400, PctEmpate = 3.2, PctTempo = 26.5, MediaLances = 32.6 ;
Faixa = 1600, PctEmpate = 3.6, PctTempo = 26.5, MediaLances = 34.5 ;
Faixa = 1800, PctEmpate = 4.6, PctTempo = 27.4, MediaLances = 36.9 ;
Faixa = 2000, PctEmpate = 5.8, PctTempo = 28.3, MediaLances = 38.0 ;
Faixa = 2200, PctEmpate = 6.6, PctTempo = 27.5, MediaLances = 39.1 ;
Faixa = 2400, PctEmpate = 8.0, PctTempo = 24.2, MediaLances = 41.0.
```

As partidas ficam mais longas a cada faixa (25,2 -> 41,0 lances) e os empates sobem a partir de 1200 (3,0% -> 8,0%). Perder no relógio só é claramente mais comum na faixa 800 (35,1%).

## Como rodar

### Gerar a base

`base.pl` e `base_mini.pl` já estão no repositório. Para só fazer as perguntas, pule para SWISH ou SWI-Prolog local.

1. Baixe o dataset no Kaggle (botão Download) e descompacte em `data/`, de modo que exista `data/chess_games.csv`. Pela CLI do Kaggle, com o token em `~/.kaggle/kaggle.json`: `kaggle datasets download -d arevel/chess-games -p data/ --unzip`.
2. Rode o ETL (Python 3.10+ com pandas 2.x; testado com Python 3.12 e pandas 2.1):

```bash
pip install -r requirements.txt   # no Ubuntu 24.04, dentro de um venv
python3 etl.py
```

Leva cerca de 2 minutos e usa ~1,5 GB de RAM. Opcional: `python3 etl.py entrada.csv saida.pl` (escreve também `saida_mini.pl`).

### SWISH

1. Acesse https://swish.swi-prolog.org/ e crie um Program.
2. Cole, nesta ordem, o conteúdo de `base_mini.pl`, `regras.pl` e `perguntas.pl` na área Program. A `base.pl` (8 MB) é grande demais para colar.
3. Rode as queries acima na área Query.

Na base mini os números mudam e a pergunta 3 responde `false`, porque nenhuma abertura chega a 50 jogos nas duas faixas. Os resultados válidos são os da base completa.

### SWI-Prolog local

```bash
swipl base.pl regras.pl perguntas.pl
?- mais_jogada(Faixa, Abertura, N, Pct).
```

Testado com SWI-Prolog 9.0.4.

## Limitações

- Taxa de vitória não é causalidade: uma abertura com taxa alta pode refletir quem escolhe jogá-la, não um efeito dela.
- 50 jogos é um corte baixo, por isso a pergunta 1 mostra a margem de erro e a 3 ordena por `Z`.
- `queen_s_pawn` e `queen_s_pawn_game` são famílias separadas porque o Lichess as nomeia assim.
- Dados de 2016: o metagame do Lichess pode ter mudado.
