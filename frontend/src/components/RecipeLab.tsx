import React, { useState, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import './RecipeLab.css';

interface Ingredient {
    item: string;
    quantity: string;
    unit: string;
    notes: string;
}

interface Recipe {
    title: string;
    description: string;
    ingredients: Ingredient[];
    instructions: string[];
    science_notes: string;
}

export const RecipeLab: React.FC = () => {
    const { currentUser } = useAuth();
    const [prompt, setPrompt] = useState('');
    const [recipe, setRecipe] = useState<Recipe | null>(null);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState('');
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file || !currentUser) return;

        setUploading(true);
        setUploadStatus('Uploading...');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('http://localhost:8000/api/rag/upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${await currentUser.getIdToken()}`
                },
                body: formData
            });

            if (!response.ok) throw new Error('Upload failed');

            setUploadStatus(`✅ ${file.name} added to knowledge base!`);
            setTimeout(() => setUploadStatus(''), 3000);
        } catch (error) {
            console.error(error);
            setUploadStatus('❌ Upload failed');
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const generateRecipe = async () => {
        if (!prompt.trim() || !currentUser) return;

        setLoading(true);
        setRecipe(null);

        try {
            const response = await fetch('http://localhost:8000/api/rag/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${await currentUser.getIdToken()}`
                },
                body: JSON.stringify({ prompt })
            });

            if (!response.ok) throw new Error('Generation failed');

            const data = await response.json();
            setRecipe(data);
        } catch (error) {
            console.error(error);
            // Construct a fake error recipe for UI feedback
            setRecipe({
                title: "Error Generating Recipe",
                description: "Could not generate recipe. Please try again.",
                ingredients: [],
                instructions: [],
                science_notes: "Check backend logs."
            });
        } finally {
            setLoading(false);
        }
    };

    const clearKnowledge = async () => {
        if (!currentUser) return;
        if (!confirm("Are you sure? This will delete all uploaded documents.")) return;

        try {
            await fetch('http://localhost:8000/api/rag/clear', {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${await currentUser.getIdToken()}` }
            });
            setUploadStatus('🗑️ Knowledge cleared');
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="recipe-lab-container">
            {/* Left Panel: Controls */}
            <div className="lab-controls">
                <div className="section-header">
                    <h2>🧪 Recipe Lab</h2>
                    <p>Iterate on recipes with AI + Food Science</p>
                </div>

                <div className="upload-section card">
                    <h3>1. Add Knowledge</h3>
                    <p className="hint">Upload PDF or Text files containing scientific context.</p>

                    <div className="file-actions">
                        <input
                            type="file"
                            ref={fileInputRef}
                            onChange={handleFileUpload}
                            accept=".pdf,.txt"
                            className="file-input"
                            disabled={uploading}
                        />
                        <button className="clear-btn" onClick={clearKnowledge} title="Clear all knowledge">🗑️</button>
                    </div>
                    {uploadStatus && <div className="status-msg">{uploadStatus}</div>}
                </div>

                <div className="generate-section card">
                    <h3>2. Create Recipe</h3>
                    <textarea
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="e.g., Create a sourdough bread recipe using the uploaded hydration techniques..."
                        disabled={loading}
                    />
                    <button
                        className="generate-btn"
                        onClick={generateRecipe}
                        disabled={loading || !prompt}
                    >
                        {loading ? '⚗️ Distilling...' : '✨ Generate Recipe'}
                    </button>
                </div>
            </div>

            {/* Right Panel: Recipe Output */}
            <div className="lab-output">
                {!recipe && !loading && (
                    <div className="placeholder-state">
                        <div className="placeholder-icon">📋</div>
                        <p>Your generated recipe will appear here.</p>
                    </div>
                )}

                {loading && (
                    <div className="loading-state">
                        <div className="spinner">🍳</div>
                        <p>Analyzing food science data...</p>
                    </div>
                )}

                {recipe && (
                    <div className="recipe-card-full">
                        <div className="recipe-header">
                            <h1>{recipe.title}</h1>
                            <p className="recipe-desc">{recipe.description}</p>
                        </div>

                        <div className="recipe-science-note">
                            <h4>🔬 Food Science Notes</h4>
                            <p>{recipe.science_notes}</p>
                        </div>

                        <div className="recipe-body">
                            <div className="ingredients-list">
                                <h3>Ingredients</h3>
                                <ul>
                                    {recipe.ingredients.map((ing, i) => (
                                        <li key={i}>
                                            <span className="qty">{ing.quantity} {ing.unit}</span>
                                            <span className="item">{ing.item}</span>
                                            {ing.notes && <span className="note">({ing.notes})</span>}
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            <div className="instructions-list">
                                <h3>Instructions</h3>
                                <ol>
                                    {recipe.instructions.map((step, i) => (
                                        <li key={i}>{step}</li>
                                    ))}
                                </ol>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
