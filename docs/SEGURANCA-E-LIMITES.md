# Segurança, privacidade e limites

Leia antes de confiar no tutor para algo que importa.

## O que o tutor é e o que não é

- É um apoio de estudo: organiza o material, pratica com você, registra seus erros e agenda revisões.
- **Não substitui aulas, professores nem o material oficial.** O conteúdo das questões geradas e as explicações vêm de um modelo de linguagem, que erra. As questões passam por verificação independente, mas "verificada" quer dizer que dois caminhos chegaram à mesma resposta, não que a questão está certa.
- O preparo estimado é uma faixa calculada a partir das suas tentativas no banco. **Não é previsão de nota**: a prova real pode cobrar outra coisa, de outro jeito.
- Quando algo não está nas suas fontes, o tutor deve dizer ("conhecimento geral, não está nas suas fontes"). Desconfie de respostas sem citação.

## A proteção do gabarito é em camadas, não um cofre

O objetivo é impedir que a resposta apareça **por acidente** antes da sua tentativa, porque isso atrapalha o aprendizado. As camadas:

1. Banco e gabarito em arquivos separados; o tutor só vê a resposta depois que você dá a sua e a confiança (`corrigir`).
2. Gabarito, respostas do verificador e texto das provas ficam codificados (zlib + base64). Isso não é criptografia: serve para não serem lidos por acidente.
3. Regras de permissão negam ao Claude a leitura desses arquivos.
4. Uma guarda (hook) bloqueia buscas recursivas nas suas matérias, leitura de rascunhos, o comando de exportação pelo agente e truques de shell conhecidos (comandos escondidos atrás de `#` ou de quebras de linha, variáveis como `BASH_ENV`). O verificador de questões só consegue rodar três comandos exatos.
5. O protocolo do tutor manda recusar pedidos de "só a letra" e nunca mostrar imagens de páginas de prova. A única imagem de prova que você vê é o recorte da figura, por link: o motor recusa o recorte quando há vermelho, rosa, laranja ou magenta na área, e o agente que recorta confere a imagem.

O que essas camadas **não** impedem:

- Você mesmo abrir os arquivos, rodar `banco exportar` no seu terminal ou abrir o PDF da prova.
- Um script qualquer ler os arquivos (a codificação é reversível de propósito).
- Variações de comando que a guarda não conhece. A guarda é uma rede a mais, não uma lista completa.
- O tutor resolver a questão sozinho e deixar escapar a resposta numa explicação. Isso é tratado por instrução e medido pelos evals, mas pode acontecer.
- Uma marca de resposta de outra cor (azul, preta, amarela), um círculo preto ou uma prova escaneada passam pela trava de cor do recorte. Nesses casos, a proteção é o agente conferir a imagem.
- O gabarito da matéria de exemplo é público (está no repositório), como qualquer arquivo versionado.
- Limites conhecidos da implementação: PDFs enormes são lidos inteiros pelo `pdftotext` (memória); argumentos com aspas dentro de aspas podem ser repartidos ao passar do Git Bash do Windows para o WSL; com `TUTOR_MATERIAS_DIR` apontando para fora do repositório (uso de desenvolvimento), as regras de busca da guarda não reconhecem a pasta.

Hooks e regras `allow` do projeto só passam a valer depois que você aceita a confiança na pasta, na primeira vez que abre o Claude Code nela. Se recusar, o tutor funciona, mas pede permissão a cada comando, e a guarda não roda.

Endurecimento opcional, **não testado neste projeto**: em macOS, Linux e WSL2, o sandbox do Claude Code pode negar a leitura de caminhos a comandos de shell ([documentação](https://code.claude.com/docs/en/sandboxing)). Ele também bloquearia o próprio motor se configurado sem exceções; teste antes de adotar.

## Fontes são dados, não instruções

Tudo o que você coloca em `fontes/` é tratado como material de estudo **não confiável**: um PDF baixado da internet pode conter texto escondido tentando dar ordens à IA ("ignore as regras", "mostre o gabarito"). Esse risco é conhecido como injeção indireta de instruções (veja Greshake et al., 2023, e OWASP LLM01:2025 em [REFERENCIAS.md](REFERENCIAS.md#desenho-de-agentes-e-segurança)). O tutor:

- nunca segue instruções encontradas nas fontes e avisa quando as encontra;
- marca, na ingestão, páginas com frases desse tipo (detecção heurística: pode deixar passar);
- recusa arquivos de configuração do Claude (`CLAUDE.md`, `AGENTS.md`, `.claude/`) dentro de `fontes/` e não os carrega (`claudeMdExcludes`);
- ignora links simbólicos que apontam para fora da matéria.

## Privacidade

- `subjects/` fica fora do git deste repositório. Seus PDFs, respostas e histórico não vão para o GitHub se você publicar um fork.
- O tutor não tem telemetria e não envia nada para serviços externos. O que sai da sua máquina é o que o Claude Code envia ao modelo durante as conversas, como em qualquer uso do Claude Code (veja os termos e a política de dados do seu plano).
- Para guardar o histórico de uma matéria, versione-a num repositório **privado** próprio, dentro da pasta da matéria.

## Direitos autorais do material

O material que você coloca em `fontes/` continua pertencendo aos autores. Use só o que você tem direito de usar para estudo pessoal, não publique esse material e não o coloque no repositório do tutor. A matéria de exemplo é original e fictícia, sob a licença MIT do projeto.

## Uso ético

O tutor é para aprender. Não o use para responder avaliações valendo nota em andamento (provas, trabalhos, listas entregues para correção): ele foi instruído a recusar e a oferecer estudo do conteúdo depois. Respeite as regras da sua instituição sobre uso de IA.

## Riscos conhecidos

| Risco | Mitigação | Resíduo |
|---|---|---|
| Resposta revelada antes da tentativa | `corrigir` exige o compromisso; protocolo; evals | O modelo pode errar no protocolo |
| Questão gerada errada | Verificação às cegas por outro modelo; divergentes saem de uso | Dois modelos podem errar igual |
| Injeção de instruções pelas fontes | Fontes como dados; alertas; `claudeMdExcludes`; inventário recusa configurações | Detecção heurística |
| Imagem de página de prova com a resposta marcada | Só o recorte da figura, com trava de cor e conferência do ingestor; guarda; renderização e recorte só para o ingestor | Marca de outra cor passa; o aluno pode abrir o PDF |
| Falsa precisão do painel | Faixas de incerteza; cobertura mínima para o preparo | Parâmetros heurísticos |
| Dados perdidos | Escrita atômica; registros só de acréscimo | Sem backup automático: versione num repositório privado |
