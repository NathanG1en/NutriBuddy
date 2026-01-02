import { useState, useEffect } from 'react';

export interface Ingredient {
    id: string;
    name: string;
    grams: number;
}

interface NutritionResult {
    recipe_totals: Record<string, number>;
    per_serving: Record<string, number>;
    ingredients: any[];
}

export function useRecipeCalculation(
    ingredients: Ingredient[],
    servingSizeGrams: number,
    servings: number
) {
    const [nutrition, setNutrition] = useState<NutritionResult | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const calculate = async () => {
            if (ingredients.length === 0) {
                setNutrition(null);
                return;
            }

            setLoading(true);
            try {
                const res = await fetch('/api/recipe/calculate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        recipe_name: "Draft Recipe",
                        ingredients: ingredients.map(i => ({ name: i.name, grams: i.grams })),
                        serving_size_grams: servingSizeGrams, // This might need adjustment if logic differs
                        servings_per_container: servings
                    })
                });

                if (res.ok) {
                    const data = await res.json();
                    setNutrition({
                        recipe_totals: data.totals,
                        per_serving: data.per_serving,
                        ingredients: data.ingredients
                    });
                }
            } catch (err) {
                console.error("Calculation failed", err);
            } finally {
                setLoading(false);
            }
        };

        const debounce = setTimeout(calculate, 800);
        return () => clearTimeout(debounce);
    }, [ingredients, servingSizeGrams, servings]);

    return { nutrition, loading };
}
