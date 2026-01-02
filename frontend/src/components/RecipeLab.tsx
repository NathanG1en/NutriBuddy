import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
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

interface RecipeLabProps {
    onAnalyze?: (data: any) => void;
}

export const RecipeLab: React.FC<RecipeLabProps> = ({ onAnalyze }) => {
    const { currentUser } = useAuth();
    const [prompt, setPrompt] = useState('');
    const [recipe, setRecipe] = useState<Recipe | null>(null);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState('');
    const [savedRecipes, setSavedRecipes] = useState<any[]>([]);
    const [saving, setSaving] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const { isListening, transcript, startListening, isSupported } = useSpeechRecognition();

    useEffect(() => {
        if (transcript) {
            setPrompt(prev => prev + (prev ? ' ' : '') + transcript);
        }
    }, [transcript]);

    // Fetch saved recipes on load
    React.useEffect(() => {
        if (currentUser) {
            fetchSavedRecipes();
        }
    }, [currentUser]);

    const fetchSavedRecipes = async () => {
        try {
            const token = await currentUser?.getIdToken();
            const res = await fetch('/api/recipes', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            setSavedRecipes(data);
        } catch (e) {
            console.error("Error fetching recipes:", e);
        }
    };

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file || !currentUser) return;

        setUploading(true);
        setUploadStatus('Uploading...');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/rag/upload', {
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
            const response = await fetch('/api/rag/generate', {
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

    const saveRecipe = async () => {
        if (!recipe || !currentUser) return;
        setSaving(true);
        try {
            await fetch('/api/recipes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${await currentUser.getIdToken()}`
                },
                body: JSON.stringify(recipe)
            });
            fetchSavedRecipes(); // Refresh list
            alert("Recipe saved!");
        } catch (e) {
            console.error(e);
            alert("Failed to save.");
        } finally {
            setSaving(false);
        }
    };

    const analyzeRecipe = async () => {
        if (!recipe || !currentUser) return;
        setAnalyzing(true);
        try {
            const ingredients = recipe.ingredients.map(i => `${i.quantity} ${i.unit} ${i.item}`);
            const res = await fetch('/api/labels/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${await currentUser.getIdToken()}`
                },
                body: JSON.stringify({
                    recipe_name: recipe.title,
                    ingredients: ingredients
                })
            });
            if (!res.ok) throw new Error("Analysis failed");
            const data = await res.json();

            // Navigate to Label Builder with data
            if (onAnalyze && data.ingredients) {
                // Enhance data with recipe name
                onAnalyze({
                    name: recipe.title,
                    ingredients: data.ingredients
                });
            } else {
                alert("Could not extract ingredients for Label Builder.");
            }
        } catch (e) {
            console.error(e);
            alert("Failed to create label: " + e);
        } finally {
            setAnalyzing(false);
        }
    };

    const loadRecipe = (r: any) => {
        setRecipe(r);
    };

    const clearKnowledge = async () => {
        if (!currentUser) return;
        if (!confirm("Are you sure? This will delete all uploaded documents.")) return;

        try {
            await fetch('/api/rag/clear', {
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
            {/* Left Panel: Controls & Saved Items */}
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
                    <div className="input-wrapper">
                        <textarea
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            placeholder="e.g., Create a sourdough bread recipe using the uploaded hydration techniques..."
                            disabled={loading}
                        />
                        {isSupported && (
                            <button
                                className={`mic-btn ${isListening ? 'listening' : ''}`}
                                onClick={startListening}
                                title="Speak to add text"
                            >
                                {isListening ? '🔴' : '🎤'}
                            </button>
                        )}
                    </div>
                    <button
                        className="generate-btn"
                        onClick={generateRecipe}
                        disabled={loading || !prompt}
                    >
                        {loading ? '⚗️ Distilling...' : '✨ Generate Recipe'}
                    </button>
                </div>

                {/* Saved Recipes List */}
                <div className="saved-list-section card">
                    <h3>📚 Saved Recipes</h3>
                    <div className="saved-list">
                        {!Array.isArray(savedRecipes) || savedRecipes.length === 0 ? <p className="hint">No saved recipes yet.</p> :
                            savedRecipes.map((r, i) => (
                                <div key={r.id || i} className="saved-item" onClick={() => loadRecipe(r)}>
                                    <span className="saved-title">{r.title}</span>
                                    <span className="saved-date">{new Date(r.created_at).toLocaleDateString()}</span>
                                </div>
                            ))
                        }
                    </div>
                </div>
            </div>

            {/* Right Panel: Recipe Output */}
            <div className="lab-output">
                {!recipe && !loading && (
                    <div className="placeholder-state">
                        <div className="placeholder-icon">📋</div>
                        <p>Select a saved recipe or generate a new one.</p>
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
                            <div className="header-actions">
                                <h1>{recipe.title}</h1>
                                <div style={{ display: 'flex', gap: '10px' }}>
                                    <button onClick={analyzeRecipe} disabled={analyzing} className="analyze-btn">
                                        {analyzing ? '🔬 Analyzing...' : '🏷️ Create Label'}
                                    </button>
                                    <button onClick={saveRecipe} disabled={saving} className="save-btn">
                                        {saving ? 'Saving...' : '💾 Save'}
                                    </button>
                                </div>
                            </div>
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
