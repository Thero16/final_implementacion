import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import keycloak from './keycloak'

const root = createRoot(document.getElementById('root')!)

root.render(
  <div className="min-h-screen bg-gray-950 flex items-center justify-center">
    <p className="text-gray-400 text-sm">Connecting to authentication server…</p>
  </div>
)

keycloak
  .init({ onLoad: 'login-required', pkceMethod: 'S256' })
  .then((authenticated) => {
    if (authenticated) {
      root.render(<App />)
    }
  })
  .catch((err) => {
    console.error('Keycloak init failed:', err)
    root.render(
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 font-semibold mb-2">Could not connect to Keycloak</p>
          <p className="text-gray-500 text-sm">Make sure Docker is running: <code className="text-gray-300">docker compose up -d</code></p>
          <p className="text-gray-600 text-xs mt-1">{String(err)}</p>
        </div>
      </div>
    )
  })
