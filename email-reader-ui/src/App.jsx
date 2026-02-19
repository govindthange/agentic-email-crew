import { useState } from 'react'
import './App.css'

function App({ backendOrigin }) {
  console.log('EmailReaderUI: App component rendering with origin:', backendOrigin);
  const [lastEmail, setLastEmail] = useState(null)
  const [archiveCount, setArchiveCount] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [wipResponse, setWipResponse] = useState(null)

  const fetchLastEmail = async () => {
    setLoading(true)
    setError(null)
    setWipResponse(null)
    try {
      const response = await fetch(`${backendOrigin}/api/email/fetch/last`)
      const data = await response.json()
      setLastEmail(data)
    } catch (err) {
      setError(`Failed to fetch last email: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const fetchArchiveCount = async () => {
    setLoading(true)
    setError(null)
    setWipResponse(null)
    try {
      const response = await fetch(`${backendOrigin}/api/email/archive-count`)
      const data = await response.json()
      setArchiveCount(data.count)
    } catch (err) {
      setError(`Failed to fetch archive count: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const callWipEndpoint = async (endpoint) => {
    setLoading(true)
    setError(null)
    setWipResponse(null)
    try {
      const response = await fetch(`${backendOrigin}${endpoint}`)
      const data = await response.json()
      setWipResponse({ endpoint, data })
    } catch (err) {
      setError(`Failed to call ${endpoint}: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="email-reader-ui">
      <h1>Inbox Queries</h1>

      <div className="actions">
        <button onClick={fetchLastEmail} disabled={loading}>Fetch Last Email</button>
        <button onClick={fetchArchiveCount} disabled={loading}>Get Today's Email Archive Count</button>
        <button onClick={() => callWipEndpoint('/api/email/fetch/all')} disabled={loading}>Fetch All Emails</button>
        <button onClick={() => callWipEndpoint('/api/email/read-count')} disabled={loading}>Read Count</button>
        <button onClick={() => callWipEndpoint('/api/email/unread-count')} disabled={loading}>Unread Count</button>
      </div>

      {loading && <p className="status loading">Processing...</p>}
      {error && <p className="status error">{error}</p>}

      {lastEmail && (
        <div className="result">
          <h3>Last Email Result:</h3>
          <p>Status: {lastEmail.status}</p>
          <p>Archived: {lastEmail.archived ? 'Yes' : 'No'}</p>
          <pre>{JSON.stringify(lastEmail.email, null, 2)}</pre>
        </div>
      )}

      {archiveCount !== null && (
        <div className="result">
          <h3>Archive Count:</h3>
          <p>Total Emails: {archiveCount}</p>
        </div>
      )}

      {wipResponse && (
        <div className="result">
          <h3>WIP Endpoint: {wipResponse.endpoint}</h3>
          <pre>{JSON.stringify(wipResponse.data, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

export default App
