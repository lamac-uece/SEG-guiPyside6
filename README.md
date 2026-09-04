# SEG — Segmentador Manual de Imagens DICOM

Ferramenta de segmentação manual de imagens tomográficas desenvolvida no **LAMAC (Laboratório de Métodos e Análise Computacional)** da UECE. Permite que pesquisadores delimitem e classifiquem tecidos corporais em imagens DICOM de forma interativa, gerando máscaras de segmentação exportáveis para análise posterior.

---

## Sumário

- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Pipeline de execução](#pipeline-de-execução)
- [Como executar](#como-executar)
- [Testes](#testes)
- [Requisitos](#requisitos)

---

## Funcionalidades

- Leitura de imagens DICOM (`.dcm`), incluindo arquivos comprimidos em JPEG Lossless
- Pré-processamento de imagem:
  - Remoção de objetos externos (mesa, lençol)
  - Remoção de pele
  - Equalização adaptativa de histograma (CLAHE) como opção On/Off
- Segmentação por superpixels via algoritmo SLIC
- Pintura manual interativa de regiões por tecido
- Suporte a múltiplos tecidos por imagem: Gordura, Gordura Intermuscular, Gordura Visceral, Osso, Músculo, Órgão e Outros
- Filtragem por densidade Hounsfield (HU) por tipo de tecido
- Desfazer pinturas (undo) com histórico de até 15 entradas
- Exportação e importação de máscaras em formato `.csv`
- Visualização de percentuais de área por tecido segmentado
- Configuração de diretórios padrão de abertura e salvamento

---

## Arquitetura

O projeto segue a arquitetura **MVC em camadas**, separando completamente interface gráfica, lógica de negócio e dados:

```
┌─────────────────────────────────────────────────────┐
│                     Views (PySide6)                 │
│  main_window · superpixel_panel · reference_panel   │
│  toolbar · params_dialog · percentages_widget       │
└──────────────────────┬──────────────────────────────┘
                       │ eventos / callbacks
┌──────────────────────▼──────────────────────────────┐
│                   Controller                        │
│                 main_controller                     │
└───────┬──────────────┬──────────────────────────────┘
        │              │
┌───────▼──────┐ ┌─────▼────────────────────────────┐
│    Models    │ │            Services              │
│ segmentation │ │ dicom_service · image_processing │
│    _state    │ │ mask_io · undo_manager           │
│ tissue_config│ └──────────────────────────────────┘
└──────────────┘
        │
┌───────▼──────┐
│    Utils     │
│ image_utils  │
│    modes     │
└──────────────┘
```

**Models** — estruturas de dados e constantes de domínio (`SegmentationState`, `tissue_config`)

**Services** — lógica de negócio pura, sem dependência de UI (`dicom_service`, `image_processing`, `mask_io`, `undo_manager`)

**Controllers** — intermediário entre view e services; único ponto que conhece ambos (`MainController`)

**Views** — exclusivamente interface gráfica; não acessam services diretamente

**Utils** — funções auxiliares genéricas de processamento de imagem

---

## Estrutura de pastas

```
SEG-guiPyside6/
├── app.py                          # Entrypoint da aplicação
├── requirements.txt                # Dependências de produção
├── conftest.py                     # Configuração do pytest
│
├── assets/                         # Recursos estáticos da interface
│   ├── icon.png
│   └── trash.png
│
├── local/                          # Configuração local de máquina (gitignored)
│   ├── defaultImageDir.txt
│   └── defaultMaskDir.txt
│
├── src/
│   ├── controllers/
│   │   └── main_controller.py      # Coordena view ↔ services
│   │
│   ├── models/
│   │   ├── segmentation_state.py   # Estado global encapsulado
│   │   └── tissue_config.py        # Constantes de tecidos e HU
│   │
│   ├── services/
│   │   ├── dicom_service.py        # Leitura e decompressão de DICOM
│   │   ├── image_processing.py     # CLAHE, SLIC, remoção de pele
│   │   ├── mask_io.py              # Leitura e escrita de máscaras CSV
│   │   └── undo_manager.py         # Histórico de pinturas (UndoStack)
│   │
│   ├── utils/
│   │   ├── image_utils.py          # Funções auxiliares de imagem
│   │   └── modes.py                # Enum de modos da toolbar
│   │
│   └── views/
│       ├── main_window.py          # Janela principal (ImageViewer)
│       ├── superpixel_panel.py     # Painel de pintura com superpixels
│       ├── reference_panel.py      # Painel de conferência da imagem
│       ├── toolbar.py              # Toolbar matplotlib estendida
│       ├── params_dialog.py        # Diálogo de parâmetros SLIC/CLAHE
│       ├── percentages_widget.py   # Gráfico de percentuais por tecido
│       └── dialogs.py              # Diálogos auxiliares
│
└── tests/
    ├── unit/
    │   ├── test_image_utils.py
    │   ├── test_image_processing.py
    │   └── test_mask_io.py
    └── integration/
        └── test_pipeline.py
```

---

## Pipeline de execução

O fluxo principal da ferramenta segue estas etapas:

```
1. Abertura
   └── Arquivo .dcm  →  dicom_service.dicom2array()
                    →  Escala HU aplicada (RescaleSlope + RescaleIntercept)

2. Pré-processamento (opcional, aplicável em qualquer ordem)
   ├── Remove Objects  →  image_processing.select_RoI()
   ├── Remove Skin     →  image_processing.removeSkinAndObjects()
   └── CLAHE           →  image_processing.apply_clahe()

3. Superpixels
   └── image_processing.compute_superpixels()  (algoritmo SLIC)
       └── Parâmetros configuráveis: n_segments, sigma, compactness,
           max_num_iter, min_size_factor, max_size_factor

4. Pintura manual
   ├── Clique na região  →  controller.paint_superpixel()
   ├── Filtragem HU ativa →  aplica máscara de gordura ou músculo
   ├── Undo (Port)        →  undo_manager.UndoStack.pop()
   └── Undo por clique    →  modo Clear ativo na toolbar

5. Exportação
   └── Save  →  mask_io.save_mask()  →  arquivo .csv

6. Reabertura de máscara
   └── Arquivo .csv  →  mask_io.load_mask()
                    →  controller.recovery_mask3d()
```

**Formato do arquivo `.csv` de máscara:**

```
linha 0..N-3  →  linhas da segmented_mask (inteiros separados por vírgula)
linha N-2     →  informações dos tecidos: "r,g,b,identifier,tissue " por tecido
linha N-1     →  área total em pixels
```

---

## Como executar

### Pré-requisitos

- Python >= 3.10.9
- pip

### Instalação

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd SEG-guiPyside6

# Crie e ative o ambiente virtual
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

### Execução

```bash
python app.py
```

### Uso básico

1. **File → Open** — abre um arquivo `.dcm` ou uma máscara `.csv` salva anteriormente
2. **View → Remove Objects** — remove mesa e objetos externos (opcional)
3. **View → Remove Skin and Objects** — remove também a camada de pele (opcional)
4. **View → Hist CLAHE** — liga/desliga a equalização de histograma (opcional); é aplicada uma única vez sobre a imagem atual e pode ser desativada sem distorcer o resultado
5. **View → SuperPixel** — gera a segmentação por superpixels
6. Clique nas regiões da imagem para pintar o tecido atual
7. Use o ícone de cor na toolbar superior para trocar de tecido
8. **File → Save** ou `Ctrl+S` — exporta a máscara em `.csv`

### Atalhos de teclado

| Atalho | Ação |
|--------|------|
| `Ctrl+O` | Abrir arquivo |
| `Ctrl+S` | Salvar máscara |
| `Ctrl+Z` | Desfazer última pintura |
| `Ctrl+C` | Ligar/desligar CLAHE |
| `Ctrl+Shift+S` | Gerar SuperPixel |
| `Ctrl+T` | Toggle visualização de superpixels |
| `Ctrl+R` | Remover objetos externos |
| `Ctrl+Shift+R` | Remover pele e objetos |
| `Ctrl+Shift+D` | Toggle filtragem por densidade HU |
| `Ctrl+Q` | Sair |

### Configuração de diretórios padrão

Acesse **Options → Default Open Directory** e **Options → Default Save Directory** para configurar os diretórios padrão de abertura e salvamento. As preferências são salvas em `local/` e não são versionadas.

---

## Testes

```bash
# Instale as dependências de desenvolvimento
pip install pytest

# Todos os testes
pytest tests/ -v

# Apenas unitários
pytest tests/unit/ -v

# Apenas integração
pytest tests/integration/ -v
```

Os testes de integração que dependem de um arquivo DICOM real (`test.dcm`) são automaticamente ignorados se o arquivo não estiver presente na raiz do projeto.

---

## Requisitos

Principais dependências e suas funções no projeto:

| Biblioteca | Versão | Uso |
|---|---|---|
| PySide6 | 6.6.3 | Interface gráfica |
| numpy | 1.26.4 | Operações matriciais sobre imagens |
| pydicom | 2.4.4 | Leitura de arquivos DICOM |
| pylibjpeg | 1.4.0 | Decompressão JPEG Lossless |
| scikit-image | 0.22.0 | SLIC, CLAHE, morfologia |
| opencv-python | 4.9.0.80 | Processamento de imagem |
| matplotlib | 3.8.4 | Visualização e canvas interativo |
| scipy | 1.12.0 | Transformadas de distância e morfologia |

## TODO

* [] Corrigir continuade de segmentação após abrir um arquivo csv "encima" de uma mesma DICOM
* [] Implementar segmentação semiautomática de tomo a partir de um modelo
* [] Implementar salvamento de dados de porcentagem e estado global