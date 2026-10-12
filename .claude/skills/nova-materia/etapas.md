# Formatos e regras da preparação

## Mapa de conhecimento (`mapa-conhecimento.json`)

```json
{
  "schema_version": 1,
  "materia": "<slug>",
  "conceitos": [
    {
      "id": "prob-condicional",
      "nome": "Probabilidade condicional",
      "descricao": "Probabilidade de A sabendo que B ocorreu: P(A|B) = P(A e B) / P(B).",
      "tema": "probabilidade condicional",
      "peso": 3,
      "prerequisitos": ["prob-classica"],
      "fontes": [{"arquivo": "apostila.pdf", "local": "página 12"}],
      "origem": "fontes",
      "equivocos": ["confundir P(A|B) com P(B|A)"]
    }
  ]
}
```

- `id`: minúsculas sem acento, com hífens. `tema` agrupa conceitos parecidos (usado para intercalar e no painel).
- `peso` de 1 a 5: importância e recorrência (conceito que cai em toda prova vale mais).
- `fontes`: arquivo relativo a `fontes/` e onde aparece. Conceito que não está nas fontes leva `"origem": "conhecimento-geral"` e é dito assim ao aluno.
- `equivocos`: confusões típicas; alimentam os distratores e o novato do `/ensinar`.
- 8 a 25 conceitos costumam bastar. Pré-requisitos formam uma ordem de estudo (sem ciclos).

## Rascunho de questões (`banco/rascunhos/<lote>.json`)

```json
{
  "schema_version": 1,
  "lote": "lote-01",
  "questoes": [
    {
      "tipo": "multipla-escolha",
      "enunciado": "Uma urna tem 3 bolas brancas e 2 pretas...",
      "alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."},
      "conceitos": ["prob-condicional"],
      "dificuldade": 2,
      "figura": {"descricao": "Diagrama de árvore com dois ramos..."},
      "origem": {"tipo": "fonte", "arquivo": "provas/prova-2025.pdf", "pagina": 2, "numero": 3},
      "gabarito": {
        "resposta": "C",
        "conceito_decisivo": "condicionar ao evento observado",
        "solucao": "P(B|A) = ... = 3/5",
        "distratores": {"A": "confundiu P(A|B) com P(B|A)", "B": "...", "D": "...", "E": "..."}
      }
    }
  ]
}
```

- Tipos: `multipla-escolha` (alternativas A, B, C... em ordem), `numerica` (`"gabarito": {"resposta": {"valor": 0.6, "tolerancia_rel": 0.01}, "erros_comuns": [{"valor": 0.4, "explicacao": "..."}], ...}`) e `aberta` (`"gabarito": {"rubrica": ["critério 1", "critério 2"], ...}`).
- `distratores`: para **cada** alternativa errada, o equívoco específico que a torna tentadora. Nada de alternativa absurda.
- O enunciado e as alternativas **não podem** conter marcas de resposta ("correta", "gabarito", "[x]"). O motor recusa o rascunho inteiro se houver.
- `origem`: `{"tipo": "fonte", ...}` para questões extraídas (com arquivo, página e número) ou omitida para questões originais.
- `figura`: descrição em texto do que a figura mostra, suficiente para resolver. Se a página tinha a resposta marcada, não a registre na descrição.
- Fórmulas em LaTeX no enunciado, nas alternativas, na solução e nos distratores (`$F_x = F\\cos\\theta$`). No JSON, a barra invertida é sempre **dupla** (`\\frac`, `\\theta`): com barra simples, `\f`, `\t`, `\b`, `\n` e `\r` viram caracteres de controle e o motor recusa o rascunho. Número sozinho fica fora do LaTeX (`10`, não `$10$`), porque o app não o renderiza. Dinheiro como `R$ 10` (sem `$` de fechamento).

## Questões originais (escritor)

- Uma hipótese muda por questão em relação às questões das fontes (com atrito → sem atrito, outro valor de referência): é assim que provas costumam cobrar.
- Misture tipos: conceitual (escolher a ferramenta), numérica, leitura de gráfico ou tabela, híbrida.
- Confira **todas** as contas com `bash bin/tutor.sh calc` antes de gravar. Se a conta e a alternativa discordarem, corrija a questão.
- Idioma da matéria (`materia.json`), notação simples, sem dados desnecessários (mas um distrator numérico plausível é bem-vindo).

## Verificação às cegas

- O `verificador` só enxerga a questão (`apresentar --modo verificacao`) e a calculadora; registra sua resposta e confiança com `banco registrar-verificacao`. Ele não vê gabarito, fontes nem rascunhos (a guarda impede).
- `banco comparar`: `verificada` = chegou à mesma resposta (concordância independente, não garantia); `divergente` = outra resposta (fora de uso); `aviso` = baixa confiança, questão ambígua ou defeituosa (fora do simulado).
- Escritor e verificador usam modelos diferentes por padrão, para errarem de forma menos parecida.
