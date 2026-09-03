import { writeFile } from 'node:fs/promises'

const targets = await fetch('http://127.0.0.1:9222/json').then((response) => response.json())
const target = targets.find(
  (candidate) => candidate.type === 'page' && candidate.url.startsWith('http://localhost:5173'),
)
if (!target) throw new Error('PdfSense browser target was not found.')
const socket = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true })
  socket.addEventListener('error', reject, { once: true })
})
let nextId = 0
const pending = new Map()
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (!message.id) return
  const operation = pending.get(message.id)
  if (!operation) return
  pending.delete(message.id)
  if (message.error) operation.reject(new Error(message.error.message))
  else operation.resolve(message.result)
})
function call(method, params = {}) {
  const id = ++nextId
  socket.send(JSON.stringify({ id, method, params }))
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
}

try {
  await call('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  })
  await call('Page.reload', { ignoreCache: true })
  await new Promise((resolve) => setTimeout(resolve, 2_000))
  await call('Runtime.evaluate', {
    expression: `window.scrollTo(0, 0); document.scrollingElement.scrollTop = 0;`,
  })
  const desktop = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile('C:\\lg_G\\PdfSense\\.tmp\\ui-qa\\populated-desktop.png', Buffer.from(desktop.data, 'base64'))

  await call('Emulation.setDeviceMetricsOverride', {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  })
  await call('Page.reload', { ignoreCache: true })
  await new Promise((resolve) => setTimeout(resolve, 2_000))
  const metrics = await call('Runtime.evaluate', {
    expression: `window.scrollTo(0, 0); document.scrollingElement.scrollTop = 0; ({
      innerWidth,
      innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
      scrollX,
      scrollY,
    })`,
    returnByValue: true,
  })
  const mobile = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile('C:\\lg_G\\PdfSense\\.tmp\\ui-qa\\populated-mobile.png', Buffer.from(mobile.data, 'base64'))
  console.log('Captured desktop and mobile screenshots.', metrics.result.value)
} finally {
  socket.close()
}
