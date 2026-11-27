# LUDIODLE

Jogo de adivinhação de palavras por proximidade semântica, inspirado no Contexto.me, com vocabulário próprio, **10 modos de jogo** (cada um com seu desafio diário), histórico local e funcionamento offline.

| Modo | Conteúdo |
|---|---|
| Normal | Vocabulário geral (≈11,6 mil palavras comuns) |
| Anime | Personagens famosos de animes |
| Naruto | Naruto e Shippuden |
| Futebol Americano | Os jogadores mais famosos da NFL atual |
| One Piece | O mundo de One Piece |
| Pokémon | Só Pokémon |

Cada modo tem vocabulário, ranking e sequência de desafios próprios. O progresso e o histórico são separados por modo.

## Como usar

**Localmente:** abra `index.html` no navegador, com a pasta `data/` ao lado. Não precisa de servidor, Node, banco de dados nem internet.

**GitHub Pages:** suba `index.html`, `sw.js` e a pasta `data/` na raiz do repositório e ative Pages. Na primeira visita o service worker guarda no cache o jogo, os dados de todos os modos e os desafios de hoje e dos próximos 4 dias, e depois funciona sem internet. Desafios antigos precisam ser abertos uma vez com internet para baixar o ranking.

Não cabe tudo em um único HTML: os rankings completos pesam ≈230 MB no total.

## Interface

Visual de câmera térmica: cada palavra é uma faixa cuja cor vai do azul (longe) ao vermelho e ao dourado (perto da resposta), e cada modo tem a sua cor de fundo. Fontes Anton e DM Sans (licença OFL) embutidas no `index.html`, então continua funcionando offline. Segue o tema claro/escuro do aparelho.

## Como o jogo funciona

- Cada palavra do vocabulário do modo tem uma posição de 1 a N em relação à palavra secreta (1 = a resposta).
- A posição vem de um arquivo pré-calculado por resposta. O navegador só consulta o número; não há cálculo semântico nas tentativas.
- Palavra fora do vocabulário: mensagem "Essa palavra não está no vocabulário", sem registrar nem gastar dica. Palavra repetida na partida não é registrada de novo.
- Flexões (jogando, joguei, jogaria, jogos, computadores) são reconhecidas e mapeadas ao lema cadastrado. Jogo (substantivo) e jogar (verbo) continuam separados.
- **Você quis dizer:** se a palavra não existe, o jogo sugere até 3 parecidas do vocabulário do modo (distância de edição + comparação fonética: gamakixi → Gamakichi, smothie → Smoothie). Clicar na sugestão registra a tentativa; a palavra digitada errada continua sem registrar nem gastar dica.
- **Dica:** revela uma palavra entre 30% e 70% do caminho até a resposta, tomando como referência a sua **melhor** posição (melhor = 300 → dica entre ≈90 e ≈210), sem repetir palavras já usadas. A posição 1 só pode ser revelada quando a sua melhor posição é a 2, e nesse caso conta como desistência.
- Ao fim da partida (vitória ou desistência), o botão **Ver as 200 mais próximas** mostra as 200 palavras mais próximas, com as suas tentativas marcadas.
- **Desafio diário:** o nº 1 de cada modo é 01/10/2026. A palavra do dia é `ordem[(n-1) mod total]`, onde `ordem` é uma permutação Fisher-Yates com seed fixa gravada nos dados do modo. Todos recebem a mesma palavra, independente de recarregar ou trocar de computador. A data usada é a do relógio do aparelho. Quando a sequência de um modo acaba, ela recomeça.
- Dados salvos em IndexedDB (fallback localStorage): modo, data, palavra, tentativas, posições, melhor posição, dicas, vitória/desistência e tempo. Partida inacabada continua ao reabrir. Jogos salvos antes da existência dos modos migram automaticamente para o modo Normal.

## Estrutura de dados

```
index.html, sw.js
data/modes.js                catálogo de modos e data de início
data/meta.js, data/r/        modo Normal (meta + 2.200 rankings)
data/<modo>/meta.js, r/      todos os modos curados
```

## Como cada vocabulário foi construído

**Normal (modelo de linguagem):** árvores de palavras dos 33 temas, filtradas por `pipeline/03_filter.py` e depois por `05_build_data.py`: só entram palavras com frequência razoável no português (`zipf ≥ 2,6`; nomes próprios só se `≥ 3,6`), sem inglês/jargão, sem risadas ("kkkk") e com vetor no modelo. Respostas do dia: só palavras comuns, minúsculas e coerentes com os temas. Resultado: ≈10 mil palavras e ≈3,5 mil respostas.

**Modos curados (Anime, Naruto, Futebol Americano, One Piece, Pokémon, Minecraft, Pokémon 1ª Geração, NFL Times, League of Legends):** vocabulário e semântica escritos à mão em `curated/<modo>.txt`, uma linha por palavra: `Palavra | característica*peso, ...`. A semelhança é o cosseno entre vetores de características (time, vila, tipo, golpes, posição, relações…), calculado por `pipeline/09_build_curated.py`. Não usa o modelo de linguagem, então nomes próprios têm vizinhos que fazem sentido (Charizard perto de Charmander e dos Pokémon de fogo/voador; Mahomes perto de Kelce, Rice e dos outros quarterbacks). Em todos os modos curados, qualquer palavra do vocabulário pode ser a resposta do dia (um `~` antes da palavra a tornaria só-palpite).

| Modo | Palavras | Respostas | Conteúdo |
|---|---|---|---|
| Anime | 347 | 347 | personagens famosos de Dragon Ball, Naruto, One Piece, Bleach, Demon Slayer, Shingeki, JJK etc. |
| Naruto | 154 | 154 | personagens conhecidos + conceitos famosos (Konoha, Rasengan, Sharingan, Akatsuki…) |
| Futebol Americano | 280 | 280 | só os jogadores atuais mais famosos (QB, RB, WR, TE, LB, CB, S e os principais da linha defensiva); sem times nem jogadas; proximidade por time + posição |
| One Piece | 181 | 181 | personagens conhecidos + conceitos famosos (Haki, Gomu, Wano, Yonkou…) |
| Pokémon | 841 | 841 | só Pokémon; vizinhança por tipo, família evolutiva, aparência, golpes, habilidades e número da Pokédex |
| Minecraft | 184 | 184 | mobs, minérios, itens, ferramentas, blocos, comidas, biomas, estruturas e conceitos famosos do jogo |
| Pokémon 1ª Geração | 151 | 151 | só os 151 Pokémon de Kanto; mesmas camadas do Pokémon |
| League of Legends | 173 | 173 | os 173 campeões; vizinhança por classe, rota, região, espécie, facção, parentescos e rivalidades da história |
| NFL Times | 32 | 32 | os 32 times; vizinhança por divisão, conferência, rivais, região, mascote e história |

Cada palavra citada nas tags de outra ganha automaticamente a própria tag (assim 'doflamingo' em Law liga a Doflamingo), e tags raras pesam mais que as comuns (IDF). **Pokémon (4 blocos):** a semelhança é a média ponderada de quatro cossenos: tipo/família/aparência (`pokemon.txt`, peso 1), golpes (`pokemon_extra_*.txt`, 0,7), habilidades (0,45) e número da Pokédex nacional (`pokemon_dex.txt`, 0,22; vizinhos de número ganham pouco, para só desempatar parentes de época). Pesos ajustáveis por `W_MV`, `W_HAB`, `W_DEX` ao rodar o build. Golpes e habilidades foram escritos de memória (4 golpes e 2–3 habilidades por Pokémon).

**Segunda ordem (vizinhos dos vizinhos):** a semelhança final é `S = S0 + 0,5·S2`, onde `S0` é o cosseno das tags e `S2` faz a média das semelhanças dos 12 vizinhos mais próximos de cada palavra. Isso desempata com sentido (quem tem vizinhos parecidos fica mais perto) em vez de por sorte; os empates no top-30 caíram de 12–36% para 4–17%. O build imprime métricas de qualidade: empates no top-30, reciprocidade (os 5 primeiros vizinhos de A têm A entre os 25 primeiros deles?, 97–99% nos modos curados, 81% no Pokémon) e os maiores 'hubs'. **Palavras compostas:** só as essenciais de cada tema (Fairy Tail, Gomu Gomu, Super Bowl, Mr Mime, Iron Valiant…). Escreva com espaço no `.txt`; no jogo vale com espaço, hífen, ponto ou junto (`fairy tail`, `fairy-tail`, `fairytail`, `Mr. Mime`). Se você digitar só uma parte (`fairy`), o jogo sugere a palavra composta. **Apelidos:** `=apelido` na linha de uma palavra (ex.: `Newgate | ..., =barbabranca`) faz o apelido levar à palavra sem entrar no vocabulário. `python audit.py <modo> [n] [palavras]` mostra os n vizinhos de cada resposta, para conferir se a semântica faz sentido. Para acrescentar palavras, edite o `.txt`, rode `python 09_build_curated.py <modo>` e `python 08_write_modes_js.py`, e substitua `data/<modo>/`.

## Semântica (congelada)

Modelo spaCy `pt_core_news_lg` 3.8.0 (vetores estáticos), 300 dimensões, normalização L2, similaridade de cosseno, desempate estável pelo índice do vocabulário. Hashes SHA-256 de vetores e vocabulário em cada `manifest.json`. Os rankings são arquivos prontos: mudar o modelo no futuro não altera desafios antigos.

## Viabilidade e armazenamento

- Cada arquivo de ranking guarda uma posição uint16 por palavra do vocabulário do modo (≈20 KB no Normal; menos de 1 KB nos curados). Só as palavras que podem ser resposta têm ranking completo: ranking de todas as palavras seria ≈800 MB no Normal.
- Normal: o sorteio diário vem de 3.904 palavras elegíveis (todas as palavras comuns do vocabulário, menos as da lista de exclusão); os rankings são gerados para as 2.200 primeiras da sequência embaralhada (≈6 anos). Para ir além, `python 05_build_data.py 3904`. Modos curados: de 93 a 822 respostas.
- Cada partida carrega um arquivo de ranking e um vetor de poucos milhares de posições na memória.

## Limitações conhecidas

- **Poucos dias nos modos curados:** a sequência repete depois de 262 (Anime), 181 (One Piece), 154 (Naruto), 280 (Futebol Americano), 822 (Pokémon), 184 (Minecraft), 151 (Pokémon 1ª Geração) 32 (NFL Times) ou 173 dias (League of Legends). É o preço de só aceitar personagens conhecidos; para aumentar, basta acrescentar linhas aos arquivos de `curated/`.
- **Semântica curada por mim, não aprendida:** as características foram escritas de memória e podem ter erros ou omissões (um personagem esquecido, uma relação fraca). O Normal usa o modelo antigo `pt_core_news_lg`, com vizinhos às vezes estranhos em palavras abstratas.
- Qualquer pessoa com as ferramentas do navegador pode ver o ranking de um dia e descobrir a resposta. Isso é inerente ao jogo offline.
- Testado só em Chromium automatizado, não em aparelhos reais nem em Safari/Firefox.

## Reconstruir e testar

```
pip install spacy wordfreq numpy playwright
pip install https://github.com/explosion/spacy-models/releases/download/pt_core_news_lg-3.8.0/pt_core_news_lg-3.8.0-py3-none-any.whl
cd pipeline
python 01_parse_raw.py && python 02_analyze.py && python 03_filter.py     # Normal
python 04b_extend_common.py && python 05_build_data.py 2200 && python 06_pack_js.py                      # Normal
for m in anime naruto fa onepiece pokemon; do python 09_build_curated.py $m; done  # curados
python 08_write_modes_js.py
python test_game.py && python test_modes.py && python test_offline.py
```
(Os testes usam `build/<modo>/`, gerado pelos scripts. No Normal, mover `build/*.json` e `build/bin` para `build/normal/` depois de rodar o passo 06.)

## Conferência com fontes externas

- **Normal (revisão do dicionário):** `04b_extend_common.py` acrescentou ≈1,5 mil palavras comuns que faltavam (lema de plurais, femininos e verbos) e ≈6 mil formas passaram a ser reconhecidas (flexões, `-mente`, diminutivos), levando ao lema. Das 30 mil palavras mais comuns do português, 91% das 5 mil primeiras e 77% das 10–20 mil agora são aceitas (antes 78% e 54%). Formas flexionadas valem a posição do lema. Respostas do dia: só minúsculas de conteúdo, frequência ≥ 3,5, sem inglês, siglas, nomes próprios, gentílicos, formas flexionadas, grafias de Portugal e as ≈900 palavras técnicas ou difíceis de `vocab/answer_exclude.txt` (revisado à mão; continuam valendo como palpite).
- **League of Legends:** os 173 campeões (lista conferida com a de lançamentos até Locke, 2026); regiões conferidas com uma lista pública por região; classes, rotas e relações de história (irmãos, rivais, facções como Lâmina Negra, Kinkou, Darkin) escritas de memória.
- **Pokémon:** número da Pokédex e tipos de todos os 841 conferidos com a lista nacional da Wikidex; sem Paradox e sem Type Null. Gerações 8 e 9 (e algumas famílias) ficam fora do vocabulário.
- **Anime, Naruto e One Piece:** vocabulário comparado com os personagens de mais de 10 mil favoritos do MyAnimeList; os que faltavam foram adicionados.
- One Piece: nomes e apelidos (Sakazuki/Akainu, Kuzan/Aokiji etc.) são uma palavra só.
- Revisão final de vocabulário: One Piece só até o arco de Wano e sem personagens obscuros; Minecraft só itens, mobs e blocos padrão.

- Recomeço: sementes novas em todos os modos e banco local novo; os dias começam todos do zero, mesma data inicial (01/10/2026).
- Página inicial = menu de jogos (endereço raiz, sem #); cada jogo abre em #modo/N; a logo e a aba Menu voltam à raiz.
