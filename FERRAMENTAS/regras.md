# MJS Agent — Regras de Configuração

Este arquivo define como o agente autônomo deve se comportar.
Edite os valores após os dois pontos (`- chave: valor`).
Para desativar uma regra, você pode deletá-la ou comentar colocando `#` na frente.

## REGRA: Criar Estrutura de Pastas Diária
- gatilho: horario_diario
- hora: 07:30
- acao: criar_pastas
- base: Z:\
- subpastas: BOLSINHAS, BOLSINHAS\PARA FAZER, PAINEL_CUT, CONF, APS, TEX

## REGRA: Processar Bolsinhas Automático
- gatilho: arquivo_novo
- acao: bolsinhas
- pasta: Z:\BOLSINHAS\PARA FAZER
- ext: .tif, .tiff

## REGRA: CONF Processador de TIFFs Automático
- gatilho: arquivo_novo
- acao: conf
- pasta: Z:\CONF
- ext: .tif, .tiff

## REGRA: Servidor do Notepad
- gatilho: sempre_ativo
- acao: notepad_servidor
- reiniciar_se_cair: sim

## ENCADEAMENTO: Fluxo de Conf e Bolsinhas
- primeiro: CONF Processador de TIFFs Automático
- depois: Processar Bolsinhas Automático
- notificar: "Lote de Conf processado e bolsinhas geradas com sucesso!"
