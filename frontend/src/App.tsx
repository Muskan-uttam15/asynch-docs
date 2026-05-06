import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent } from 'react'
import axios from 'axios'

type JobStatus = 'queued' | 'processing' | 'completed' | 'failed'

type DocumentRecord = {
  id: number
  filename: string
  content_type: string
  size_bytes: number
  status: JobStatus
  progress: number
  stage: string
  error_message: string | null
  extracted_data: Record<string, unknown> | null
  finalized_data: Record<string, unknown> | null
  is_finalized: boolean
  attempts: number
  created_at: string
  updated_at: string
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function App() {
  const [files, setFiles] = useState<FileList | null>(null)
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState('created_at')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [reviewJson, setReviewJson] = useState('{}')
  const [message, setMessage] = useState('')

  const selectedDocument = useMemo(
    () => documents.find((d) => d.id === selectedId) ?? null,
    [documents, selectedId]
  )

  const fetchDocuments = async () => {
    const params: Record<string, string> = { sort_by: sortBy, order }
    if (search) params.search = search
    if (statusFilter !== 'all') params.status = statusFilter
    const res = await axios.get<DocumentRecord[]>(`${API_URL}/documents`, { params })
    setDocuments(res.data)
    if (!selectedId && res.data.length > 0) {
      setSelectedId(res.data[0].id)
    }
  }

  useEffect(() => {
    fetchDocuments().catch(() => setMessage('Failed to load documents'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortBy, order, statusFilter])

  useEffect(() => {
    if (!selectedDocument) return
    setReviewJson(JSON.stringify(selectedDocument.finalized_data ?? {}, null, 2))
  }, [selectedDocument])

  useEffect(() => {
    if (!selectedId) return
    const stream = new EventSource(`${API_URL}/documents/${selectedId}/progress`)
    stream.onmessage = (event) => {
      const progressEvent = JSON.parse(event.data) as {
        document_id: number
        progress: number
        status: JobStatus
        event: string
        message?: string
      }
      setDocuments((prev) =>
        prev.map((doc) =>
          doc.id === progressEvent.document_id
            ? {
                ...doc,
                progress: progressEvent.progress,
                status: progressEvent.status,
                stage: progressEvent.event,
                error_message: progressEvent.message ?? doc.error_message,
              }
            : doc
        )
      )
    }
    return () => stream.close()
  }, [selectedId])

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => setFiles(e.target.files)

  const uploadDocuments = async () => {
    if (!files || files.length === 0) return
    const formData = new FormData()
    Array.from(files).forEach((file) => formData.append('files', file))
    await axios.post(`${API_URL}/documents/upload`, formData)
    setMessage('Upload successful and jobs queued')
    await fetchDocuments()
  }

  const saveReview = async () => {
    if (!selectedDocument) return
    const parsed = JSON.parse(reviewJson) as Record<string, unknown>
    await axios.put(`${API_URL}/documents/${selectedDocument.id}/review`, { data: parsed })
    setMessage('Review data saved')
    await fetchDocuments()
  }

  const finalize = async () => {
    if (!selectedDocument) return
    await axios.post(`${API_URL}/documents/${selectedDocument.id}/finalize`)
    setMessage('Record finalized')
    await fetchDocuments()
  }

  const retry = async () => {
    if (!selectedDocument) return
    await axios.post(`${API_URL}/documents/${selectedDocument.id}/retry`)
    setMessage('Retry queued')
    await fetchDocuments()
  }

  const exportFile = (format: 'csv' | 'json') => {
    window.open(`${API_URL}/documents/export/${format}`, '_blank')
  }

  return (
    <div className="container">
      <h1>Async Document Processor</h1>
      <div className="panel">
        <input type="file" multiple onChange={onFileChange} />
        <button onClick={uploadDocuments}>Upload</button>
        <button onClick={() => exportFile('json')}>Export JSON</button>
        <button onClick={() => exportFile('csv')}>Export CSV</button>
      </div>

      <div className="panel filters">
        <input
          placeholder="Search by filename"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button onClick={() => fetchDocuments()}>Search</button>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          <option value="queued">Queued</option>
          <option value="processing">Processing</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="created_at">Created</option>
          <option value="updated_at">Updated</option>
          <option value="filename">Filename</option>
          <option value="status">Status</option>
        </select>
        <select value={order} onChange={(e) => setOrder(e.target.value as 'asc' | 'desc')}>
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
      </div>

      <div className="layout">
        <div className="jobs">
          {documents.map((doc) => (
            <button key={doc.id} className="job" onClick={() => setSelectedId(doc.id)}>
              <div>
                <strong>{doc.filename}</strong>
              </div>
              <div>Status: {doc.status}</div>
              <div>Progress: {doc.progress}%</div>
              <div>Stage: {doc.stage}</div>
            </button>
          ))}
        </div>

        <div className="detail">
          {selectedDocument ? (
            <>
              <h2>Document #{selectedDocument.id}</h2>
              <p>Status: {selectedDocument.status}</p>
              <p>Attempts: {selectedDocument.attempts}</p>
              {selectedDocument.error_message && <p>Error: {selectedDocument.error_message}</p>}
              <textarea value={reviewJson} onChange={(e) => setReviewJson(e.target.value)} rows={18} />
              <div className="panel">
                <button onClick={saveReview}>Save Review</button>
                <button onClick={finalize} disabled={selectedDocument.status !== 'completed'}>
                  Finalize
                </button>
                <button onClick={retry} disabled={selectedDocument.status !== 'failed'}>
                  Retry Failed
                </button>
              </div>
            </>
          ) : (
            <p>Select a document to inspect</p>
          )}
        </div>
      </div>

      {message ? <p>{message}</p> : null}
    </div>
  )
}

export default App
