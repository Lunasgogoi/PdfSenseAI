const targets = await fetch('http://127.0.0.1:9222/json').then((response) => response.json())
const target = targets.find((candidate) => candidate.webSocketDebuggerUrl)
if (target) {
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  socket.send(JSON.stringify({ id: 1, method: 'Browser.close', params: {} }))
  await new Promise((resolve) => setTimeout(resolve, 500))
  socket.close()
}
