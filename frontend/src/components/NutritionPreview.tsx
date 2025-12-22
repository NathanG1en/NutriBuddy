interface Props {
    nutrition: Record<string, number> | undefined;
    loading: boolean;
}

export function NutritionPreview({ nutrition, loading }: Props) {
    if (loading) return <div className="preview-card loading">Calculating...</div>;
    if (!nutrition) return <div className="preview-card empty">Add ingredients to see nutrition info</div>;

    const items = [
        { label: 'Calories', key: 'calories', unit: '' },
        { label: 'Protein', key: 'protein', unit: 'g' },
        { label: 'Carbs', key: 'carbs', unit: 'g' },
        { label: 'Fat', key: 'fat', unit: 'g' },
        { label: 'Fiber', key: 'fiber', unit: 'g' },
        { label: 'Sugar', key: 'sugars', unit: 'g' },
    ];

    return (
        <div className="preview-card">
            <h4>Nutrition Preview (Per Serving)</h4>
            <div className="nutrition-grid">
                {items.map(item => (
                    <div key={item.key} className="nutrient-stat">
                        <span className="label">{item.label}</span>
                        <span className="value">
                            {nutrition[item.key]?.toFixed(1) || 0}{item.unit}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
