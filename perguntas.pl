:- encoding(utf8).

% Perguntas sobre a base. Carregar depois de base.pl e regras.pl.
% Pct = taxa em %, Margem = margem de erro de 95% em pontos percentuais.

% 1. Qual a melhor abertura, para cada cor, em cada faixa de rating?
%    (maior taxa de vitória entre as aberturas com pelo menos 50 jogos)
%    ?- melhor_abertura(white, Faixa, Abertura, Pct, Margem, N).
melhor_abertura(Cor, Faixa, Abertura, Pct, Margem, N) :-
    faixa_existe(Faixa),
    setof(T-A, N0^taxa_vitoria(Cor, Faixa, A, T, N0), Lista),
    last(Lista, Taxa-Abertura),
    taxa_vitoria(Cor, Faixa, Abertura, Taxa, N),
    margem(Taxa, N, M),
    percentual(Taxa, Pct),
    percentual(M, Margem).

% 2. Qual a abertura mais jogada em cada faixa? A popularidade muda
%    com o nível? (Pct = % das partidas da faixa)
%    ?- mais_jogada(Faixa, Abertura, N, Pct).
popularidade(Faixa, Abertura, N) :-
    faixa_existe(Faixa),
    abertura_existe(Abertura),
    aggregate_all(count, faixa_partida(Faixa, Abertura, _), N),
    N > 0.

mais_jogada(Faixa, Abertura, N, Pct) :-
    faixa_existe(Faixa),
    setof(Q-A, popularidade(Faixa, A, Q), Lista),
    last(Lista, N-Abertura),
    jogos_faixa(Faixa, Total),
    percentual(N / Total, Pct).

% 3. Quais aberturas "funcionam no iniciante, mas não no avançado"?
%    Queda da taxa de vitória de Cor entre duas faixas. O ranking é por
%    Z = queda / erro-padrão, e não pela queda bruta, que favoreceria
%    aberturas com poucos jogos (taxas que oscilam mais).
%    ?- ranking_queda(white, 1000, 2000, Top).      Top = [Z-Abertura-QuedaPP, ...]
%    ?- resumo_queda(white, 1000, 2000, Total, ComQueda, QuedaGeral).
queda(Cor, FaixaBaixa, FaixaAlta, Abertura, Delta, Z) :-
    taxa_vitoria(Cor, FaixaBaixa, Abertura, T1, N1),
    taxa_vitoria(Cor, FaixaAlta, Abertura, T2, N2),
    Delta is T1 - T2,
    EP is sqrt(T1 * (1 - T1) / N1 + T2 * (1 - T2) / N2),
    EP > 0,                             % evita divisão por 0 se a taxa for 0 ou 1
    Z is Delta / EP.

ranking_queda(Cor, FaixaBaixa, FaixaAlta, Top) :-
    setof(Z-A-D, queda(Cor, FaixaBaixa, FaixaAlta, A, D, Z), Crescente),
    reverse(Crescente, Decrescente),
    primeiros(5, Decrescente, Top5),
    maplist(arredonda_queda, Top5, Top).

arredonda_queda(Z-A-D, Z2-A-PP) :-
    arredonda(Z, 2, Z2),
    percentual(D, PP).

% Quantas aberturas dá para comparar, em quantas a taxa cai e quanto
% cai a taxa geral (todas as aberturas juntas), para comparação.
resumo_queda(Cor, FaixaBaixa, FaixaAlta, Total, ComQueda, QuedaGeral) :-
    findall(D, queda(Cor, FaixaBaixa, FaixaAlta, _, D, _), Ds),
    length(Ds, Total),
    include(positivo, Ds, Quedas),
    length(Quedas, ComQueda),
    taxa_geral(Cor, FaixaBaixa, G1, _),
    taxa_geral(Cor, FaixaAlta, G2, _),
    percentual(G1 - G2, QuedaGeral).

% 4. Com que frequência o jogador de rating menor vence ("zebra"),
%    conforme a diferença de rating aumenta?
%    ?- taxa_zebra(Diferenca, Pct, N).
%    Uma única varredura da base: junta os pares Bucket-Z e agrupa
%    pela chave (o "group by").
taxa_zebra(Bucket, Pct, N) :-
    findall(B-Z, zebra(B, Z), Pares),
    keysort(Pares, Ordenados),
    group_pairs_by_key(Ordenados, Grupos),   % [0-[1,0,...], 100-[...], ...]
    member(Bucket-Zs, Grupos),
    length(Zs, N),
    sum_list(Zs, S),
    percentual(S / N, Pct).

% 5. Como empates, derrotas por tempo e tamanho das partidas mudam
%    com o nível?
%    ?- perfil_faixa(Faixa, PctEmpate, PctTempo, MediaLances).
perfil_faixa(Faixa, PctEmpate, PctTempo, MediaLances) :-
    faixa_existe(Faixa),
    findall(V-T-L,
            ( partida(_, EW, EB, V, _, _, T, L),
              M is (EW + EB) // 2,
              faixa(M, Faixa) ),
            Jogos),
    length(Jogos, N),
    N > 0,
    findall(x, member(draw-_-_, Jogos), Empates),
    length(Empates, NE),
    % time_forfeit também tem empates (tempo esgotado contra material
    % insuficiente); derrota por tempo é só quando há vencedor
    findall(x, (member(R-time_forfeit-_, Jogos), R \== draw), Tempo),
    length(Tempo, NT),
    findall(L, member(_-_-L, Jogos), Ls),
    sum_list(Ls, SL),
    percentual(NE / N, PctEmpate),
    percentual(NT / N, PctTempo),
    arredonda(SL / N, 1, MediaLances).
