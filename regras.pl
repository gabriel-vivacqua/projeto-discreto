:- encoding(utf8).

% Regras auxiliares sobre partida/8. Carregar depois de base.pl.
% Faixa = faixa de rating de 200 pontos da média dos dois Elos
% (800 = abaixo de 1000, 2400 = 2400 ou mais).
% Taxas são frações entre 0 e 1; perguntas.pl as mostra em %.

% Faixas de rating

faixa(Elo, Faixa) :-
    F is (Elo // 200) * 200,
    Faixa is max(800, min(2400, F)).

faixa_partida(Faixa, Abertura, Vencedor) :-
    partida(_, EW, EB, Vencedor, _, Abertura, _, _),
    Media is (EW + EB) // 2,
    faixa(Media, Faixa).

% Domínio (sem repetição). table: o setof roda uma vez e o resultado
% é reaproveitado nas chamadas seguintes.

:- table faixas/1, aberturas/1.
faixas(Fs) :-
    setof(F, A^V^faixa_partida(F, A, V), Fs).
aberturas(As) :-
    setof(A, T^W^B^V^E^Tm^L^partida(T, W, B, V, E, A, Tm, L), As).

faixa_existe(F) :-
    faixas(Fs),
    member(F, Fs).

abertura_existe(A) :-
    aberturas(As),
    member(A, As).

% Cor deve ser ligada ANTES de conta/3: com Cor livre, ==(Cor) nunca
% é verdadeiro e toda taxa sairia 0.
cor(white).
cor(black).

jogos_faixa(Faixa, N) :-
    faixa_existe(Faixa),
    aggregate_all(count, faixa_partida(Faixa, _, _), N).

% Contagem e taxas

conta(X, Lista, N) :-
    include(==(X), Lista, Iguais),
    length(Iguais, N).

% Mínimo de jogos para uma taxa ser considerada.
min_jogos(50).

% Taxa de vitória de Cor com Abertura na Faixa, em N jogos.
taxa_vitoria(Cor, Faixa, Abertura, Taxa, N) :-
    cor(Cor),
    faixa_existe(Faixa),
    abertura_existe(Abertura),
    findall(V, faixa_partida(Faixa, Abertura, V), Todos),
    length(Todos, N),
    min_jogos(Min),
    N >= Min,
    conta(Cor, Todos, W),
    Taxa is W / N.

% Mesma taxa, somando todas as aberturas da faixa.
taxa_geral(Cor, Faixa, Taxa, N) :-
    cor(Cor),
    faixa_existe(Faixa),
    findall(V, faixa_partida(Faixa, _, V), Todos),
    length(Todos, N),
    N > 0,
    conta(Cor, Todos, W),
    Taxa is W / N.

% Zebra: Z = 1 se o jogador de rating menor venceu, 0 se o maior venceu.
% Bucket = diferença de rating em degraus de 100 (0, 100, ..., 500+).
% Empates e ratings iguais ficam de fora.
zebra(Bucket, Z) :-
    partida(_, EW, EB, V, _, _, _, _),
    V \== draw,
    EW =\= EB,
    D is abs(EW - EB),
    Bucket is min(500, (D // 100) * 100),
    (   (EW < EB, V == white ; EB < EW, V == black)
    ->  Z = 1
    ;   Z = 0
    ).

% Estatística

% Margem de erro (95%) de uma proporção P medida em N jogos.
margem(P, N, M) :-
    M is 1.96 * sqrt(P * (1 - P) / N).

positivo(X) :-
    X > 0.

% Utilidades

primeiros(N, Lista, Prefixo) :-
    length(Lista, Len),
    K is min(N, Len),
    length(Prefixo, K),
    append(Prefixo, _, Lista).

arredonda(X, Casas, Y) :-
    F is 10.0 ** Casas,
    Y is round(X * F) / F.

% Fração -> porcentagem com 1 casa (0.5061 -> 50.6).
percentual(Fracao, Pct) :-
    arredonda(Fracao * 100, 1, Pct).
