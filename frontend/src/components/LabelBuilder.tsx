import { useState, useEffect } from 'react';
import { IngredientTable } from './IngredientTable';
import { NutritionPreview } from './NutritionPreview';
import { ServingControls } from './ServingControls';
import { useRecipeCalculation, type Ingredient } from '../hooks/useRecipeCalculation';

interface LabelBuilderProps {
    initialData?: {
        name: string;
        ingredients: { name: string; grams: number }[];
    } | null;
}

export function LabelBuilder({ initialData }: LabelBuilderProps) {
    const [ingredients, setIngredients] = useState<Ingredient[]>([]);
    const [recipeName, setRecipeName] = useState('My Custom Recipe');
    const [servingSize, setServingSize] = useState('1 cup');
    const [servingGrams, setServingGrams] = useState(100);
    const [servings, setServings] = useState(4);
    const [labelUrl, setLabelUrl] = useState<string | null>(null);

    // Hydrate from initialData
    useEffect(() => {
        if (initialData) {
            setRecipeName(initialData.name);
            setIngredients(initialData.ingredients.map((ing, i) => ({
                id: i.toString(), // Simple ID generation
                name: ing.name,
                grams: ing.grams
            })));
        }
    }, [initialData]);

    // Live calculation
    const { nutrition, loading: calcLoading } = useRecipeCalculation(
        ingredients,
        servingGrams,
        servings
    );

    const handleGenerate = async () => {
        if (!nutrition) return;

        try {
            const res = await fetch('/api/recipe/label', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    recipe_name: recipeName,
                    serving_size: servingSize,
                    servings: servings,
                    nutrition: nutrition.per_serving
                })
            });

            if (res.ok) {
                const data = await res.json();
                setLabelUrl(data.url);
            }
        } catch (e) {
            console.error(e);
            alert("Failed to generate label");
        }
    };

    return (
        <div className="label-builder">
            <div className="builder-left">
                <h2>🛠️ Recipe Builder</h2>

                <div className="section">
                    <label>Recipe Name</label>
                    <input
                        value={recipeName}
                        onChange={e => setRecipeName(e.target.value)}
                        className="recipe-name-input"
                    />
                </div>

                <IngredientTable
                    ingredients={ingredients}
                    setIngredients={setIngredients}
                />

                <ServingControls
                    servingSize={servingSize}
                    setServingSize={setServingSize}
                    servings={servings}
                    setServings={setServings}
                    servingGrams={servingGrams}
                    setServingGrams={setServingGrams}
                />
            </div>

            <div className="builder-right">
                <NutritionPreview nutrition={nutrition?.per_serving} loading={calcLoading} />

                <div className="actions">
                    <button
                        className="generate-btn"
                        onClick={handleGenerate}
                        disabled={ingredients.length === 0 || calcLoading}
                    >
                        🎨 Generate Label
                    </button>
                </div>

                {labelUrl && (
                    <div className="label-result">
                        <h3>Result:</h3>
                        <img src={labelUrl} alt="Nutrition Label" />
                        <a href={labelUrl} download="nutrition-label.png" className="download-btn">
                            📥 Download PNG
                        </a>
                    </div>
                )}
            </div>
        </div>
    );
}
