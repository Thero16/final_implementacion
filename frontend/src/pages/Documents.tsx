import { useCallback, useEffect, useRef, useState } from 'react'
import api from '../api/client'

interface Doc {
  id: number
  original_name: string
  chunk_count: number
  status: string
  error_message: string | null
  uploaded_at: string
}

const ACCEPTED = '.pdf,.txt,.md,.csv,.docx'

export default function Documents() {
  const [docs, setDocs] = useState<Doc[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const fetchDocs = async () => {
    try {
      const res = await api.get('/documents/')
      setDocs(res.data)
    } catch {
      // silently fail
    }
  }

  useEffect(() => {
    fetchDocs()
  }, [])

  const uploadFile = async (file: File) => {
    setError(null)
    setSuccess(null)
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      await api.post('/documents/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setSuccess(`"${file.name}" uploaded and processed successfully.`)
      fetchDocs()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  const handleFiles = (files: FileList | null) => {
    if (files && files.length > 0) uploadFile(files[0])
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }, [])

  const deleteDoc = async (id: number, name: string) => {
    if (!confirm(`Delete "${name}"?`)) return
    try {
      await api.delete(`/documents/${id}`)
      setDocs((prev) => prev.filter((d) => d.id !== id))
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Delete failed.')
    }
  }

  const statusBadge = (status: string) => {
    if (status === 'ready')
      return 'bg-green-900/40 text-green-400 border border-green-700'
    if (status === 'processing')
      return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
    return 'bg-red-900/40 text-red-400 border border-red-700'
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-white mb-6">Knowledge Base</h1>

      {/* Upload area */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer border-2 border-dashed rounded-xl p-10 text-center transition-colors mb-6 ${
          dragOver
            ? 'border-red-500 bg-red-900/10'
            : 'border-gray-600 hover:border-gray-400 bg-gray-900'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        {uploading ? (
          <p className="text-gray-400 text-sm">Uploading and processing…</p>
        ) : (
          <>
            <p className="text-4xl mb-3">📄</p>
            <p className="text-gray-300 font-medium">
              Drop a file here or <span className="text-red-400 underline">browse</span>
            </p>
            <p className="text-gray-500 text-xs mt-2">
              Supported: PDF, TXT, MD, CSV, DOCX · Max 50 MB
            </p>
          </>
        )}
      </div>

      {error && (
        <div className="mb-4 bg-red-900/30 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 bg-green-900/30 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm">
          {success}
        </div>
      )}

      {/* Documents list */}
      <h2 className="text-lg font-semibold text-gray-300 mb-3">
        Uploaded Documents ({docs.length})
      </h2>

      {docs.length === 0 ? (
        <p className="text-gray-500 text-sm">No documents uploaded yet.</p>
      ) : (
        <div className="space-y-3">
          {docs.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between bg-gray-900 border border-gray-700 rounded-xl px-4 py-3"
            >
              <div className="flex-1 min-w-0 mr-4">
                <p className="text-gray-100 text-sm font-medium truncate">
                  {doc.original_name}
                </p>
                <div className="flex items-center gap-3 mt-1">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${statusBadge(doc.status)}`}
                  >
                    {doc.status}
                  </span>
                  {doc.status === 'ready' && (
                    <span className="text-gray-500 text-xs">
                      {doc.chunk_count} chunks
                    </span>
                  )}
                  <span className="text-gray-600 text-xs">
                    {new Date(doc.uploaded_at).toLocaleDateString()}
                  </span>
                </div>
                {doc.error_message && (
                  <p className="text-red-400 text-xs mt-1 truncate">{doc.error_message}</p>
                )}
              </div>
              <button
                onClick={() => deleteDoc(doc.id, doc.original_name)}
                className="text-gray-500 hover:text-red-400 transition-colors text-sm px-2 py-1"
                title="Delete document"
              >
                🗑
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
