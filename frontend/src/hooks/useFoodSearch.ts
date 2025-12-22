import { useState, useEffect } from 'react';

interface FoodResult {
    fdc_id: number;
    description: string;
}

export function useFoodSearch() {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<FoodResult | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const search = async () => {
            if (!query || query.length < 3) {
                setResults(null);
                return;
            }

            setLoading(true);
            try {
                const res = await fetch(`http://localhost:8000/api/recipe/search?query=${encodeURIComponent(query)}`);
                if (res.ok) {
                    const data = await res.json();
                    if (!data.error) {
                        setResults(data);
                    } else {
                        setResults(null);
                    }
                }
            } catch (err) {
                console.error("Search failed", err);
            } finally {
                setLoading(false);
            }
        };

        const debounce = setTimeout(search, 500);
        return () => clearTimeout(debounce);
    }, [query]);

    return { query, setQuery, results, loading };
}
