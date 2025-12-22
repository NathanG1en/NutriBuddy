import { useState } from 'react';
import type { Ingredient } from '../hooks/useRecipeCalculation';
import { useFoodSearch } from '../hooks/useFoodSearch';

interface Props {
    ingredients: Ingredient[];
    setIngredients: (updater: (prev: Ingredient[]) => Ingredient[]) => void;
}

export function IngredientTable({ ingredients, setIngredients }: Props) {
    const [newName, setNewName] = useState('');
    const [newGrams, setNewGrams] = useState(100);
    const { query, setQuery, results, loading } = useFoodSearch();

    const handleAdd = () => {
        // Use the selected result description if available, otherwise raw input
        const nameToAdd = results && results.description === query ? results.description : (query || newName);

        if (!nameToAdd) return;

        const newIng: Ingredient = {
            id: Math.random().toString(36).substr(2, 9),
            name: nameToAdd,
            grams: Number(newGrams)
        };

        setIngredients(prev => [...prev, newIng]);
        setNewName('');
        setQuery('');
        setNewGrams(100);
    };

    const remove = (id: string) => {
        setIngredients(prev => prev.filter(i => i.id !== id));
    };

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setNewName(e.target.value);
        setQuery(e.target.value);
    }

    const selectSuggestion = (desc: string) => {
        setNewName(desc);
        setQuery(desc); // Keep it consistent so we don't re-trigger search needlessly or known it matches
        // Ideally we'd close the dropdown here
    }

    return (
        <div className="ingredient-table-container">
            <h3>Ingredients</h3>

            <div className="add-row">
                <div className="search-wrapper">
                    <input
                        type="text"
                        placeholder="Search ingredient (e.g. 'Avocado')"
                        value={newName}
                        onChange={handleSearchChange}
                        className="ingredient-input"
                    />
                    {results && query && results.description.toLowerCase().includes(query.toLowerCase()) && (
                        <div className="search-suggestions" onClick={() => selectSuggestion(results.description)}>
                            <div className="suggestion-item">
                                {results.description}
                            </div>
                        </div>
                    )}
                </div>

                <input
                    type="number"
                    placeholder="Grams"
                    value={newGrams}
                    onChange={e => setNewGrams(Number(e.target.value))}
                    className="grams-input"
                />
                <button onClick={handleAdd} disabled={!newName}>Add</button>
            </div>

            <ul className="ingredient-list">
                {ingredients.map(ing => (
                    <li key={ing.id} className="ingredient-item">
                        <span>{ing.name}</span>
                        <span className="grams">{ing.grams}g</span>
                        <button onClick={() => remove(ing.id)} className="remove-btn">×</button>
                    </li>
                ))}
            </ul>
        </div>
    );
}
