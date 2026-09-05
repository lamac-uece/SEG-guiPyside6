# Plano de desenvolvimento — Redesign da interface do SuperSeg

## 1. Objetivo

Migrar o layout atual (duas imagens lado a lado + toolbar de texto no topo) para um
layout com **uma única imagem central**, **rail de ferramentas à esquerda** e
**painel de tecidos/abas à direita**, no espírito visual do SegWeb, mantendo total
compatibilidade com a lógica já existente em `MainController`.

## 2. Escopo desta fase

Redesign de UI/UX do `ImageViewer` (`src/views/main_window.py`) e widgets associados
(`tissue_palette.py`, `toolbar.py`, `reference_panel.py`, `superpixel_panel.py`,
`params_dialog.py`, `percentages_widget.py`). **Sem alteração de algoritmos** de
segmentação, SLIC, CLAHE ou HU — apenas reorganização de onde e como essas ações
são acionadas. Observação: o `PlotWidgetModify` (reference_panel.py) deixa de ser
um segundo canvas fixo e seu conteúdo passa a ser exposto na aba Comparação
(§7.3), renderizado no canvas central único quando a aba está ativa.

## 3. Fluxo/pipeline de execução — preservado *(adicionado no feedback)*

O redesign **não altera a ordem nem as regras do fluxo de uso** já existente,
apenas atualiza como cada etapa é apresentada visualmente:

1. **Upload** — usuário abre o arquivo DICOM (`open` / `Ctrl+O`).
2. **Pré-processamento** — remoção de pele e objetos (`remove_objects` /
   `remove_skin`, via o dropdown do item 5.3) e aplicação do CLAHE
   (`toggle_clahe`, seção 6).
3. **Aplicação do superpixel** — `apply_superpixel` (`Ctrl+Shift+S`). **Antes**
   dessa etapa, a cor de tecido selecionada no momento e as labels de cores no
   painel direito (aba Segmentação) ficam **desativadas**, aparecendo somente
   **depois** que o superpixel é aplicado — mesmo comportamento de
   habilitação já implementado hoje em `TissuePalette.refresh`
   (`enabled = bool(state.superpixel_auth)`).

Isso é **apenas uma atualização de visualização da interface**: a paleta de
tecidos na nova UI (seção 7.1) precisa refletir esse mesmo estado
habilitado/desabilitado que a `TissuePalette` horizontal já trata hoje, sem
mudança de regra de negócio.

As ações de pré-processamento continuam sendo os mesmos métodos do
`MainController` e atualizam `dicom_image_array`/`base_image_array` em memória;
o resultado passa a ser renderizado no canvas central **único** (o antigo painel
direito "Imagem Conferência" deixa de existir como segundo canvas fixo — ver
§7.3). Quando ainda não há máscara pintada, o efeito aparece direto na vista de
trabalho; para inspecionar o pré-processado a qualquer momento, usa-se a aba
Comparação (somente leitura, sem pintura nem malha).

## 4. Layout geral

| Área | Conteúdo |
|---|---|
| Topbar | Nome do app, undo/redo, salvar |
| Rail esquerdo (ícones) | Ferramentas de interação com a imagem |
| Centro | Imagem única (máscara/superpixel), com a malha SLIC sempre visível na vista de trabalho; a aba Comparação troca o conteúdo central pelo pré-processado (sem pintura nem malha) |
| Lateral direita | Abas: **Segmentação** / **Índices** / **Comparação** |

## 5. Rail de ferramentas (ícones à esquerda)

### 5.1 Pincel — pintura de tecido
Mantém o fluxo atual: seleciona um tecido no painel direito e pinta superpixels
via `MainController.paint_superpixel`.

### 5.2 Borracha — apagar pintura *(corrigido no feedback)*
Ícone dedicado no rail que replica, em **clique único por superpixel**, o que a
lixeira `Clear` do toolbar matplotlib faz hoje na develop (`MplToolbar.change_undo`,
toolbar.py:47–77, tooltip "Undo a specific paint"). Especificação do fluxo
reaproveitado:

1. Ativar a ferramenta equivale ao `change_undo` **ligado**: define
   `state.undo` para o plot corrente (`state.undo = 1`, com `plot` fixo em 1 no
   canvas único).
2. O clique segue o fluxo normal `_mouse_event` →
   `MainController.paint_superpixel(x, y, segments, 1)`. Como `plot == 1 and
   s.undo == 1`, o branch de `MainController.paint_superpixel` (linhas 173–182)
   **apaga** aquele superpixel: `s.segmented_mask[segments == segment_id] = 0`,
   devolvendo-o ao estado "sem tecido" (a imagem base é restaurada em `mask3d`).
3. A cada clique apaga-se **um** superpixel — não é arraste e não apaga tudo;
   é possível apagar vários em cliques sucessivos.
4. A remoção continua sendo registrada no `UndoStack` antes da modificação
   (linha 171), então `Ctrl+Z`/undo restaura o superpixel apagado.
5. Voltar à ferramenta pincel desliga o modo (equivale ao `change_undo`
   desligado: `state.undo = 0`).

Restrições preservadas (já existentes): só funciona com superpixel aplicado
(`superpixel_auth`) e com pan/zoom desligados. Nota de implementação: hoje essa
lógica gerencia dois canvas/`plot` (`plotsuperpixelmask` e `plotwidget_modify`);
com um único canvas central ela simplifica para **um modo borracha** no canvas
de trabalho. Não é uma ação nova — é o fluxo existente por trás de um ícone
dedicado.

### 5.3 Remover objetos / pele — ícone próprio com menu dropdown *(ajustado no feedback)*
Um único ícone (ex.: varinha/objeto) que, ao ser clicado, abre um **menu
dropdown** com duas opções mutuamente exclusivas:
- Remover apenas objetos externos → `MainController.remove_objects`
- Remover pele e objetos → `MainController.remove_skin`

Substitui as duas entradas hoje espalhadas no menu `View`.

### 5.4 Lixeira — restaurar imagem original *(redefinido no feedback)*
Passa a corresponder ao que hoje é `View → Original Image`, ou seja,
`MainController.restore_original`. Não deve ser confundida com `reset_mask3d`
(reset da máscara 3D), que continua acessível pelo menu/Options por enquanto.

### 5.5 Pan / Zoom
Mantêm equivalência direta com as ferramentas do toolbar do matplotlib hoje
duplicadas em cada painel (`plotsuperpixelmask.toolbar` / `plotwidget_modify.toolbar`).
Com uma imagem só, existe apenas um toolbar.

### 5.6 Ajustes — vira parte de "Options", não um ícone isolado *(ajustado no feedback)*
Fica no menu/ícone **Options**, cobrindo os parâmetros hoje presentes no
`ParamsDialog`: parâmetros do SLIC/superpixel, parâmetros do CLAHE e aparência da
malha (cor/opacidade/modo). Comportamento:
1. Usuário clica no ícone de Options.
2. O painel de tecidos (lateral direita) é **sobreposto** por um painel de
   configurações no lugar, mantendo a mesma área da tela.
3. Ao clicar em "OK", as opções são aplicadas (reaproveitando a lógica já
   existente em `ImageViewer.changeOptions`) e o painel volta a mostrar a
   paleta de tecidos.

### 5.7 Salvar
Mantém `MainController.save_mask_action`.

## 6. CLAHE — mantido como está *(confirmado no feedback)*
O liga/desliga rápido do CLAHE (`toggle_clahe`) **não muda** — continua sendo um
toggle direto e visível, fora do painel de Options, por ser um ajuste que
profissionais já validam manualmente. O painel de Options citado no item
5.6 cobre apenas os *parâmetros* do CLAHE (clip limit, tile size etc.), não o
liga/desliga.

## 7. Painel direito — abas

### 7.1 Segmentação
Lista vertical de swatches de cor por tecido (substitui a `TissuePalette`
horizontal atual), com "Tecido atual" destacado no topo do painel. Segue
desabilitada até a aplicação do superpixel, conforme item 3.

### 7.2 Índices
Substitui a janela pop-up `PercentagesGraph` por conteúdo embutido nesta aba,
reaproveitando `PercentagesGraph.calculatePercentages`.

### 7.3 Comparação *(remodelado no feedback)*
Faz hoje o papel da imagem "Conferência" (`PlotWidgetModify`, reference_panel.py):
exibe o DICOM pré-processado em tons de cinza — **sem a pintura e sem a malha
do SLIC** — refletindo o pré-processamento aplicado até aquele momento (original,
remoção de objetos/pele e/ou CLAHE, via `state.dicom_image_array` /
`base_image_array`).

Não existe mais um segundo canvas fixo: esse conteúdo continua vivendo em
memória e, ao ativar a aba Comparação, **substitui temporariamente o conteúdo do
canvas central**; ao voltar para a aba Segmentação, o centro retorna à vista de
trabalho (máscara + malha).

A vista de Comparação é **somente leitura**: cliques não pintam nem apagam
(`superpixel_auth` continua valendo para a vista de trabalho, mas os eventos de
pintura são ignorados enquanto a aba estiver ativa). Pan/zoom permanecem
disponíveis.

O `Ctrl+T` (Toggle SuperPixel View) é **removido** da interface (ver §10): seu
efeito era apenas ocultar a malha na vista de trabalho (e travar a pintura ao
mesmo tempo). Com a imagem central única + aba Comparação, isso perdeu o
sentido — ver o resultado sem a malha equivale a ajustar a opacidade da malha
no painel Options, e a referência visual agora é a aba Comparação.

## 8. Tema do canvas — claro/escuro *(ajustado no feedback)*
Canvas da imagem passa a ter um fundo neutro escuro (não preto puro) no modo
escuro, para melhorar o contraste da imagem de CT em tons de cinza. O tema
**segue o tema do sistema operacional** (claro/escuro), sem precisar de uma
preferência separada dentro do app.

## 9. Menu simplificado
`Set Default Open Directory`, `Set Default Save Directory`, `Alternar`
(`num_segments`) e o **RD check** saem do menu `Options` e vão para uma área de
configurações dedicada (ícone de engrenagem), mantendo o menu principal só com
File/Help. O **RD check** (`Ctrl+Shift+D` / `radio_density_check_enabled`,
filtro por densidade HU usado na pintura, `MainController.paint_superpixel`)
entra como um checkbox marcado como "somente para testes", já que tende a ser
desabilitado no futuro e não é uma ação principal da interface. O atalho
continua valendo (§10).

## 10. Atalhos de teclado — mantidos *(adicionado no feedback)*
Todos os atalhos hoje definidos em `_create_actions` (`main_window.py`)
continuam existindo e disparando exatamente as mesmas ações, independentemente
de qual ícone/menu novo passa a expor cada função na UI:

| Atalho | Ação |
|---|---|
| `Ctrl+O` | Abrir arquivo |
| `Ctrl+Q` | Sair |
| `Ctrl+C` | Toggle CLAHE |
| `Ctrl+Shift+S` | Aplicar SuperPixel |
| `Ctrl+Shift+D` | Toggle RD check |
| `Ctrl+R` | Remover objetos |
| `Ctrl+Shift+R` | Remover pele e objetos |
| `Ctrl+S` | Salvar |
| `Ctrl+Z` | Undo (back paint) |
| `Ctrl+F` | Alternar (`num_segments`) |

O redesign muda **onde** cada ação é exposta visualmente (ícone, dropdown, aba
etc.), não os atalhos nem os métodos do `MainController`/`ImageViewer` por
trás deles.

`Ctrl+T` (Toggle SuperPixel View) foi **removido** da interface junto com este
redesign: seu efeito era ocultar a malha na vista de trabalho e, ao mesmo tempo,
desabilitar a pintura/paleta (`superpixel_auth`). Com a imagem central única e a
aba Comparação, isso perdeu o sentido — ocultar a malha equivale a ajustar a
opacidade da malha no painel Options, e a referência visual agora é a aba
Comparação (§7.3).

## 11. Fora do escopo desta fase / backlog
- **Minimapa**: descartado por ora, sem necessidade identificada.
- **Redo** (além do undo): `UndoStack` hoje só implementa `push`/`pop` (undo
  puro); adicionar uma pilha de redo fica como item futuro, não bloqueante
  para este redesign.
- **Reset/recovery da máscara 3D** (`reset_mask3d`/`recovery_mask3d`):
  permanece acessível via menu, fora do rail principal.

## 12. Mapeamento técnico (ação de UI → código existente)

| Ação na nova UI | Método/arquivo já existente | Status |
|---|---|---|
| Pincel | `MainController.paint_superpixel` | Existe |
| Borracha | `MplToolbar.change_undo` (modo `_Mode.CLEAR`) + branch de apagar em `MainController.paint_superpixel` (linhas 173–182); com canvas único, `plot` fixo em 1 e `state.undo` controlado pelo modo borracha | Existe, só ganha ícone dedicado e simplifica de dois plots para um |
| Remover objetos | `MainController.remove_objects` | Existe |
| Remover pele e objetos | `MainController.remove_skin` | Existe |
| Lixeira (restaurar original) | `MainController.restore_original` | Existe |
| Salvar | `MainController.save_mask_action` | Existe |
| Undo | `MainController.back_paint` | Existe |
| Redo | — | Backlog |
| Habilitação da paleta de tecidos pós-superpixel | `TissuePalette.refresh` (`state.superpixel_auth`) | Existe |
| Malha SLIC na vista de trabalho | Sempre visível (`show_superpixel` permanece `True`); remover `ImageViewer.toggleSuperPixelView` / `Ctrl+T` (§10) | Removido da UI |
| Painel Options (SLIC/CLAHE/malha) | `ImageViewer.changeOptions` + `ParamsDialog` | Existe, muda de modal para painel sobreposto |
| Toggle CLAHE on/off | `ImageViewer.HistMethodCLAHE` / `MainController.toggle_clahe` | Existe, mantido como está |
| Aba Índices | `PercentagesGraph.calculatePercentages` | Existe, muda de janela pop-up para aba |
| Aba Comparação (vista somente leitura) | Conteúdo de `PlotWidgetModify` (reference_panel.py: `DisableClahe`/`EnableClahe`/`DeleteObjects`/`DeleteSkinAndObjects`/`ResetDicom`) renderizado no canvas central único | Existe, muda de canvas fixo para troca de conteúdo no canvas central |
| RD check | `ImageViewer.toggleRadioDensityCheck` / `state.radio_density_check_enabled` (filtro HU em `MainController.paint_superpixel`) | Existe, muda do menu para o painel de configurações (engrenagem) |
| Renderização do pré-processamento | Antes desenhada em `PlotWidgetModify.*` (reference_panel.py); o alvo passa a ser o canvas central único | Muda o alvo de desenho, sem alterar a lógica |
| Diretórios padrão | `MainController.set_default_open_dir` / `set_default_save_dir` | Existe, muda de local no menu |

## 13. Perguntas em aberto
Sem pendências no momento — as dúvidas da rodada anterior (interação da
borracha, formato do menu de remover objetos/pele, origem do tema
claro/escuro) foram todas resolvidas e já refletidas nas seções 5.2, 5.3 e 8.