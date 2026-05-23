import { Link, useLocation } from 'react-router-dom'
import keycloak from '../keycloak'

export default function Navbar() {
  const location = useLocation()
  const username =
    keycloak.tokenParsed?.preferred_username ||
    keycloak.tokenParsed?.email ||
    'User'

  const linkClass = (path: string) =>
    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      location.pathname === path
        ? 'bg-red-600 text-white'
        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
    }`

  return (
    <nav className="bg-gray-900 border-b border-gray-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2">
            <span className="text-red-500 font-bold text-xl">🏎 F1 Agent</span>
            <div className="ml-8 flex gap-2">
              <Link to="/" className={linkClass('/')}>
                Chat
              </Link>
              <Link to="/documents" className={linkClass('/documents')}>
                Documents
              </Link>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-gray-400 text-sm">{username}</span>
            <button
              onClick={() => keycloak.logout()}
              className="bg-gray-700 hover:bg-gray-600 text-white text-sm px-3 py-1.5 rounded-md transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}
