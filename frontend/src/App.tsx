import { useState } from 'react'
import './App.css'
import { LabelBuilder } from './components/LabelBuilder'
import { AuthProvider, useAuth } from './context/AuthContext'
import { Login } from './components/Login'
import { useVoice } from './hooks/useVoice'
import { RecipeLab } from './components/RecipeLab'

interface Message {
  type: string
  content: string
  imagePath?: string
}

function AppContent() {
  const { currentUser, loading: authLoading, logout } = useAuth()
  const { speak } = useVoice()
  const [activeTab, setActiveTab] = useState<'chat' | 'label' | 'recipe'>('chat')
  const [messages, setMessages] = useState<Message[]>([
    {
      type: 'ai',
      content: 'Hi! I can help you search for foods in the USDA database and create nutrition labels. Try asking me to "Find avocado and create a nutrition label"!'
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [threadId] = useState(`user-${Math.random().toString(36).substr(2, 9)}`)

  if (authLoading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>
  }

  if (!currentUser) {
    return <Login />
  }

  const sendMessage = async (message = input) => {
    if (!message.trim()) return

    const userMessage: Message = { type: 'user', content: message }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${await currentUser.getIdToken()}`
        },
        body: JSON.stringify({ message, thread_id: threadId })
      })

      const data = await response.json()

      setMessages(prev => [...prev, {
        type: 'ai',
        content: data.response,
        imagePath: data.image_path
      }])

      // Speak the response
      if (data.response) {
        speak(data.response)
      }

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

  // Shared state for Label Builder
  const [initialLabelData, setInitialLabelData] = useState<any>(null)

  const handleAnalyzeRecipe = (data: any) => {
    setInitialLabelData(data)
    setActiveTab('label')
  }

  return (
    <div className="app">
      <div className="main-container">
        {/* Navigation Bar */}
        <nav className="nav-bar">
          <div className="logo">
            <div className="logo-icon">🥑</div>
            <span>NutriBuddy</span>
          </div>
          <div className="nav-links">
            <div className="nav-user-info">
              <span className="user-greeting">Hi, {currentUser.displayName?.split(' ')[0]}</span>
              <button onClick={logout} className="logout-btn">Logout</button>
            </div>
          </div>
        </nav>

        {/* Tab Bar */}
        <div className="tab-bar">
          <button
            className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            💬 AI Chat
          </button>
          <button
            className={`tab ${activeTab === 'label' ? 'active' : ''}`}
            onClick={() => setActiveTab('label')}
          >
            🏷️ Label Builder
          </button>
          <button
            className={`tab ${activeTab === 'recipe' ? 'active' : ''}`}
            onClick={() => setActiveTab('recipe')}
          >
            🧪 Recipe Lab
          </button>
        </div>

        {activeTab === 'chat' ? (
          <>
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
          </>
        ) : activeTab === 'label' ? (
          <LabelBuilder initialData={initialLabelData} />
        ) : (
          <RecipeLab onAnalyze={handleAnalyzeRecipe} />
        )}
      </div>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App