import 'dotenv/config'
import { app, BrowserWindow } from 'electron'
import { Sandbox } from '@e2b/desktop'

// Additional px to take into the account the window border at the top
const windowFrameHeight = 29

app.on('window-all-closed', () => {
  app.quit()
})

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * @param {string} streamUrl - The URL of the stream to load
 * @param {number} width - The width of the window
 * @param {number} height - The height of the window
 */
async function createWindow(streamUrl, width, height) {
  const win = new BrowserWindow({
    title: 'E2B Desktop',
    width,
    height: height + windowFrameHeight,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: true,
    },
  })

  console.log('> Loading stream URL...')
  await win.loadURL(streamUrl)
  console.log(' - Stream URL loaded')
}

/**
 * @param {import('@e2b/desktop').Sandbox} desktop - E2B desktop sandbox
 * @param {number} width - The width of the window
 * @param {number} height - The height of the window
 */
async function moveAround(desktop, width, height) {
  console.log('\n> Randomly moving mouse and right clicking 5 times...')
  for (let i = 0; i < 5; i++) {
    const x = Math.floor(Math.random() * width)
    const y = Math.floor(Math.random() * height)
    await desktop.moveMouse(x, y)
    console.log(` - Moved mouse to ${x}, ${y}`)
    await desktop.rightClick()
    console.log(` - Right clicked ${i}`)
    console.log(' - Waiting 2 seconds...\n')
    await wait(2000)
  }
}

async function main() {
  console.log('> Waiting for electron app to be ready...')
  await app.whenReady()
  console.log(' - Electron app is ready')

  console.log('\n> Starting desktop sandbox...')
  const desktop = await Sandbox.create()
  console.log(' - Desktop sandbox started, ID:', desktop.sandboxId)

  const size = await desktop.getScreenSize()
  console.log(' - Desktop sandbox screen size:', size)

  console.log('\n> Starting desktop stream...')
  await desktop.stream.start({
    requireAuth: true
  })

  console.log('\n> Waiting 5 seconds for the stream to load...')
  for (let i = 5; i > 0; i--) {
    console.log(` - ${i} seconds remaining until the next step...`)
    await wait(1000)
  }

  const authKey = await desktop.stream.getAuthKey()
  const url = desktop.stream.getUrl({ authKey })
  console.log(' - Stream URL:', url)

  console.log('\n> Creating browser window...')
  createWindow(url, size.width, size.height)
  console.log(' - Browser window created')

  await moveAround(desktop, size.width, size.height)

  console.log('\nPress enter to kill the sandbox and close the window...')
  process.stdin.once('data', async () => {
    console.log('\n> Stopping desktop stream...')
    await desktop.stream.stop()
    console.log(' - Desktop stream stopped')

    console.log('\n> Closing browser window...')
    console.log(' - Browser window closed')

    console.log('\n> Killing desktop sandbox...')
    await desktop.kill()
    console.log(' - Desktop sandbox killed')

    app.quit()
  })
}

main().then().catch(console.error)
