import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import Chat from './pages/Chat'
import Documents from './pages/Documents'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-950 text-gray-100">
        <Navbar />
        <Routes>
          <Route path="/" element={<Chat />} />
          <Route path="/documents" element={<Documents />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
