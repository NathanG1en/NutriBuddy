// frontend/src/components/VisionStudio.tsx
import React, { useState, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import './VisionStudio.css';

interface DetectedItem {
  name: string;
  quantity: number;
  unit: string;
  confidence?: number;
}

interface IngredientNutrient {
  name: string;
  grams: number;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

interface MealAnalysisResult {
  meal_name: string;
  description: string;
  dietary_flags: string[];
  estimated_prep_notes?: string;
  detected_items: DetectedItem[];
  recipe_totals: {
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
    sodium: number;
    fiber?: number;
    sugars?: number;
  };
  ingredients: IngredientNutrient[];
  status: string;
}

interface LabelAnalysisResult {
  food_name: string;
  serving_size: string;
  servings_per_container: number;
  nutrition: Record<string, number>;
  image_url: string;
  filename: string;
  status: string;
}

interface VisionStudioProps {
  onExportToLabel?: (data: { name: string; ingredients: { name: string; grams: number }[] }) => void;
  onExportToRecipe?: (data: any) => void;
}

export const VisionStudio: React.FC<VisionStudioProps> = ({
  onExportToLabel,
  onExportToRecipe,
}) => {
  const { currentUser } = useAuth();
  const [mode, setMode] = useState<'meal' | 'label'>('meal');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [userNotes, setUserNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [error, setError] = useState<string | null>(null);

  const [mealResult, setMealResult] = useState<MealAnalysisResult | null>(null);
  const [labelResult, setLabelResult] = useState<LabelAnalysisResult | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setError('Please select a valid image file (JPEG, PNG, WebP).');
      return;
    }
    setError(null);
    setSelectedFile(file);
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    setMealResult(null);
    setLabelResult(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;

    setLoading(true);
    setError(null);

    try {
      const token = await currentUser?.getIdToken();
      const formData = new FormData();
      formData.append('file', selectedFile);

      if (mode === 'meal') {
        setLoadingMessage('AI is visually inspecting meal & cross-referencing USDA database...');
        if (userNotes.trim()) {
          formData.append('notes', userNotes);
        }

        const res = await fetch('/api/vision/meal', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Meal analysis failed.');
        }

        const data: MealAnalysisResult = await res.json();
        setMealResult(data);
      } else {
        setLoadingMessage('Scanning physical Nutrition Facts & reconstructing digital FDA label...');
        const res = await fetch('/api/vision/label', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Label reconstruction failed.');
        }

        const data: LabelAnalysisResult = await res.json();
        setLabelResult(data);
      }
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred during vision analysis.');
    } finally {
      setLoading(false);
      setLoadingMessage('');
    }
  };

  const handleSendToLabelBuilder = () => {
    if (!mealResult || !onExportToLabel) return;
    const formattedIngredients = mealResult.ingredients.map(ing => ({
      name: ing.name,
      grams: ing.grams || 100,
    }));
    onExportToLabel({
      name: mealResult.meal_name,
      ingredients: formattedIngredients,
    });
  };

  const handleSendToRecipeLab = () => {
    if (!mealResult || !onExportToRecipe) return;
    onExportToRecipe(mealResult);
  };

  return (
    <div className="vision-studio">
      <div className="vision-header">
        <h2 className="vision-title">📸 Multimodal Vision Studio</h2>
        <p className="vision-subtitle">
          Snap a photo of your meal or scan a packaged nutrition label to get instant, USDA-grounded data.
        </p>
      </div>

      {/* Mode Selector */}
      <div className="vision-modes">
        <button
          className={`mode-btn ${mode === 'meal' ? 'active' : ''}`}
          onClick={() => {
            setMode('meal');
            setError(null);
          }}
        >
          🍽️ Meal & Plate Analyzer
        </button>
        <button
          className={`mode-btn ${mode === 'label' ? 'active' : ''}`}
          onClick={() => {
            setMode('label');
            setError(null);
          }}
        >
          🏷️ Physical Label OCR & Reconstructor
        </button>
      </div>

      {/* Upload Box */}
      <div className="upload-card">
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          accept="image/*"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFileSelect(e.target.files[0]);
            }
          }}
        />

        {!previewUrl ? (
          <div
            className="dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="dropzone-icon">📷</div>
            <div className="dropzone-text">
              {mode === 'meal'
                ? 'Drop a plate photo here or click to browse'
                : 'Drop a Nutrition Facts label photo here or click to browse'}
            </div>
            <div className="dropzone-hint">Supports JPEG, PNG, and WebP (up to 10MB)</div>
          </div>
        ) : (
          <div className="preview-container">
            <img src={previewUrl} alt="Preview" className="image-preview" />
            <button
              className="change-photo-btn"
              onClick={() => fileInputRef.current?.click()}
            >
              🔄 Choose Different Photo
            </button>
          </div>
        )}

        {/* Optional Notes for Meal Analyzer */}
        {mode === 'meal' && previewUrl && (
          <div className="context-box">
            <label htmlFor="user-notes">Optional Preparation or Ingredient Notes:</label>
            <input
              id="user-notes"
              type="text"
              className="context-input"
              value={userNotes}
              onChange={(e) => setUserNotes(e.target.value)}
              placeholder="e.g. Cooked with olive oil, salad dressing on the side, half portion"
            />
          </div>
        )}

        {previewUrl && (
          <button
            className="analyze-btn"
            onClick={handleAnalyze}
            disabled={loading}
          >
            {loading ? (loadingMessage || 'Analyzing with AI...') : (mode === 'meal' ? '✨ Analyze Plate & Macros' : '✨ Scan & Reconstruct Label')}
          </button>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div style={{ background: '#ffebeb', border: '3px solid #ff4d4f', padding: '16px', borderRadius: '14px', color: '#a8071a', fontWeight: 'bold' }}>
          ⚠️ {error}
        </div>
      )}

      {/* Meal Analysis Result */}
      {mealResult && (
        <div className="results-card">
          <div className="result-title-section">
            <h3 className="result-meal-name">{mealResult.meal_name}</h3>
            <p className="result-description">{mealResult.description}</p>
            {mealResult.dietary_flags && mealResult.dietary_flags.length > 0 && (
              <div className="dietary-tags">
                {mealResult.dietary_flags.map((flag, idx) => (
                  <span key={idx} className="diet-tag">✓ {flag}</span>
                ))}
              </div>
            )}
          </div>

          {/* Macro Cards Grid */}
          <div className="macros-grid">
            <div className="macro-box calories">
              <span className="macro-label">Total Calories</span>
              <span className="macro-val">{Math.round(mealResult.recipe_totals.calories || 0)} kcal</span>
            </div>
            <div className="macro-box">
              <span className="macro-label">Protein</span>
              <span className="macro-val">{(mealResult.recipe_totals.protein || 0).toFixed(1)}g</span>
            </div>
            <div className="macro-box">
              <span className="macro-label">Carbohydrates</span>
              <span className="macro-val">{(mealResult.recipe_totals.carbs || 0).toFixed(1)}g</span>
            </div>
            <div className="macro-box">
              <span className="macro-label">Total Fat</span>
              <span className="macro-val">{(mealResult.recipe_totals.fat || 0).toFixed(1)}g</span>
            </div>
            <div className="macro-box">
              <span className="macro-label">Sodium</span>
              <span className="macro-val">{Math.round(mealResult.recipe_totals.sodium || 0)}mg</span>
            </div>
          </div>

          {/* Ingredients Breakdown Table */}
          <div className="ingredients-section">
            <h4 className="section-subtitle">🔍 Detected Ingredients & USDA Portions</h4>
            <table className="items-table">
              <thead>
                <tr>
                  <th>Ingredient</th>
                  <th>Visual Estimate</th>
                  <th>Resolved Weight</th>
                  <th>Calories</th>
                  <th>Protein</th>
                </tr>
              </thead>
              <tbody>
                {mealResult.detected_items.map((item, idx) => {
                  const resolved = mealResult.ingredients[idx] || {};
                  return (
                    <tr key={idx}>
                      <td style={{ fontWeight: 'bold' }}>{item.name}</td>
                      <td>{item.quantity} {item.unit}</td>
                      <td>{resolved.grams ? `${resolved.grams}g` : '—'}</td>
                      <td>{resolved.calories ? `${Math.round(resolved.calories)} kcal` : '—'}</td>
                      <td>{resolved.protein ? `${resolved.protein.toFixed(1)}g` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Action Buttons */}
          <div className="result-actions">
            <button className="action-btn primary" onClick={handleSendToLabelBuilder}>
              🏷️ Create FDA Nutrition Label
            </button>
            <button className="action-btn secondary" onClick={handleSendToRecipeLab}>
              🧪 Edit in Recipe Lab
            </button>
          </div>
        </div>
      )}

      {/* Label Reconstruction Result */}
      {labelResult && (
        <div className="results-card">
          <div className="result-title-section">
            <h3 className="result-meal-name">🏷️ Reconstructed Digital FDA Label</h3>
            <p className="result-description">
              OCR extraction of <strong>{labelResult.food_name}</strong> (Serving size: {labelResult.serving_size}, {labelResult.servings_per_container} servings/container).
            </p>
          </div>

          <div className="label-comparison">
            {previewUrl && (
              <div className="comparison-pane">
                <span className="pane-label">📸 Original Packaging Photo</span>
                <img src={previewUrl} alt="Original Label" className="image-preview" style={{ maxHeight: '420px' }} />
              </div>
            )}
            <div className="comparison-pane">
              <span className="pane-label">✨ Reconstructed Digital FDA Label</span>
              <img
                src={labelResult.image_url}
                alt="Reconstructed FDA Label"
                className="reconstructed-image"
              />
              <a
                href={labelResult.image_url}
                download={labelResult.filename}
                className="action-btn primary"
                style={{ textDecoration: 'none', width: '100%', marginTop: '8px' }}
              >
                📥 Download High-Res PNG
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
