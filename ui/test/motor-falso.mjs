// Motor falso para testes: fala o mesmo protocolo (uma linha JSON por mensagem).
// Responde "<tipo>_resposta" com o mesmo id; "cair" encerra com código 1;
// "lixo" imprime uma linha que não é JSON.
import { createInterface } from 'node:readline'

const escrever = (obj) => process.stdout.write(JSON.stringify(obj) + '\n')

escrever({ tipo: 'pronto', dispositivo: 'cpu', modelo: 'falso', pid: process.pid })

const leitor = createInterface({ input: process.stdin })
leitor.on('line', (linha) => {
  let msg
  try {
    msg = JSON.parse(linha)
  } catch {
    return
  }
  if (msg.tipo === 'cair') process.exit(1)
  if (msg.tipo === 'sair') process.exit(0)
  if (msg.tipo === 'lixo') {
    process.stdout.write('isto { nao e json\n')
    escrever({ tipo: 'log', nivel: 'info', msg: 'depois do lixo' })
    return
  }
  if (msg.tipo === 'mudo') return // nunca responde (teste de tempo limite)
  if (msg.id !== undefined) {
    escrever({ tipo: `${msg.tipo}_resposta`, id: msg.id, ok: true })
  }
})
