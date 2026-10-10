# Migração do formato `.learning/`

Para quem estudava com um projeto no formato do [learn-faster-kit](https://github.com/hluaguo/learn-faster-kit) (pasta `.learning/<tópico>/` com `syllabus.md`, `review_schedule.json` e, nas versões adaptadas, `question_bank.json`, `answer_key.json` e `attempts.jsonl`). Não há ferramenta automática: os formatos são diferentes o bastante para valer a pena refazer com o pipeline, aproveitando o material.

## O que corresponde a quê

| Formato antigo | Formato novo | Como levar |
|---|---|---|
| Pasta do projeto com PDFs e guias | `subjects/<slug>/fontes/` | Copie o material; provas e guias com gabarito vão em `fontes/provas/`. |
| `config.json` (`exam_date`, `daily_minutes`) | `materia.json` | O `/nova-materia` pergunta de novo; ou passe as respostas na linha de comando. |
| `syllabus.md` | `mapa-conhecimento.json` + `plano.md` | O ingestor gera o mapa das fontes; o motor gera o plano. Use o syllabus antigo como fonte (copie para `fontes/`) se ele tiver boa estrutura. |
| `question_bank.json` + `answer_key.json` | `banco/questoes.json` + `banco/gabarito.json` | Refaça pela extração das provas (com verificação às cegas). Os ids antigos não são reaproveitados. |
| `review_schedule.json` (escada fixa) | `estado/revisoes.json` (SM-2 limitado pela prova) | Não migra; as revisões recomeçam. Para manter a escada fixa: `"revisao": {"algoritmo": "escada-fixa"}` no `materia.json`. |
| `attempts.jsonl` | `estado/tentativas.jsonl` | Não migra (os ids das questões mudam). |
| `mastery.md`, `progress.md` | `estado/dominio.md`, `estado/diario.md` | Gerados pelo motor. |
| `/study`, `/review`, `/simulado`, `/progress` | `/estudar`, `/revisar`, `/simulado`, `/progresso` | Mesma ideia, com o protocolo reforçado. |
| `attempts.py check <id> <letra>` | `corrigir --questao Q --resposta R --confianca N` | Agora exige a confiança e uma apresentação antes. |
| `present.py` (específico de um layout de PDF) | `ingerir` + `apresentar` | O texto das provas é extraído uma vez para o banco; `apresentar` só lê o banco. |

## Passo a passo

1. Clone este repositório e crie `subjects/<slug>/fontes/` (slug sem acento nem espaço).
2. Copie o **material** (PDFs, guias, listas) para `fontes/`; provas e listas com gabarito em `fontes/provas/`. **Não** copie `answer_key.json` nem gabaritos soltos para fora de `fontes/provas/`.
3. Se as provas antigas vinham com a resposta marcada na página (por exemplo, em vermelho), responda "sim" a essa pergunta no `/nova-materia`: o `CLAUDE.md` da matéria passa a proibir imagens dessas páginas.
4. Rode `/nova-materia <slug>`. O banco é refeito a partir das provas, com verificação às cegas; questões divergentes ficam de fora até você decidir.
5. Abra uma sessão nova e rode `/estudar <slug>`. O diagnóstico inicial substitui o histórico antigo.

## O que fazer com o projeto antigo

Guarde-o (ele tem o seu histórico) num lugar fora deste repositório. Nada dele precisa vir para cá além do material de estudo.
