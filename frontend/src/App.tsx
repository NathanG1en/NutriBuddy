import { useState, useRef } from 'react'
import './App.css'
import { LabelBuilder } from './components/LabelBuilder'
import { AuthProvider, useAuth } from './context/AuthContext'
import { Login } from './components/Login'
import { useVoice } from './hooks/useVoice'
import { RecipeLab } from './components/RecipeLab'
import { VisionStudio } from './components/VisionStudio'
import ReactMarkdown from 'react-markdown'
import { FEATURES } from './config/features'

interface Message {
  type: string
  content: string
  imagePath?: string
}

function AppContent() {
  const { currentUser, loading: authLoading, logout } = useAuth()
  const { speak } = useVoice()
  const [activeTab, setActiveTab] = useState<'chat' | 'label' | 'recipe' | 'vision'>('chat')
  const [messages, setMessages] = useState<Message[]>([
    {
      type: 'ai',
      content: 'Hi! I can help you search for foods in the USDA database, analyze photos of your meals, or create nutrition labels. Try asking me about any recipe or click the 📸 Snap & Scan tab to upload a photo!'
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [threadId] = useState(`user-${Math.random().toString(36).substr(2, 9)}`)
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(FEATURES.ENABLE_VOICE)
  const chatFileInputRef = useRef<HTMLInputElement>(null)

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
      const response = await fetch('/api/chat', {
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

      // Speak the response if voice feature is enabled
      if (FEATURES.ENABLE_VOICE && isVoiceEnabled && data.response) {
        if (data.image_path) {
          speak("Here is the generated nutrition label.")
        } else {
          speak(data.response)
        }
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

  const handleChatImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0]) return
    const file = e.target.files[0]

    const userMsg: Message = {
      type: 'user',
      content: `📸 Uploaded image: ${file.name}`
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const token = await currentUser.getIdToken()
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch('/api/vision/meal', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (!res.ok) {
        throw new Error('Meal vision analysis failed')
      }

      const data = await res.json()
      const formattedItems = (data.detected_items || [])
        .map((it: any) => `- **${it.name}**: ${it.quantity} ${it.unit}`)
        .join('\n')

      const macros = data.recipe_totals || {}
      const summaryText = `### 🍽️ Detected Meal: ${data.meal_name}\n\n${data.description}\n\n**Visual Ingredients Breakdown:**\n${formattedItems}\n\n**USDA Verified Nutrition Totals:**\n- **Calories**: ${Math.round(macros.calories || 0)} kcal\n- **Protein**: ${(macros.protein || 0).toFixed(1)}g\n- **Carbs**: ${(macros.carbs || 0).toFixed(1)}g\n- **Fat**: ${(macros.fat || 0).toFixed(1)}g\n- **Sodium**: ${Math.round(macros.sodium || 0)}mg`

      setMessages(prev => [...prev, {
        type: 'ai',
        content: summaryText
      }])
    } catch (err: any) {
      setMessages(prev => [...prev, {
        type: 'ai',
        content: `❌ Error analyzing image: ${err.message}`
      }])
    } finally {
      setLoading(false)
      if (chatFileInputRef.current) {
        chatFileInputRef.current.value = ''
      }
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
            {FEATURES.ENABLE_VOICE && (
              <button
                className={`voice-toggle-btn ${isVoiceEnabled ? 'active' : 'muted'}`}
                onClick={() => setIsVoiceEnabled(!isVoiceEnabled)}
                title={isVoiceEnabled ? "Mute Voice" : "Enable Voice"}
              >
                {isVoiceEnabled ? '🔊' : '🔇'}
              </button>
            )}
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
            className={`tab ${activeTab === 'vision' ? 'active' : ''}`}
            onClick={() => setActiveTab('vision')}
          >
            📸 Snap & Scan
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
                  <div className="message-content">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
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
                type="file"
                ref={chatFileInputRef}
                style={{ display: 'none' }}
                accept="image/*"
                onChange={handleChatImageUpload}
              />
              <button
                type="button"
                className="upload-icon-btn"
                onClick={() => chatFileInputRef.current?.click()}
                title="Upload meal or food photo"
                style={{
                  background: '#d4d1b8',
                  border: '2px solid #3d3d2e',
                  borderRadius: '12px',
                  padding: '10px 14px',
                  fontSize: '18px',
                  cursor: 'pointer'
                }}
              >
                📷
              </button>
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
        ) : activeTab === 'vision' ? (
          <VisionStudio
            onExportToLabel={handleAnalyzeRecipe}
            onExportToRecipe={() => setActiveTab('recipe')}
          />
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