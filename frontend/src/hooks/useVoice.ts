import { useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

export const useVoice = () => {
    const { currentUser } = useAuth();
    const [isPlaying, setIsPlaying] = useState(false);

    const speak = useCallback(async (text: string) => {
        if (!currentUser) return;

        // Cleanup text: remove markdown like ** or *
        const cleanText = text.replace(/[*_#`]/g, '');

        try {
            setIsPlaying(true);
            const token = await currentUser.getIdToken();

            const response = await fetch('/api/speak', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ text: cleanText })
            });

            if (!response.ok) {
                throw new Error('Failed to generate speech');
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);

            audio.onended = () => {
                setIsPlaying(false);
                URL.revokeObjectURL(url);
            };

            await audio.play();
        } catch (error) {
            console.error("Voice error:", error);
            setIsPlaying(false);
        }
    }, [currentUser]);

    return { speak, isPlaying };
};
