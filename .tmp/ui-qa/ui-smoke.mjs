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
const browserErrors = []
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data)
  if (message.id) {
    const operation = pending.get(message.id)
    if (!operation) return
    pending.delete(message.id)
    if (message.error) operation.reject(new Error(message.error.message))
    else operation.resolve(message.result)
    return
  }
  if (message.method === 'Runtime.exceptionThrown') {
    browserErrors.push(message.params.exceptionDetails.text)
  }
})

function call(method, params = {}) {
  const id = ++nextId
  socket.send(JSON.stringify({ id, method, params }))
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }))
}

async function evaluate(expression) {
  const response = await call('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  })
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text)
  return response.result.value
}

async function waitFor(expression, label, timeout = 180_000) {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (await evaluate(expression)) return
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(`Timed out waiting for ${label}.`)
}

try {
  await call('Runtime.enable')
  await call('Page.enable')
  await call('Page.reload', { ignoreCache: true })
  await waitFor(
    `document.body.innerText.includes('Turn any PDF into a conversation.')`,
    'the empty workspace',
  )

  const documentNode = await call('DOM.getDocument', { depth: -1, pierce: true })
  const fileInput = await call('DOM.querySelector', {
    nodeId: documentNode.root.nodeId,
    selector: 'input[type="file"]',
  })
  if (!fileInput.nodeId) throw new Error('Upload input was not found.')
  await call('DOM.setFileInputFiles', {
    nodeId: fileInput.nodeId,
    files: ['C:\\lg_G\\PdfSense\\.tmp\\ui-qa\\pdfsense-ui-qa.pdf'],
  })
  await waitFor(
    `document.body.innerText.includes('pdfsense-ui-qa.pdf') && Boolean(document.querySelector('textarea'))`,
    'uploaded document workspace',
  )

  await evaluate(`(() => {
    const input = document.querySelector('textarea');
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    setter.call(input, 'When does Project Aurora launch?');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    return input.value;
  })()`)
  await waitFor(
    `!document.querySelector('button[aria-label="Send question"]').disabled`,
    'enabled chat submit button',
  )
  await evaluate(`document.querySelector('button[aria-label="Send question"]').click()`)
  await waitFor(`document.body.innerText.includes('Source 1 · Page 1')`, 'cited chat answer')

  const chatVerified = await evaluate(
    `document.body.innerText.includes('2028') && document.body.innerText.includes('Source 1 · Page 1')`,
  )

  await evaluate(
    `[...document.querySelectorAll('button')].find((button) => button.textContent.trim() === 'Summarize').click()`,
  )
  await waitFor(
    `[...document.querySelectorAll('button')].some((button) => button.textContent.includes('Generate summary'))`,
    'summary controls',
  )
  await evaluate(
    `[...document.querySelectorAll('button')].find((button) => button.textContent.includes('Generate summary')).click()`,
  )
  await waitFor(
    `document.body.innerText.includes('Regenerate summary') && document.body.innerText.includes('Aurora')`,
    'generated summary',
  )
  const summaryVerified = await evaluate(
    `document.body.innerText.includes('Aurora') && document.body.innerText.includes('2028')`,
  )

  await evaluate(
    `[...document.querySelectorAll('button')].find((button) => button.textContent.trim() === 'Study').click()`,
  )
  await waitFor(`document.querySelectorAll('input[type="number"]').length === 2`, 'study controls')
  await evaluate(`(() => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    for (const input of document.querySelectorAll('input[type="number"]')) {
      setter.call(input, '1');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
  })()`)
  await waitFor(
    `[...document.querySelectorAll('button')].some((button) => button.textContent.trim() === 'Generate' && !button.disabled)`,
    'enabled study button',
  )
  await evaluate(
    `[...document.querySelectorAll('button')].find((button) => button.textContent.trim() === 'Generate' && !button.disabled).click()`,
  )
  await waitFor(
    `document.body.innerText.includes('MCQs (1)') && document.body.innerText.includes('Flashcards (1)')`,
    'generated study materials',
  )
  const studyVerified = await evaluate(
    `document.body.innerText.includes('MCQs (1)') && document.body.innerText.includes('Flashcards (1)')`,
  )

  console.log(
    JSON.stringify(
      {
        uploadVerified: true,
        chatVerified,
        summaryVerified,
        studyVerified,
        browserErrors,
      },
      null,
      2,
    ),
  )
} finally {
  socket.close()
}
