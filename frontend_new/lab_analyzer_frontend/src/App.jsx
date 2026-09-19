import { useState } from 'react'
import Navbar from './navbar'
import FileUpload from './fileUpload'
import { analyzeLabs, parseCsv, readFileText } from './api'
import './App.css'

function App() {
  const [view, setView] = useState('home')
  const [selectedFile, setSelectedFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [data, setData] = useState(null)

  async function callAnalyze() {
    if (!selectedFile) {
      setError('Please select a CSV first.')
      return
    }

    setLoading(true)
    setError('')
    setData(null)

    try {
      const rows = parseCsv(await readFileText(selectedFile))
      if (!rows.length) {
        throw new Error('That CSV has no data rows.')
      }
      setData(await analyzeLabs(rows))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Navbar active={view} onNavigate={setView} />

      <section id="home">
        <h1>Laboratory Result Analyzer</h1>
      </section>

      <section id="analyze">
        <h2>Analyze</h2>

        <FileUpload onFileSelect={(file) => setSelectedFile(file)} />

        <button onClick={callAnalyze} disabled={!selectedFile || loading}>
          {loading ? 'Analyzing…' : 'Analyze'}
        </button>

        {error && <p role="alert">{error}</p>}

        {data && (
          <div>
            <p>
              {data.summary.critical} critical · {data.summary.warning} warning ·{' '}
              {data.summary.normal} normal · {data.summary.unknown} unknown
            </p>
            {data.errors.length > 0 && (
              <p>
                {data.errors.length} row{data.errors.length === 1 ? '' : 's'} could not be read.
              </p>
            )}
          </div>
        )}
      </section>

      <section id="consultation">
        <h2>Consultation</h2>
      </section>

      <section id="about">
        <h2>About</h2>
      </section>
    </div>
  )
}

export default App
