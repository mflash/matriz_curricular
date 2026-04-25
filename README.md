# Utilitário MCI - Matriz Curricular Interativa

Utilitário de linha de comando que, a partir de um arquivo JSON contendo a estrutura curricular de um curso de graduação, gera um único arquivo `HTML+CSS+JavaScript` com a matriz curricular de forma gráfica e interativa, pronto para ser hospedado em qualquer servidor web.

> Autor: Prof. Daniel Callegari, 2026

---

## Exemplo de Resultado

Veja aqui um exemplo de resultado do utilitário (criado a partir do exemplo [99TI.json](https://github.com/profdcallegari/matriz_curricular/blob/main/examples/99TI.json)).

[Acessar a página de um currículo de exemplo: 99TI](https://profdcallegari.github.io/matriz_curricular/)


## Funcionalidades

- Leitura de arquivo JSON com a estrutura completa do currículo
- Validação do JSON de entrada (códigos únicos, posições de pré-requisitos etc.)
- Geração de arquivo HTML único e auto-contido (sem dependências externas)
- Saída determinística: a mesma entrada sempre produz a mesma saída
- Compatível com Chrome, Edge, Safari e Firefox

### Visualização da Matriz

- Informações gerais do curso exibidas no topo
- Disciplinas organizadas em colunas por nível (semestre), com cabeçalho em algarismos romanos e total de créditos
- Ligações de pré-requisito com dois estilos selecionáveis por flag:
  - **`arrows`**: setas clássicas com ponta
  - **`paths`**: caminhos espessos estilo Sankey
- Opção de preenchimento dos cartões por categoria definida no JSON de entrada
- Três tipos de setas visuais:
  - **Linha sólida** — pré-requisito comum
  - **Linha tracejada** — pré-requisito especial
  - **Linha pontilhada** — co-requisito
- Switch global para ligar/desligar todas as linhas e rótulos de pré-requisitos
- Painel de legenda expansível/retrátil

### Interatividade

- **Hover sobre uma disciplina**: destaca a disciplina e seus pré-requisitos/dependentes, esmaece as demais e exibe apenas as setas relacionadas
- **Clique em uma disciplina**: abre um painel (popup) com todos os detalhes — código, nome, carga horária, créditos, ementa e tags

---

## Stack de Tecnologias

### Ferramenta CLI

| Tecnologia | Uso |
|---|---|
| **Node.js + TypeScript** | Plataforma e linguagem do gerador |
| dependências | não usar nenhum pacote externo |

### Arquivo HTML de saída

| Tecnologia | Uso |
|---|---|
| **HTML5** | Estrutura da página |
| **CSS Grid / Flexbox** | Layout em colunas por nível |
| **CSS Custom Properties** | Temas, cores e estados visuais |
| **SVG inline** | Setas de pré-requisito com roteamento ortogonal |
| **Vanilla JavaScript (ES2020+)** | Toda a lógica de interatividade |

---

## Estrutura do Projeto

```
matriz_curricular/
├── src/
│   ├── mci.ts                    # Entry point da ferramenta CLI
│   ├── types.ts                  # Tipos e interfaces compartilhados
│   ├── parser.ts                 # Leitura e validação do JSON de entrada
│   ├── layout.ts                 # Cálculo do layout das disciplinas
│   ├── router.ts                 # Algoritmo de roteamento das setas
│   ├── generator.ts              # Geração do HTML de saída
│   └── templates/
│       └── matrix.html.ts        # Template do arquivo HTML gerado
├── examples/
│   └── 99TI.json                 # Exemplo de currículo de entrada
├── dist/                         # Saída da compilação TypeScript (gerado)
├── descricao.txt
├── layout.md
├── README.md
├── package.json
└── tsconfig.json
```

---

## Formato do JSON de Entrada

```json
{
  "curriculum": {
    "code": "CDIA-2026",
    "name": "Bacharelado em Ciência de Dados e Inteligência Artificial",
    "availableSince": "2026/1",
    "description": "Descrição do curso.",
    "levels": 8
  },
  "courses": [
    {
      "code": "MAT101",
      "name": "Cálculo I",
      "hours": 60,
      "credits": 4,
      "level": 1,
      "syllabus": "Limites, derivadas e aplicações.",
      "tags": [],
      "category": "MAT"
    }
  ],
  "categories": [
    { "id": "MAT", "color": "#1d4ed8" },
    { "id": "COMP", "color": "#166534" },
    { "id": "HUM", "color": "#b45309" }
  ],
  "display": {
    "card_fill_style": "category"
  },
  "requirements": [
    {
      "type": "prerequisite",
      "from": "MAT101",
      "to": "MAT201"
    },
    {
      "type": "corequisite",
      "from": "PROG101",
      "to": "MAT101"
    },
    {
      "type": "special",
      "from": "PROG101",
      "to": "EST301",
      "description": "Conhecimentos básicos de programação"
    },
    {
      "type": "credit_requirement",
      "to": "EST301",
      "min_credits": 40
    }
  ]
}
```

### Tipos de Pré-requisito

| Tipo | Descrição | Representação Visual |
|---|---|---|
| `prerequisite` | Disciplina de nível anterior | Seta com linha sólida |
| `special` | Disciplina de nível anterior com descrição | Seta com linha tracejada |
| `corequisite` | Disciplina do mesmo nível | Seta com linha pontilhada |
| `credit_requirement` | Mínimo de créditos já cursados | Indicado no popup da disciplina |

### Categorias e preenchimento dos cartões

- `categories` é opcional e permite mapear `category -> cor`.
- Cada disciplina pode informar `course.category` para definir sua categoria visual.
- `display.card_fill_style` controla o estilo de preenchimento dos cartões:
  - `category`: preenche o cartão com a cor definida para `course.category` em `categories`
- O preenchimento só é aplicado quando `display.card_fill_style` estiver definido.
- Se não houver categoria mapeada para a disciplina, o cartão mantém o estilo padrão.

---

## Uso

```bash
# Limpar os artefatos de compilação (remove dist/, node_modules/ e package-lock.json)
npm run clean

# Instalar dependências
npm install

# Compilar o projeto
npm run build


# Gerar a matriz curricular (gera um arquivo HTML com o mesmo nome do arquivo JSON de entrada)
node dist/mci.js examples/99TI.json

# Escolher o estilo das ligações (setas clássicas)
node dist/mci.js examples/99TI.json --links arrows

# Escolher o estilo das ligações (caminhos estilo Sankey)
node dist/mci.js examples/99TI.json --links paths

# Exibir ajuda (sem argumentos de entrada)
node dist/mci.js
```

---

## Validações

O gerador verifica e reporta os seguintes erros no JSON de entrada:

- Códigos de disciplinas duplicados
- Pré-requisito comum (`prerequisite` / `special`) apontando para disciplina do mesmo nível ou de nível posterior
- Co-requisito (`corequisite`) apontando para disciplina de nível diferente
- Referência a código de disciplina inexistente em `requirements`
