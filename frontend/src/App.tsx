import { useState } from 'react'
import './App.css'

interface Message {
  type: string
  content: string
  imagePath?: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      type: 'ai',
      content: 'Hi! I can help you search for foods in the USDA database and create nutrition labels. Try asking me to "Find avocado and create a nutrition label"!'
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [threadId] = useState(`user-${Math.random().toString(36).substr(2, 9)}`)

  const sendMessage = async (message = input) => {
    if (!message.trim()) return

    const userMessage: Message = { type: 'user', content: message }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, thread_id: threadId })
      })

      const data = await response.json()

      setMessages(prev => [...prev, {
        type: 'ai',
        content: data.response,
        imagePath: data.image_path
      }])
    } catch (error) {
      setMessages(prev => [...prev, {
        type: 'ai',
        content: '❌ Error connecting to backend. Make sure it\'s running on port 8000.'
      }])
    } finally {
      setLoading(false)
    }
  }

  const examples = [
    '🥑 Find avocado and create a nutrition label image',
    '🐟 Compare protein content in salmon vs chicken breast',
    '🥛 Find organic whole milk and show nutrition facts'
  ]

  return (
    <div className="app">
      <div className="main-container">
        {/* Navigation Bar */}
        <nav className="nav-bar">
          <div className="logo">
            <div className="logo-icon">🥑</div>
            <span>NutriAgent</span>
          </div>
          <div className="nav-links">
            <a className="nav-link">About</a>
            <a className="nav-link">Features</a>
            <a className="nav-link">Docs</a>
            <button className="action-button">Get Started</button>
          </div>
        </nav>

        {/* Hero Section */}
        <div className="hero-section">
          <h1 className="hero-title">
            Get Nutrition Facts
            <br />
            with <span className="highlight">AI Power</span>
          </h1>
          <p className="hero-subtitle">Search foods, analyze nutrition, generate labels</p>
        </div>

        {/* Chat Container */}
        <div className="chat-container">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.type}-message`}>
              <div className="message-content">{msg.content}</div>
              {msg.imagePath && (
                  <div className="image-wrapper">
                    <img
                      src={msg.imagePath}
                      alt="Nutrition Label"
                      className="nutrition-image"
                      onError={(e) => {
                        console.error('Failed to load image:', msg.imagePath)
                        e.currentTarget.style.display = 'none'
                      }}
                    />
                    <a
                      href={msg.imagePath}
                      download
                      className="download-link"
                    >
                      📥 Download Label
                    </a>
                  </div>
                )}
            </div>
          ))}
          {loading && <div className="loading">🤔 Thinking...</div>}
        </div>

        {/* Examples */}
        <div className="examples">
          <h3>💡 Try these:</h3>
          {examples.map((ex, idx) => (
            <button key={idx} onClick={() => sendMessage(ex)} className="example-btn">
              {ex}
            </button>
          ))}
        </div>

        {/* Input Container */}
        <div className="input-container">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Ask about nutrition, search for foods, or request labels..."
          />
          <button onClick={() => sendMessage()} disabled={loading || !input.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

export default App