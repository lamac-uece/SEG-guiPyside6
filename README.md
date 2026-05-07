# SuperSeg: Ferramenta de Segmentação Manual de Tomografias com Superpixels

## 1. Visão Geral do Projeto

SuperSeg é uma aplicação desktop desenvolvida em Python com o objetivo de **auxiliar na segmentação manual de tomografias computadorizadas (TC)** — especialmente cortes axiais no nível **L3** — utilizando **técnicas de superpixels** para facilitar e acelerar o processo de anotação para estudos de composição corporal.

A interface gráfica permite ao usuário:

- carregar arquivos DICOM,
- visualizar e processar as imagens,
- aplicar algoritmos como SLIC Superpixels, CLAHE, remoção de pele/objetos,
- pintar regiões usando segmentação baseada em superpixels,
- salvar segmentações manualmente no formato CSV (ground truth),
- abrir segmentações anteriores para revisão ou edição.

O software foi projetado para ser utilizado em laboratórios de pesquisa, hospitais e universidades que trabalham com análise de gordura visceral, gordura subcutânea e massa muscular em TC.

## 2. Objetivo do Projeto

O objetivo principal do SuperSeg é fornecer:

- uma ferramenta estável, rápida e intuitiva
- para gerar segmentações manuais que servirão como ground truths
- para uso em validação de modelos de IA, processamento de imagens médicas e pesquisas científicas.

O foco é reduzir esforços repetitivos na segmentação, oferecendo:
- navegação fluida,
- superpixels para delimitar automaticamente regiões homogêneas,
- ferramentas visuais de apoio,
- salvamento estruturado de dados.

## 3. Principais Funcionalidades

A interface gráfica do SuperSeg oferece diversas funções distribuídas em menus e atalhos. As principais incluem:

### 3.1 Abertura e Visualização

- Abrir imagens DICOM (Ctrl + O)
- Visualização lado a lado (imagem original e imagem com superpixels)
- Zoom e Pan interativos
- Reset de zoom e navegação

### 3.2 Segmentação Manual Baseada em Superpixels

- Aplicação do algoritmo SLIC (Ctrl + Shift + S)
- Pintura de superpixels clicando sobre eles
- Alteração de cores associadas a cada tecido
- Ferramenta de borracha para remover segmentações locais
- Atalho de desfazer (Ctrl + Z) com histórico limitado por 10 ações

### 3.3 Pré-Processamentos Disponíveis

- Remove Objects (Ctrl + R): remove cama, lençóis e objetos externos
- Remove Skin and Objects (Ctrl + Shift + R): remove objetos e também a pele
- Hist CLAHE (Ctrl + C): realça detalhes por equalização adaptativa do histograma

### 3.4 Salvamento e Carregamento de Segmentações

- Exportar segmentação no formato .csv (Ctrl + S)
- Visualização da segmentação sobre a imagem original
- Reabrir arquivos .csv para análise
- Combinar .csv com DICOM correspondente para edição posterior
- Cálculo automático das porcentagens de tecido segmentado

### 3.5 Configurações Internas

Opção “Options” da barra de ferramentas:
- Alterar número de superpixels
- Ajustar parâmetros de processamento
- Escolher pasta padrão de abertura
- Escolher pasta padrão de salvamento

## 4. Arquitetura do Projeto (Completa)

A seguir, uma descrição aprofundada da implementação interna dos arquivos functions.py e app.py.

### 4.1 Arquitetura Interna — Módulo functions.py

functions.py contém toda a lógica científica do projeto: leitura, pré-processamento, segmentação e manipulação de máscaras binárias e multiclasses.

#### 4.1.1 Processamento de Máscaras

bitwise_minus(img1, img2)

- Implementa a operação lógica img1 - img2 entre máscaras binárias.

remove_small_CCs(mask, thres)

- Remove componentes conectados com área inferior ao limiar thres:
- reduz ruídos
- remove pequenos objetos indesejados durante a segmentação

find_extreme_points(img, thresh=None)

- Localiza os pontos extremos (esquerda, direita, topo, base) da máscara.

compose_muscle_mask(muscle, skmuscle, tol)

- Combina máscara de músculo e músculo esquelético adicionando uma faixa superior para manter a coerência anatômica.

#### 4.1.2 Segmentação por HU (Hounsfield Units)

Dicionário materials

Contém faixas HU de:

- osso
- músculo
- músculo esquelético
- gordura
- gordura visceral
- gordura intramuscular
- ar

tissue_segmentation(image, tissue)

- Retorna máscara binária dos pixels cuja HU pertence ao tecido selecionado.

select_RoI(image)

- Remove cama e objetos externos mantendo apenas a maior componente conectada acima do ar.

#### 4.1.3 Leitura e Conversão de DICOM

dicom2array(dcm)

- Detecta compressão (JPEG Lossless)
- Descomprime via pylibjpeg se necessário
- Converte pixel_array para HU usando Slope/Intercept

ConvertToUint8(image)

- Normaliza HU para faixa 0–255 para visualização.

#### 4.1.4 Remoção de pele e objetos

removeSkinAndObjects(image, m)

Pipeline avançado:

- Segmentação HU inicial
- Cálculo de máscara do corpo
- Transformada de distância (EDT)
- Estimativa automática da espessura de pele (função do perímetro corporal)
- Remoção adaptativa de gordura subcutânea
- Refinamento morfológico (closing, fill holes, ecc.)
- Subtração da pele da imagem original

#### 4.1.5 Interface auxiliar

CustomDialog

- Caixa de diálogo usada ao carregar um CSV perguntando se o usuário deseja reaproveitar a máscara existente.

### 4.2 Arquitetura Interna — Módulo app.py

app.py implementa toda a interface gráfica utilizando PySide6, além do fluxo de segmentação manual baseado em superpixels e pintura.

#### 4.2.1 PlotWidgetModify (painel de pré-processamento)

Gerencia:

- visão “Imagem Conferência”
- aplicação de CLAHE
- remoção de objetos
- remoção de pele
- reset da imagem

Mantém sincronização com a imagem principal (dicom_image_array).

#### 4.2.2 PlotSuperPixelMask (painel de pintura)

Painel principal de segmentação manual:

- exibe máscara colorida (mask3d)
- exibe ou oculta limites dos superpixels
- aplica SLIC
- captura cliques do mouse
- pinta superpixels inteiros
- sincroniza com segmentedMask
- exibe máscara salva ao abrir CSV

É o coração visual da ferramenta.

#### 4.2.3 Mouse Events e Pintura

O app utiliza duas funções centrais:

mouse_event(event, plot_id): Identifica:

- botão pressionado
- coordenadas do clique
- painel associado
- modo atual (pintura, borracha, visualizar superpixels)

paintSuperPixel(event): Executa a lógica principal:

- identifica superpixel clicado
- pinta ou apaga toda a região
- valida densidade HU se o filtro estiver ativado
- atualiza máscara RGB (mask3d)
- ajusta matriz segmentedMask
- salva estado para permitir Ctrl+Z

#### 4.2.4 PercentagesGraph

Calcula automaticamente a área (%) segmentada por tecido selecionado:

- gordura
- músculo
- osso
- vísceras
- etc.

Mostra gráfico em janela separada.

#### 4.2.5 Form (Configurações Internas)

Permite alterar:

- número de superpixels
- compactness
- sigma
- parâmetros de remoção de pele
- parâmetros de CLAHE

Todas as mudanças são aplicadas dinamicamente.

#### 4.2.6 MplToolbar (Toolbar personalizada)

Adiciona:

- Pan
- Zoom
- Home
- Save
- Undo (Back)
- Clear (Remove superpixel)
- Toggle Superpixel View
- Informações adicionais na GUI

#### 4.2.7 Classe ImageViewer (janela principal)

Responsável por:

- menus
- atalhos
- associação de cores a tecidos
- abertura de DICOM/CSV
- reconstrução de máscara salva
- controle dos dois painéis (superpixels e imagem modificada)
- salvamento com estrutura consistente

O método open() é particularmente rico:

Se for DICOM:

- converte
- aplica ROI
- configura cores/tipos
- atualiza HU de referência

Se for CSV:

- restaura máscara completa
- restaura cores
- restaura identificadores
- restaura tecidos

#### 4.2.8 Salvamento da máscara

O botão Save salva:

- segmentedMask completa
- cores correspondentes
- identificadores
- tecidos
- área total do ROI

Formato compatível para reabertura e edição.

#### 4.2.9 Execução

```py
if __name__ == '__main__':
    app = QApplication(sys.argv)
    imageViewer = ImageViewer()
    imageViewer.show()
    sys.exit(app.exec())
```

## 5. Fluxo Geral de Uso

1. Selecionar um arquivo DICOM
2. Aplicar pré-processamentos opcionais
3. Aplicar superpixels (SLIC)
4. Escolher o tecido a ser segmentado
5. Pintar regiões clicando nos superpixels
6. Ajustar zoom/pan conforme necessário
7. Salvar segmentação (CSV)
8. Consultar estatísticas de porcentagens
9. Opcionalmente reabrir o CSV para editar