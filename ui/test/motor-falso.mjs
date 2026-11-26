// Motor falso para testes: fala o mesmo protocolo (uma linha JSON por mensagem).
// Responde "<tipo>_resposta" com o mesmo id; "cair" encerra com código 1;
// "lixo" imprime uma linha que não é JSON; "gravar" anuncia o estado "gravando".
import { createInterface } from 'node:readline'

const escrever = (obj) => process.stdout.write(JSON.stringify(obj) + '\n')

escrever({ tipo: 'pronto', dispositivo: 'cpu', modelo: 'falso', pid: process.pid })

let lento = false
const leitor = createInterface({ input: process.stdin })
leitor.on('line', (linha) => {
  let msg
  try {
    msg = JSON.parse(linha)
  } catch {
    return
  }
  if (msg.tipo === 'cair') process.exit(1)
  if (msg.tipo === 'erro_e_cair') {
    escrever({ tipo: 'estado', estado: 'erro', msg: 'Erro ao carregar o modelo: sem CUDA' })
    process.exit(1)
  }
  if (msg.tipo === 'stderr_e_cair') {
    process.stderr.write('Traceback (most recent call last):\nRuntimeError: DLL quebrada\n', () =>
      process.exit(1)
    )
    return
  }
  if (msg.tipo === 'transcrever') {
    // Simula a transcrição final em andamento: o "sair" só termina depois de 3 s.
    lento = true
    escrever({ tipo: 'estado', estado: 'transcrevendo' })
    return
  }
  if (msg.tipo === 'sair') {
    if (!lento) process.exit(0)
    setTimeout(() => {
      escrever({ tipo: 'log', nivel: 'info', msg: 'saiu limpo' })
      process.exit(0)
    }, 3000)
    return
  }
  if (msg.tipo === 'lixo') {
    process.stdout.write('isto { nao e json\n')
    escrever({ tipo: 'log', nivel: 'info', msg: 'depois do lixo' })
    return
  }
  if (msg.tipo === 'gravar') {
    escrever({ tipo: 'estado', estado: 'gravando' })
    return
  }
  if (msg.tipo === 'mudo') return // nunca responde (teste de tempo limite)
  if (msg.id !== undefined) {
    escrever({ tipo: `${msg.tipo}_resposta`, id: msg.id, ok: true })
  }
})
