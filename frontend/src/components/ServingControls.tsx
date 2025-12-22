interface Props {
    servingSize: string;
    setServingSize: (val: string) => void;
    servings: number;
    setServings: (val: number) => void;
    servingGrams: number;
    setServingGrams: (val: number) => void;
}

export function ServingControls({
    servingSize, setServingSize,
    servings, setServings,
    servingGrams, setServingGrams
}: Props) {
    return (
        <div className="serving-controls">
            <div className="control-group">
                <label>Serving Name</label>
                <input
                    value={servingSize}
                    onChange={e => setServingSize(e.target.value)}
                    placeholder="e.g. 1 bar"
                />
            </div>

            <div className="control-group">
                <label>Serving Weight(g)</label>
                <input
                    type="number"
                    value={servingGrams}
                    onChange={e => setServingGrams(Number(e.target.value))}
                />
            </div>

            <div className="control-group">
                <label>Servings Per Container</label>
                <input
                    type="number"
                    value={servings}
                    onChange={e => setServings(Number(e.target.value))}
                />
            </div>
        </div>
    );
}
