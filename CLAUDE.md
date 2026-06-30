# Dodo Starter Pack - Manifesto Anti-Vibe Coding

> Esse arquivo e lido pelo Claude no inicio de toda conversa.
> **Mantenha curto e direto.** Para regras deterministicas, use `.claude/settings.json`.
> Para conhecimento sob demanda e guias operacionais, consulte `.claude/skills/`.

## Regras Globais

**Este projeto segue as regras GSD definidas em `C:\Users\Admin\.claude\CLAUDE.md`:**
- Caveman Mode full
- RTK obrigatorio em terminal
- Fluxo GSD 4-D (Discuss -> Plan -> Execute -> Verify)
- Memoria ID-based (`resumo-de-trabalho.md`)
- Subagentes para tarefas complexas

**O que esta abaixo sao regras ESPECIFICAS deste projeto.**

---

## Stack do Projeto

- **Frontend:** HTML5, CSS3 Vanilla, JavaScript Moderno (ES6+)
- **Backend/Scripting:** Python 3.10+
- **Quality & Linting:** Ruff (Python), ESLint/Prettier (JS/HTML/CSS)
- **Testing:** Pytest (Python)

## Comandos Essenciais

```bash
# Setup de Ambiente
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Qualidade (RTK Mindset)
ruff check .
ruff format .
npx prettier --write .
pytest
```

## Regras Inegociaveis (Anti-Vibe Coding)

1.  **Codigo Sem Testes Nao Entra**: Cada nova logica publica ou funcionalidade deve ser acompanhada por testes equivalentes.
2.  **Nao Simule Execucoes**: Proibido fingir que um comando ou linter funcionou sem de fato roda-lo e obter o resultado real.
3.  **Auditoria Paginada (ID-Based)**: Qualquer mutacao ou decisao arquitetural deve ser registrada no `resumo-de-trabalho.md` sob um ID de observacao estruturado `[OBS-YYYYMMDD-NN]`.
4.  **Uso de Proxy RTK**: Toda interacao de terminal de desenvolvimento deve ser realizada de forma otimizada para tokens.
5.  **COMMIT PROIBIDO SEM AUTORIZACAO EXPLICITA**: Nunca faca commit, push ou deploy sem pedido direto do usuario. Commit automatico esta desativado. Aguarde instrucao explicita antes de enviar qualquer codigo ao repositorio.

## Modularização Obrigatória (Anti-Monolito)

1.  **Nenhum arquivo único**: Proibido concentrar toda a lógica em um único arquivo. Separe responsabilidades em módulos distintos.
2.  **Funções bem definidas**: Cada função deve ter uma única responsabilidade clara. Funções com mais de 50 linhas devem ser refatoradas.
3.  **Estrutura modular mínima**:
    - Python: Separe em pacotes (`__init__.py`) com módulos por domínio/funcionalidade
    - JavaScript: Use módulos ES6 (`import/export`) separados por feature
4.  **Critério de quebra**: Ao atingir 200+ linhas em um arquivo, avalie se há oportunidades de extração para módulos menores.
5.  **Nomeação semântica**: Módulos devem ter nomes descritivos do domínio que representam (ex: `auth.py`, `validators.js`, `db_operations.py`).
6.  **Frontend separado obrigatoriamente**:
    - HTML: Apenas estrutura semântica e referências a arquivos externos
    - CSS: Arquivos `.css` dedicados, nunca `<style>` inline
    - JavaScript: Arquivos `.js` dedicados, nunca `<script>` com código inline
    - Exceção: Micro-otimizações de performance (critical CSS inline) devem ser justificadas em comentário

**Exemplo de estrutura esperada:**
```
project/
├── src/
│   ├── main.py          # Entry point mínimo
│   ├── config/          # Configurações
│   ├── services/        # Lógica de negócio
│   ├── utils/           # Funções auxiliares
│   └── models/          # Estruturas de dados
```

## Estrutura de Dominio Recomendada

```
dodo-project/
|-- .claude/                   # Configuracoes do Claude Code
|   |-- settings.json          # Permissoes deterministicas e hooks wired
|   +-- skills/                # progressive disclosure de conhecimentos
|-- .githooks/                 # Hooks de git integrados para seguranca
|-- docs/                      # Documentacao tecnica do GSD Flow e RTK
|-- tests/                     # Suite de testes automatizados
|-- resumo-de-trabalho.md      # Historico linear de auditoria tecnica (GSD)
+-- CLAUDE.md                  # Esse manifesto
```

## Referencia Cruzada

> Regras globais de orquestracao, subagentes, auto-aperfeicoamento e correcao autonoma estao definidas em `C:\Users\Admin\.claude\CLAUDE.md`. Este manifesto contem apenas regras especificas do projeto.

## Setup Obrigatorio (Primeira Execucao)

Ao iniciar neste projeto pela primeira vez, execute:
- Windows: `.\setup.ps1`
- Linux/macOS: `bash setup.sh`

Isso ativa os hooks de seguranca e qualidade (.githooks). Sem isso, commits nao serao validados.
